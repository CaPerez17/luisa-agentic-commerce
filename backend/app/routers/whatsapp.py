"""
Router para webhooks de WhatsApp Cloud API.
"""
from fastapi import APIRouter, Request, Response, HTTPException, Query
from typing import Optional
import json

from app.config import (
    WHATSAPP_ENABLED,
    WHATSAPP_VERIFY_TOKEN,
    HANDOFF_COOLDOWN_MINUTES
)
from app.models.database import (
    create_or_update_conversation,
    save_message,
    get_conversation_history,
    get_conversation_mode,
    set_conversation_mode
)
from app.services.whatsapp_service import (
    parse_webhook_message,
    is_status_update,
    send_whatsapp_message,
    send_internal_notification,
    get_phone_conversation_id
)
from app.services.rate_limit import allow as rl_allow, remaining as rl_remaining
from app.services.context_service import extract_context_from_history
from app.services.intent_service import analyze_intent
from app.services.handoff_service import process_handoff, generate_handoff_message
from app.services.trace_service import trace_interaction
from app.rules.business_guardrails import is_business_related, get_off_topic_response
from app.logging_config import logger


router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """
    Verificación del webhook de WhatsApp.
    Facebook/Meta envía una solicitud GET para verificar el endpoint.
    """
    if not WHATSAPP_ENABLED:
        raise HTTPException(status_code=503, detail="WhatsApp no habilitado")
    
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook WhatsApp verificado")
        return Response(content=hub_challenge, media_type="text/plain")
    
    logger.warning(
        "Verificación de webhook fallida",
        mode=hub_mode,
        token_match=(hub_verify_token == WHATSAPP_VERIFY_TOKEN)
    )
    raise HTTPException(status_code=403, detail="Verificación fallida")


@router.post("/webhook")
async def receive_webhook(request: Request):
    """
    Recibe mensajes entrantes de WhatsApp.
    """
    if not WHATSAPP_ENABLED:
        return {"status": "disabled"}
    
    try:
        body = await request.json()
    except:
        logger.warning("Webhook recibido sin JSON válido")
        return {"status": "ok"}
    
    # Ignorar actualizaciones de estado
    if is_status_update(body):
        return {"status": "ok"}
    
    # Parsear mensaje
    parsed = parse_webhook_message(body)
    if not parsed:
        return {"status": "ok"}
    
    phone_from = parsed["phone_from"]
    text = parsed["text"]
    contact_name = parsed.get("contact_name")

    # Rate limit por número (ventana 60s)
    rate_key = f"wa:{phone_from}"
    if not rl_allow(rate_key, limit_per_minute=20):
        logger.warning(
            "Rate limit WhatsApp",
            phone=phone_from[-4:],
            remaining=rl_remaining(rate_key, 20)
        )
        return Response(status_code=429, content=json.dumps({"status": "rate_limited"}), media_type="application/json")
    
    logger.info(
        "Mensaje WhatsApp recibido",
        phone=phone_from[-4:],  # Solo últimos 4 dígitos por privacidad
        text_length=len(text)
    )
    
    # Obtener o crear conversación
    conversation_id = get_phone_conversation_id(phone_from)
    create_or_update_conversation(conversation_id, phone_from, "whatsapp")
    
    # Verificar modo de conversación (modo sombra)
    mode = get_conversation_mode(conversation_id)
    
    # Guardar mensaje del cliente
    save_message(conversation_id, text, "customer")
    
    # Si está en modo HUMAN_ACTIVE, solo registrar (no responder)
    if mode == "HUMAN_ACTIVE":
        logger.info(
            "Mensaje registrado en modo HUMAN_ACTIVE",
            conversation_id=conversation_id
        )
        return {"status": "ok", "mode": "human_active"}
    
    # Procesar mensaje con trazabilidad
    with trace_interaction(conversation_id, "whatsapp", phone_from) as tracer:
        tracer.raw_text = text
        tracer.normalized_text = text.lower().strip()
        
        # Verificar si es del negocio
        is_business, reason = is_business_related(text)
        tracer.business_related = is_business
        
        if not is_business:
            response_text = get_off_topic_response()
            tracer.response_text = response_text
            
            # Enviar respuesta
            success, _ = await send_whatsapp_message(phone_from, response_text)
            if success:
                save_message(conversation_id, response_text, "luisa")
            
            return {"status": "ok", "business_related": False}
        
        # Obtener historial
        history = get_conversation_history(conversation_id)
        
        # Analizar intención
        intent_result = analyze_intent(text, history)
        tracer.intent = intent_result.get("intent")
        
        # Extraer contexto
        context = extract_context_from_history(history)
        
        # Verificar si requiere handoff
        from app.services.handoff_service import should_handoff as check_handoff
        decision = check_handoff(text, context)
        
        if decision.should_handoff:
            tracer.routed_team = decision.team.value if decision.team else None
            
            # Generar respuesta de handoff para el cliente
            response_text = generate_handoff_message(
                text, 
                decision.reason, 
                decision.priority.value,
                context.get("ciudad")
            )
            
            # Procesar handoff (notificación interna)
            _, notification_text, _ = process_handoff(
                conversation_id=conversation_id,
                text=text,
                context=context,
                customer_phone=phone_from,
                customer_name=contact_name,
                history=history
            )
            
            # Enviar notificación interna
            if notification_text:
                await send_internal_notification(notification_text)
        
            # Marcar conversación como pendiente de humano
            # (pero NO silenciar inmediatamente, dar HANDOFF_COOLDOWN_MINUTES)
            
        else:
            # Generar respuesta normal
            # Por ahora usamos una respuesta genérica hasta integrar generate_response completo
            # TODO: Integrar con la lógica completa de generate_response del main.py
            response_text = _generate_whatsapp_response(text, context, intent_result, history)
        
        tracer.response_text = response_text
        
        # Enviar respuesta
        success, _ = await send_whatsapp_message(phone_from, response_text)
        
        if success:
            save_message(conversation_id, response_text, "luisa")
            return {"status": "ok", "response_sent": True}
        else:
            tracer.error = "Error enviando respuesta"
            return {"status": "error", "message": "Error enviando respuesta"}


