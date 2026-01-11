"""
Servicio de análisis de continuidad conversacional.

Analiza si un saludo debería iniciar una nueva conversación o continuar una existente.
Usa LLM para análisis de contexto cuando es necesario.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import asyncio

from app.config import OPENAI_ENABLED
from app.services.llm_adapter import get_llm_suggestion_sync, LLMTaskType
from app.logging_config import logger


# Tiempo mínimo sin actividad para considerar nueva conversación (30 minutos)
CONVERSATION_TIMEOUT_MINUTES = 30
# Tiempo sin actividad para usar LLM en análisis (15 minutos)
LLM_CONTINUITY_THRESHOLD_MINUTES = 15


class ContinuityDecision:
    """Decisión de continuidad conversacional."""
    NEW_CONVERSATION = "new_conversation"
    CONTINUE_CONVERSATION = "continue_conversation"
    ASK_CLARIFICATION = "ask_clarification"


def analyze_conversation_continuity(
    text: str,
    intent: str,
    history: List[Dict[str, Any]],
    state: Dict[str, Any],
    conversation_id: str
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Analiza si un saludo debería iniciar nueva conversación o continuar existente.
    
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
    
    # Si no es saludo, siempre continuar
    if intent != "saludo":
        return ContinuityDecision.CONTINUE_CONVERSATION, "not_greeting", metadata
    
    # Si no hay historial, es nueva conversación
    if not history or len(history) == 0:
        return ContinuityDecision.NEW_CONVERSATION, "no_history", metadata
    
    # Calcular tiempo desde último mensaje
    last_message_time = _get_last_message_time(history)
    if not last_message_time:
        return ContinuityDecision.NEW_CONVERSATION, "no_last_message_time", metadata
    
    time_since_last = datetime.now(timezone.utc) - last_message_time
    time_since_last_minutes = time_since_last.total_seconds() / 60
    metadata["time_since_last_minutes"] = round(time_since_last_minutes, 1)
    
    # USAR LLM SIEMPRE para análisis de continuidad (si está habilitado)
    if OPENAI_ENABLED:
        return _analyze_continuity_with_llm(text, history, state, conversation_id, metadata)
    
    # Fallback a heurísticas solo si LLM está deshabilitado
    # Si ha pasado mucho tiempo (>30 min), es nueva conversación
    if time_since_last_minutes > CONVERSATION_TIMEOUT_MINUTES:
        return ContinuityDecision.NEW_CONVERSATION, f"timeout_no_llm_{time_since_last_minutes:.0f}min", metadata
    
    # Si ha pasado poco tiempo (<5 min), continuar conversación
    if time_since_last_minutes < 5:
        return ContinuityDecision.CONTINUE_CONVERSATION, f"recent_no_llm_{time_since_last_minutes:.0f}min", metadata
    
    # Por defecto, continuar si hay estado activo, nueva si no
    if state.get("last_intent") or state.get("stage") not in ["discovery", "triage"]:
        return ContinuityDecision.CONTINUE_CONVERSATION, "no_llm_has_active_state", metadata
    else:
        return ContinuityDecision.NEW_CONVERSATION, "no_llm_no_active_state", metadata


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


def _analyze_continuity_with_llm(
    text: str,
    history: List[Dict[str, Any]],
    state: Dict[str, Any],
    conversation_id: str,
    metadata: Dict[str, Any]
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Usa LLM para analizar si es nueva conversación o continuación.
    
    Returns:
        Tuple[decision, reason, metadata]
    """
    metadata["llm_used"] = True
    
    try:
        # Formatear historial reciente (últimos 8 mensajes)
        recent_history = history[-8:] if len(history) > 8 else history
        history_text = _format_history_for_continuity(recent_history)
        
        # Crear prompt para análisis de continuidad
        context = {
            "contexto_conversacion": {
                "ultimo_intent": state.get("last_intent"),
                "stage": state.get("stage", "discovery"),
                "time_since_last_minutes": metadata["time_since_last_minutes"]
            },
            "datos_negocio": {
                "horarios": "Lunes a viernes: 9am-6pm, Sábados: 9am-2pm",
                "direccion": "Calle 34 #1-30, Montería"
            },
            "productos_recomendados": []
        }
        
        # Crear prompt específico para continuidad
        user_message = f"""El cliente dice: "{text}"

HISTORIAL RECIENTE:
{history_text}

ESTADO ACTUAL:
- Último intent: {state.get('last_intent', 'ninguno')}
- Stage: {state.get('stage', 'discovery')}
- Tiempo desde último mensaje: {metadata['time_since_last_minutes']:.1f} minutos

INSTRUCCIONES:
Analiza si este saludo debería:
1. INICIAR NUEVA CONVERSACIÓN (si el tema anterior ya se resolvió o cambió completamente)
2. CONTINUAR CONVERSACIÓN (si el tema anterior sigue siendo relevante)
3. PEDIR ACLARACIÓN (si no está claro)

Responde SOLO con una de estas palabras: NUEVA, CONTINUAR, o ACLARAR"""
        
        # Llamar LLM con prompt personalizado
        # Nota: Usamos CONSULTA_COMPLEJA como task_type porque es análisis, no generación de texto
        llm_response, llm_metadata = get_llm_suggestion_sync(
            task_type=LLMTaskType.CONSULTA_COMPLEJA,
            user_message=user_message,
            context=context,
            conversation_history=None,  # Ya incluimos historial en el prompt
            conversation_id=conversation_id,
            reason_for_llm_use="continuity_analysis"
        )
        
        metadata["llm_success"] = llm_metadata.get("success", False)
        metadata["llm_latency_ms"] = llm_metadata.get("latency_ms", 0)
        
        if llm_response:
            # Parsear respuesta del LLM
            llm_response_lower = llm_response.lower().strip()
            if "nueva" in llm_response_lower or "new" in llm_response_lower:
                return ContinuityDecision.NEW_CONVERSATION, "llm_analyzed_new", metadata
            elif "continuar" in llm_response_lower or "continue" in llm_response_lower:
                return ContinuityDecision.CONTINUE_CONVERSATION, "llm_analyzed_continue", metadata
            elif "aclarar" in llm_response_lower or "clarify" in llm_response_lower or "ask" in llm_response_lower:
                return ContinuityDecision.ASK_CLARIFICATION, "llm_analyzed_unclear", metadata
        
        # Si LLM falla, usar heurística por defecto
        logger.warning("LLM no retornó decisión clara de continuidad", response=llm_response[:100] if llm_response else None)
        if state.get("last_intent") or state.get("stage") not in ["discovery", "triage"]:
            return ContinuityDecision.CONTINUE_CONVERSATION, "llm_fallback_continue", metadata
        else:
            return ContinuityDecision.NEW_CONVERSATION, "llm_fallback_new", metadata
        
    except Exception as e:
        logger.error("Error en análisis de continuidad con LLM", error=str(e), conversation_id=conversation_id)
        metadata["llm_error"] = str(e)
        # Fallback: usar heurística
        if state.get("last_intent") or state.get("stage") not in ["discovery", "triage"]:
            return ContinuityDecision.CONTINUE_CONVERSATION, "llm_error_fallback_continue", metadata
        else:
            return ContinuityDecision.NEW_CONVERSATION, "llm_error_fallback_new", metadata


def _format_history_for_continuity(history: List[Dict[str, Any]]) -> str:
    """Formatea historial para análisis de continuidad."""
    if not history:
        return "Sin historial previo"
    
    lines = []
    for msg in history:
        sender = "Cliente" if msg.get("sender") == "customer" else "Luisa"
        text = msg.get("text", "")[:100]  # Limitar longitud
        timestamp = msg.get("timestamp", "")
        lines.append(f"{sender}: {text}")
    
    return "\n".join(lines)


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
