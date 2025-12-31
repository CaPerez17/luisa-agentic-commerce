"""
OpenAI Planner: Genera plan de venta estructurado (JSON).
Solo se llama cuando aporta valor (indeciso, objeción, soporte complejo).
"""
import json
import httpx
import time
from typing import Dict, Any, Optional, List

from app.config import (
    OPENAI_ENABLED,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS
)
from app.domain.schemas import PlannerOutput, Recommendation
from app.domain.business_facts import (
    get_business_facts_summary,
    get_promotions_for_context,
    get_price_ranges_for_context
)
from app.logging_config import logger


# Configuración del planner
PLANNER_MODEL = "gpt-4o-mini"  # Modelo barato
PLANNER_MAX_TOKENS = 250
PLANNER_TIMEOUT = 8


def plan_sales_conversation(
    text: str,
    intent: str,
    current_state: dict,
    conversation_history: List[Dict[str, Any]] = None
) -> Optional[PlannerOutput]:
    """
    Genera un plan de venta estructurado usando OpenAI.
    
    Args:
        text: Mensaje del usuario
        intent: Intent detectado
        current_state: Estado conversacional actual
        conversation_history: Historial reciente
    
    Returns:
        PlannerOutput o None si falla
    """
    if not OPENAI_ENABLED or not OPENAI_API_KEY:
        return None
    
    # Obtener facts del negocio
    business_facts = get_business_facts_summary()
    promotions = get_promotions_for_context()
    price_ranges = get_price_ranges_for_context()
    
    # Preparar contexto del estado actual
    slots = current_state.get("slots", {})
    stage = current_state.get("stage", "discovery")
    
    # Preparar historial corto
    history_context = ""
    if conversation_history:
        recent = conversation_history[-4:]  # Últimos 4 turnos
        history_context = "\n".join([
            f"{'Usuario' if m.get('sender') == 'customer' else 'Luisa'}: {m.get('text', '')[:80]}"
            for m in recent
        ])
    
    system_prompt = f"""Eres un planner de ventas para un asistente comercial de máquinas de coser.

{business_facts}

REGLAS ESTRICTAS:
1. NO inventes precios, horarios, dirección, garantía. Solo usa los facts proporcionados.
2. Si no hay datos suficientes, pregunta 1 cosa clave.
3. Si detectas objeción (caro, solo averiguo, desconfianza), propón respuesta de contención + CTA suave.
4. Recomendaciones SOLO de productos que están en los facts (KT-D3, KS-8800, familiares desde $400.000).
5. Máximo 2-3 líneas en recommended_reply_base.
6. 1 pregunta máxima en next_best_question.
7. CTA natural: visita/envío/reservar (no forzado).

OBJETIVO: Generar un plan de venta que cierre (visita/envío/reservar) de forma natural."""

    user_prompt = f"""Mensaje del usuario: "{text}"
Intent detectado: {intent}
Stage actual: {stage}
Slots actuales: {json.dumps(slots, ensure_ascii=False)}

{('Historial reciente:\n' + history_context) if history_context else ''}

Genera un plan de venta en JSON con este schema:
{{
  "intent": "intent_name",
  "confidence": 0.0-1.0,
  "slots": {{"product_type": "...", "use_case": "...", "qty": "...", "budget": "...", "city": "...", "visit_or_delivery": "visit|delivery|unknown"}},
  "user_goal": "objetivo del usuario (1 línea)",
  "assistant_goal": "cierre deseado (visita/envío/reservar)",
  "next_best_question": "UNA pregunta o null",
  "recommended_reply_base": "respuesta base segura (2-3 líneas, SIN inventar facts)",
  "recommendations": [
    {{"name": "KT-D3", "why": "...", "price": 1230000, "conditions": "..."}}
  ],
  "should_offer_visit": true/false,
  "should_offer_shipping": true/false,
  "handoff_needed": true/false,
  "handoff_reason": "..."
}}"""

    try:
        start_time = time.perf_counter()
        
        with httpx.Client(timeout=PLANNER_TIMEOUT) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": PLANNER_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": PLANNER_MAX_TOKENS,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                }
            )
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                try:
                    parsed = json.loads(content)
                    
                    # Validar que no inventó precios
                    for rec in parsed.get("recommendations", []):
                        if rec.get("price"):
                            # Verificar que el precio esté en facts
                            valid_prices = [p["price"] for p in promotions] + [price_ranges["familiar"]["min"], price_ranges["industrial"]["min"]]
                            if rec["price"] not in valid_prices:
                                logger.warning("Planner inventó precio", price=rec["price"])
                                rec["price"] = None
                    
                    planner_output = PlannerOutput(**parsed)
                    
                    logger.info(
                        "OpenAI planner exitoso",
                        intent=planner_output.intent,
                        confidence=planner_output.confidence,
                        recommendations_count=len(planner_output.recommendations),
                        elapsed_ms=round(elapsed_ms, 1)
                    )
                    
                    return planner_output
                except Exception as e:
                    logger.error("Error parseando planner output", error=str(e))
                    return None
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                logger.warning(
                    "Error en OpenAI planner",
                    status_code=response.status_code,
                    error=error_msg,
                    elapsed_ms=round(elapsed_ms, 1)
                )
                return None
                
    except httpx.TimeoutException:
        logger.warning("Timeout en OpenAI planner")
        return None
    except Exception as e:
        logger.error("Error en OpenAI planner", error=str(e))
        return None

