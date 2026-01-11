"""
Servicio de análisis de continuidad conversacional.

Analiza si un mensaje debería iniciar una nueva conversación o continuar una existente.
Detecta señales explícitas de nueva conversación y usa heurísticas de tiempo.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import re

from app.config import OPENAI_ENABLED
from app.logging_config import logger


# Tiempo mínimo sin actividad para considerar nueva conversación (30 minutos)
CONVERSATION_TIMEOUT_MINUTES = 30
# Tiempo para considerar conversación "reciente" (5 minutos)
RECENT_CONVERSATION_MINUTES = 5


class ContinuityDecision:
    """Decisión de continuidad conversacional."""
    NEW_CONVERSATION = "new_conversation"
    CONTINUE_CONVERSATION = "continue_conversation"
    ASK_CLARIFICATION = "ask_clarification"


# Frases que explícitamente indican nueva conversación
NEW_CONVERSATION_SIGNALS = [
    "otra conversación", "otra conversacion",
    "tema nuevo", "nuevo tema",
    "cambio de tema", "cambiar de tema",
    "empezar de nuevo", "empezar de cero",
    "otra cosa", "algo diferente", "algo distinto",
    "no es eso", "no era eso",
    "olvidalo", "olvídalo", "olvida eso",
    "dejemos eso", "deja eso",
    "quiero otra cosa", "necesito otra cosa"
]


def is_explicit_new_conversation(text: str) -> bool:
    """Detecta si el texto indica explícitamente una nueva conversación."""
    text_lower = text.lower().strip()
    for signal in NEW_CONVERSATION_SIGNALS:
        if signal in text_lower:
            return True
    return False


def needs_continuity_analysis(text: str, intent: str) -> bool:
    """
    Determina si el mensaje necesita análisis de continuidad.
    
    Returns:
        True si es saludo o señal explícita de nueva conversación
    """
    # Si es saludo, necesita análisis
    if intent == "saludo":
        return True
    
    # Si es señal explícita de nueva conversación
    if is_explicit_new_conversation(text):
        return True
    
    return False


def analyze_conversation_continuity(
    text: str,
    intent: str,
    history: List[Dict[str, Any]],
    state: Dict[str, Any],
    conversation_id: str
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Analiza si un mensaje debería iniciar nueva conversación o continuar existente.
    
    Args:
        text: Mensaje del usuario
        intent: Intención detectada
        history: Historial de mensajes
        state: Estado conversacional actual
        conversation_id: ID de la conversación
    
    Returns:
        Tuple[decision, reason, metadata]:
            - decision: "new_conversation", "continue_conversation", o "ask_clarification"
            - reason: Razón de la decisión
            - metadata: Metadatos adicionales (time_since_last, llm_used, etc.)
    """
    metadata = {
        "time_since_last_minutes": None,
        "llm_used": False,
        "history_length": len(history) if history else 0,
        "has_active_state": bool(state.get("last_intent")),
        "stage": state.get("stage", "discovery")
    }
    
    # REGLA 1: Si el usuario dice EXPLÍCITAMENTE que es otra conversación → NUEVA
    if is_explicit_new_conversation(text):
        return ContinuityDecision.NEW_CONVERSATION, "explicit_new_conversation", metadata
    
    # REGLA 2: Si no es saludo ni señal explícita, continuar normalmente
    if intent != "saludo":
        return ContinuityDecision.CONTINUE_CONVERSATION, "not_greeting", metadata
    
    # REGLA 3: Si no hay historial, es nueva conversación
    if not history or len(history) == 0:
        return ContinuityDecision.NEW_CONVERSATION, "no_history", metadata
    
    # Calcular tiempo desde último mensaje
    last_message_time = _get_last_message_time(history)
    if not last_message_time:
        return ContinuityDecision.NEW_CONVERSATION, "no_last_message_time", metadata
    
    time_since_last = datetime.now(timezone.utc) - last_message_time
    time_since_last_minutes = time_since_last.total_seconds() / 60
    metadata["time_since_last_minutes"] = round(time_since_last_minutes, 1)
    
    # REGLA 4: Si ha pasado mucho tiempo (>30 min), es nueva conversación
    if time_since_last_minutes > CONVERSATION_TIMEOUT_MINUTES:
        return ContinuityDecision.NEW_CONVERSATION, f"timeout_{time_since_last_minutes:.0f}min", metadata
    
    # REGLA 5: Si ha pasado poco tiempo (<5 min), continuar sin preguntar
    if time_since_last_minutes < RECENT_CONVERSATION_MINUTES:
        return ContinuityDecision.CONTINUE_CONVERSATION, f"recent_{time_since_last_minutes:.0f}min", metadata
    
    # REGLA 6: Zona gris (5-30 min) → Preguntar al usuario
    # No usar LLM, simplemente preguntar para evitar errores
    return ContinuityDecision.ASK_CLARIFICATION, f"ambiguous_{time_since_last_minutes:.0f}min", metadata


def _get_last_message_time(history: List[Dict[str, Any]]) -> Optional[datetime]:
    """Obtiene el timestamp del último mensaje del historial."""
    if not history:
        return None
    
    last_message = history[-1]
    timestamp = last_message.get("timestamp")
    
    if not timestamp:
        return None
    
    try:
        # Intentar parsear timestamp
        if isinstance(timestamp, str):
            # Formato ISO o SQLite timestamp
            if "T" in timestamp or " " in timestamp:
                parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00").replace(" ", "T"))
                if parsed_time.tzinfo is None:
                    parsed_time = parsed_time.replace(tzinfo=timezone.utc)
                return parsed_time
            else:
                # Formato SQLite simple
                parsed_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                return parsed_time
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=timezone.utc)
            return timestamp
    except Exception as e:
        logger.warning("Error parseando timestamp del historial", error=str(e), timestamp=str(timestamp))
    
    return None


def generate_clarification_message(conversation_id: str) -> str:
    """Genera mensaje para pedir clarificación al usuario."""
    from app.rules.keywords import select_variant
    
    # Variantes de mensaje de clarificación
    CLARIFICATION_VARIANTS = [
        "¡Hola! 😊 ¿Estás preguntando sobre lo mismo de antes o es algo nuevo?",
        "¡Hola! ¿Seguimos con lo anterior o es un tema nuevo?"
    ]
    
    variant_key = conversation_id if conversation_id else "default"
    return select_variant(variant_key, CLARIFICATION_VARIANTS)