def _generate_whatsapp_response(
    text: str,
    context: dict,
    intent_result: dict,
    history: list
) -> str:
    """
    Genera respuesta para WhatsApp.
    Versión simplificada que se integrará con el generador completo.
    """
    text_lower = text.lower()
    intent = intent_result.get("intent", "")
    
    # Saludos
    if intent == "saludo" or any(w in text_lower for w in ["hola", "buenas"]):
        return "¡Hola! 👋 Soy Luisa del Almacén El Sastre. ¿Buscas máquina familiar o industrial?"
    
    # Promociones
    if intent == "preguntar_promociones" or "promoción" in text_lower or "oferta" in text_lower:
        return (
            "¡Sí! Tenemos promoción navideña:\n\n"
            "• KINGTER KT-D3: $1.230.000\n"
            "• KANSEW KS-8800: $1.300.000\n\n"
            "Ambas incluyen mesa, motor e instalación. ¿Cuál te interesa?"
        )
    
    # Horario
    if "horario" in text_lower or "hora" in text_lower:
        return (
            "Nuestro horario es:\n\n"
            "📍 Calle 34 #1-30, Montería\n"
            "🕘 Lunes a viernes: 9am-6pm\n"
            "🕘 Sábados: 9am-2pm\n\n"
            "¿Quieres pasar o prefieres envío a domicilio?"
        )
    
    # Precio
    if intent == "preguntar_precio" or "precio" in text_lower:
        if context.get("tipo_maquina") == "industrial":
            return (
                "Las industriales en promoción:\n\n"
                "• KINGTER KT-D3: $1.230.000\n"
                "• KANSEW KS-8800: $1.300.000\n\n"
                "Incluyen mesa, motor ahorrador e instalación. ¿Cuál te interesa?"
            )
        return (
            "Los precios varían según el tipo:\n\n"
            "• Familiares: desde $400.000\n"
            "• Industriales: desde $1.230.000\n\n"
            "¿Buscas para casa o para producción?"
        )
    
    # Tipo de máquina
    if "industrial" in text_lower:
        return "Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
    
    if "familiar" in text_lower or "casa" in text_lower:
        return "Para casa una máquina familiar funciona bien. ¿Qué tipo de costura haces: arreglos, proyectos o costura creativa?"
    
    # Respuesta por defecto con contexto
    if context.get("tipo_maquina"):
        if not context.get("uso"):
            return "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        if not context.get("volumen"):
            return "¿Producción constante o pocas unidades?"
        return "¿En qué ciudad te encuentras para coordinar el envío?"
    
    # Default
    return "¿Buscas máquina familiar (para casa) o industrial (para producción)?"
