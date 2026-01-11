"""
Filtrado Mejorado con LLM para casos ambiguos.

Usa LLM barato (gpt-4o-mini) solo para casos donde las heurísticas
no pueden determinar claramente si un mensaje es personal o del negocio.
"""
import time
from typing import Tuple, Optional
import httpx

from app.config import (
    OPENAI_ENABLED,
    OPENAI_API_KEY,
    ENHANCED_FILTERING_WITH_LLM
)
from app.logging_config import logger

# Configuración del filtrado mejorado
FILTERING_MODEL = "gpt-4o-mini"  # Modelo barato
FILTERING_MAX_TOKENS = 50  # Solo necesitamos "business" o "personal"
FILTERING_TIMEOUT = 3.0  # Timeout corto para no afectar latencia


def is_ambiguous_message(text: str, heuristic_result: bool) -> bool:
    """
    Determina si un mensaje es ambiguo (necesita LLM para clasificar).
    
    Args:
        text: Mensaje del usuario
        heuristic_result: Resultado de heurísticas (True = business, False = personal)
    
    Returns:
        True si el mensaje es ambiguo y necesita LLM
    """
    text_lower = text.lower().strip()
    
    # Casos que son claramente ambiguos:
    # - Mensajes cortos sin contexto claro
    # - Saludos genéricos
    # - Mensajes que pueden ser personales o del negocio
    
    # Si las heurísticas dicen "personal" pero el mensaje es muy corto/ambiguo
    if not heuristic_result and len(text_lower.split()) <= 3:
        # Ejemplos: "Hola", "Buenos días", "¿Cómo estás?"
        ambiguous_greetings = [
            "hola", "buenos días", "buenos dias", "buenas tardes", "buenas noches",
            "cómo estás", "como estas", "qué tal", "que tal", "bien", "ok", "okay"
        ]
        if any(greeting in text_lower for greeting in ambiguous_greetings):
            return True
    
    # Si las heurísticas dicen "business" pero el mensaje es muy corto sin keywords claros
    if heuristic_result and len(text_lower.split()) <= 2:
        # Ejemplos: "Gracias", "Perfecto", "Entendido"
        return True
    
    return False


async def classify_with_llm(text: str) -> Tuple[bool, str]:
    """
    Usa LLM barato para clasificar mensajes ambiguos.
    
    Args:
        text: Mensaje del usuario
    
    Returns:
        Tuple[is_business, reason]:
            - is_business: True si es del negocio, False si es personal
            - reason: Razón de la decisión
    """
    if not OPENAI_ENABLED or not OPENAI_API_KEY or not ENHANCED_FILTERING_WITH_LLM:
        # Si LLM no está habilitado, retornar como business (conservador)
        return True, "llm_disabled_default_business"
    
    start_time = time.perf_counter()
    
    system_prompt = """Eres un clasificador de mensajes para WhatsApp Business de "Almacén y Taller El Sastre", un negocio de máquinas de coser en Montería, Colombia.

Tu tarea es determinar si un mensaje es DEL NEGOCIO o PERSONAL.

MENSAJES DEL NEGOCIO:
- Consultas sobre máquinas de coser, repuestos, servicio técnico
- Preguntas sobre precios, disponibilidad, garantía
- Solicitudes de cotización, instalación, reparación
- Preguntas sobre horarios, dirección, formas de pago
- Saludos que llevan a consultas del negocio

MENSAJES PERSONALES:
- Conversaciones personales/familiares
- Mensajes que no tienen relación con el negocio
- Saludos casuales sin intención de consultar sobre el negocio
- Mensajes sobre temas ajenos al negocio (programación, tareas, etc.)

RESPONDE SOLO: "business" o "personal" (una sola palabra, sin explicación).
"""
    
    user_prompt = f"Mensaje: {text}\n\n¿Es del negocio o personal?"
    
    try:
        async with httpx.AsyncClient(timeout=FILTERING_TIMEOUT) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": FILTERING_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": FILTERING_MAX_TOKENS,
                    "temperature": 0.1  # Muy determinístico
                }
            )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                result = data["choices"][0]["message"]["content"].strip().lower()
                
                is_business = "business" in result
                reason = f"llm_classified_{result[:20]}"
                
                logger.info(
                    "enhanced_filtering_llm_used",
                    text_preview=text[:50],
                    result="business" if is_business else "personal",
                    latency_ms=latency_ms
                )
                
                return is_business, reason
            
            else:
                # Error en LLM: retornar como business (conservador)
                logger.warning(
                    "enhanced_filtering_llm_error",
                    status=response.status_code,
                    text_preview=text[:50]
                )
                return True, "llm_error_default_business"
    
    except Exception as e:
        # Error en LLM: retornar como business (conservador)
        logger.warning(
            "enhanced_filtering_llm_exception",
            error=str(e)[:100],
            text_preview=text[:50]
        )
        return True, "llm_exception_default_business"


async def enhanced_is_business_related(text: str, heuristic_result: Tuple[bool, str]) -> Tuple[bool, str]:
    """
    Versión mejorada de is_business_related que usa LLM para casos ambiguos.
    
    Args:
        text: Mensaje del usuario
        heuristic_result: Resultado de heurísticas (is_business, reason)
    
    Returns:
        Tuple[is_business, reason]: Resultado final
    """
    is_business_heuristic, reason_heuristic = heuristic_result
    
    # Si no es ambiguo, usar resultado de heurísticas
    if not is_ambiguous_message(text, is_business_heuristic):
        return is_business_heuristic, reason_heuristic
    
    # Si es ambiguo, usar LLM
    is_business_llm, reason_llm = await classify_with_llm(text)
    
    # Combinar razones
    combined_reason = f"{reason_heuristic}_ambiguous_enhanced_{reason_llm}"
    
    return is_business_llm, combined_reason
