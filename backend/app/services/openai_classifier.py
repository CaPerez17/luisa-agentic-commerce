"""
OpenAI Classifier: Clasifica intents ambiguos con JSON estricto.
Solo se llama cuando el mensaje es ambiguo o mezcla intents.
"""
import json
import httpx
import time
from typing import Dict, Any, Optional, Tuple, List

from app.config import (
    OPENAI_ENABLED,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS
)
from app.domain.schemas import ClassifierOutput
from app.logging_config import logger


# Configuración del classifier
CLASSIFIER_MODEL = "gpt-4o-mini"  # Modelo barato
CLASSIFIER_MAX_TOKENS = 150
CLASSIFIER_TIMEOUT = 8


def classify_ambiguous_message(
    text: str,
    conversation_history: List[Dict[str, Any]] = None
) -> Optional[ClassifierOutput]:
    """
    Clasifica un mensaje ambiguo usando OpenAI.
    Solo se llama cuando reglas determinísticas no pueden clasificar.
    
    Args:
        text: Mensaje del usuario
        conversation_history: Historial reciente (últimos 3 turnos)
    
    Returns:
        ClassifierOutput o None si falla
    """
    if not OPENAI_ENABLED or not OPENAI_API_KEY:
        return None
    
    # Preparar historial corto
    history_context = ""
    if conversation_history:
        recent = conversation_history[-3:]  # Últimos 3 turnos
        history_context = "\n".join([
            f"{'Usuario' if m.get('sender') == 'customer' else 'Luisa'}: {m.get('text', '')[:100]}"
            for m in recent
        ])
    
    system_prompt = """Eres un clasificador de intenciones para un asistente comercial de máquinas de coser.

INTENTS DISPONIBLES:
- buy_machine: comprar máquina (industrial/familiar)
- spare_parts: repuestos, piezas, agujas, bobinas
- tech_support: garantía, reparación, instalación, soporte técnico
- business_advice: asesoría para montar negocio, emprender, qué máquina conviene
- faq_hours_location: horarios, dirección, ubicación, cómo llegar
- sell_machine: vender/consignar máquina
- other: no clasificable

INSTRUCCIONES:
1. Clasifica el mensaje en UNO de los intents
2. Extrae entidades clave (product_type, use_case, city, etc.)
3. Si el mensaje es ambiguo o mezcla intents, elige el más probable
4. Retorna JSON estricto con el schema definido"""

    history_section = ""
    if history_context:
        history_section = f"Historial reciente:\n{history_context}\n"
    
    user_prompt = f"""Clasifica este mensaje:

"{text}"

{history_section}Retorna JSON con:
{{
  "intent": "intent_name",
  "confidence": 0.0-1.0,
  "entities": {{"product_type": "...", "use_case": "...", "city": "..."}},
  "is_ambiguous": true/false,
  "needs_clarification": true/false
}}"""

    try:
        start_time = time.perf_counter()
        
        with httpx.Client(timeout=CLASSIFIER_TIMEOUT) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": CLASSIFIER_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": CLASSIFIER_MAX_TOKENS,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
            )
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                try:
                    parsed = json.loads(content)
                    classifier_output = ClassifierOutput(**parsed)
                    
                    logger.info(
                        "OpenAI classifier exitoso",
                        intent=classifier_output.intent,
                        confidence=classifier_output.confidence,
                        elapsed_ms=round(elapsed_ms, 1)
                    )
                    
                    return classifier_output
                except Exception as e:
                    logger.error("Error parseando classifier output", error=str(e))
                    return None
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                logger.warning(
                    "Error en OpenAI classifier",
                    status_code=response.status_code,
                    error=error_msg,
                    elapsed_ms=round(elapsed_ms, 1)
                )
                return None
                
    except httpx.TimeoutException:
        logger.warning("Timeout en OpenAI classifier")
        return None
    except Exception as e:
        logger.error("Error en OpenAI classifier", error=str(e))
        return None

