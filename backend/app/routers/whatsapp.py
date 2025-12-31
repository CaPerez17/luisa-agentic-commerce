"""
Router para webhooks de WhatsApp Cloud API.
"""
from fastapi import APIRouter, Request, Response, HTTPException, Query, BackgroundTasks
from typing import Optional
import json
import time

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
    set_conversation_mode,
    mark_wa_message_processed,
    is_wa_message_processed,
    get_conversation_state,
    save_conversation_state
)
from app.services.whatsapp_service import (
    parse_webhook_message,
    is_status_update,
    send_whatsapp_message,
    send_internal_notification,
    get_phone_conversation_id,
    analyze_webhook_event
)
from app.services.sales_dialogue import next_action
from app.services.humanizer import humanize_response_sync
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
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recibe mensajes entrantes de WhatsApp.
    ACK rápido (<1s) con procesamiento en background.
    """
    start_time = time.perf_counter()
    
    if not WHATSAPP_ENABLED:
        return {"status": "disabled"}
    
    try:
        body = await request.json()
    except:
        logger.warning("Webhook recibido sin JSON válido")
        return {"status": "ok"}
    
    # INSTRUMENTACIÓN FORENSE
    event_kind, has_messages, has_statuses, msg_ids, status_ids, phone_from, wa_phone_number_id = _analyze_webhook_event(body)
    
    # FIX P0: NO procesar eventos que no son mensajes del usuario
    if has_statuses and not has_messages:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Webhook ignorado (solo statuses)",
            event_kind=event_kind,
            status_ids=status_ids[:3] if status_ids else [],
            elapsed_ms=round(elapsed_ms, 1),
            decision_path="ignore_status_event"
        )
        return {"status": "ok"}
    
    if not has_messages:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Webhook ignorado (sin messages)",
            event_kind=event_kind,
            elapsed_ms=round(elapsed_ms, 1),
            decision_path="no_messages_skip"
        )
        return {"status": "ok"}
    
    # Parsear mensaje
    parsed = parse_webhook_message(body)
    if not parsed:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Webhook ignorado (parse falló)",
            event_kind=event_kind,
            msg_ids=msg_ids[:3] if msg_ids else [],
            elapsed_ms=round(elapsed_ms, 1),
            decision_path="parse_failed_skip"
        )
        return {"status": "ok"}
    
    message_id = parsed.get("message_id", "")
    phone_from = parsed["phone_from"]
    text = parsed["text"]
    contact_name = parsed.get("contact_name")
    timestamp = parsed.get("timestamp", "")
    
    # IDEMPOTENCIA: Verificar si ya procesamos este message_id
    if message_id:
        if is_wa_message_processed(message_id):
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Mensaje WhatsApp duplicado (dedup)",
                message_id=message_id[:20] if message_id else "unknown",
                phone=phone_from[-4:],
                elapsed_ms=round(elapsed_ms, 1),
                decision_path="dedup_skip"
            )
            return {"status": "ok", "dedup": True}
    
    # Marcar como procesado ANTES de encolar (idempotencia)
    is_new = mark_wa_message_processed(message_id, phone_from, text[:50] if text else "")
    
    if not is_new and message_id:
        # Race condition: otro proceso ya lo procesó
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Mensaje WhatsApp duplicado (race condition)",
            message_id=message_id[:20] if message_id else "unknown",
            phone=phone_from[-4:],
            elapsed_ms=round(elapsed_ms, 1),
            decision_path="dedup_skip"
        )
        return {"status": "ok", "dedup": True}
    
    # Rate limit por número (ventana 60s)
    rate_key = f"wa:{phone_from}"
    if not rl_allow(rate_key, limit_per_minute=20):
        logger.warning(
            "Rate limit WhatsApp",
            phone=phone_from[-4:],
            remaining=rl_remaining(rate_key, 20),
            message_id=message_id[:20] if message_id else "unknown"
        )
        return Response(status_code=429, content=json.dumps({"status": "rate_limited"}), media_type="application/json")
    
    # ACK RÁPIDO: Encolar procesamiento en background
    background_tasks.add_task(
        _process_whatsapp_message,
        message_id=message_id,
        phone_from=phone_from,
        text=text,
        contact_name=contact_name,
        timestamp=timestamp
    )
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Mensaje WhatsApp recibido (queued)",
        event_kind=event_kind,
        message_id=message_id[:20] if message_id else "unknown",
        phone=phone_from[-4:] if phone_from else "unknown",
        text_length=len(text),
        elapsed_ms=round(elapsed_ms, 1),
        decision_path="queued_processing",
        msg_ids=msg_ids[:3] if msg_ids else []
    )
    
    return {"status": "ok", "queued": True}


def _analyze_webhook_event(body: dict) -> tuple:
    """
    Analiza el webhook para instrumentación forense.
    Returns: (event_kind, has_messages, has_statuses, msg_ids, status_ids, phone_from, wa_phone_number_id)
    """
    try:
        entry = body.get("entry", [])
        if not entry:
            return ("unknown", False, False, [], [], None, None)
        
        changes = entry[0].get("changes", [])
        if not changes:
            return ("unknown", False, False, [], [], None, None)
        
        value = changes[0].get("value", {})
        metadata = value.get("metadata", {})
        wa_phone_number_id = metadata.get("phone_number_id")
        
        messages = value.get("messages", [])
        statuses = value.get("statuses", [])
        
        has_messages = bool(messages)
        has_statuses = bool(statuses)
        
        if has_statuses and not has_messages:
            event_kind = "statuses"
        elif has_messages and not has_statuses:
            event_kind = "messages"
        elif has_messages and has_statuses:
            event_kind = "mixed"
        else:
            event_kind = "unknown"
        
        msg_ids = [msg.get("id", "")[:30] for msg in messages[:3] if msg.get("id")]
        status_ids = [st.get("id", "")[:30] for st in statuses[:3] if st.get("id")]
        
        phone_from = None
        if messages:
            phone_from = messages[0].get("from", "")
        
        return (event_kind, has_messages, has_statuses, msg_ids, status_ids, phone_from, wa_phone_number_id)
    except Exception as e:
        logger.error("Error analizando webhook event", error=str(e))
        return ("error", False, False, [], [], None, None)


async def _process_whatsapp_message(
    message_id: str,
    phone_from: str,
    text: str,
    contact_name: Optional[str],
    timestamp: str
):
    """
    Procesa un mensaje de WhatsApp en background.
    Esta función se ejecuta después de responder 200 OK al webhook.
    """
    try:
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
                conversation_id=conversation_id,
                message_id=message_id[:20] if message_id else "unknown"
            )
            return
        
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
                
                return
            
            # Obtener historial
            history = get_conversation_history(conversation_id)
            
            # Analizar intención
            intent_result = analyze_intent(text, history)
            tracer.intent = intent_result.get("intent")
            intent = tracer.intent or ""
            
            # Extraer contexto
            context = extract_context_from_history(history)
            
            # Obtener estado conversacional
            state = get_conversation_state(phone_from)
            
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
                
                # Actualizar estado
                state["handoff_needed"] = True
                state["last_intent"] = intent
                save_conversation_state(phone_from, state)
            
                # Marcar conversación como pendiente de humano
                # (pero NO silenciar inmediatamente, dar HANDOFF_COOLDOWN_MINUTES)
                
            else:
                # SALES DIALOGUE MANAGER: Generar respuesta comercial humana
                dialogue_result = next_action(
                    user_text=text,
                    intent=intent,
                    state=state,
                    history=history,
                    context=context
                )
                
                response_text = dialogue_result.get("reply_text", "")
                reply_assets = dialogue_result.get("reply_assets")
                state_updates = dialogue_result.get("state_updates", {})
                decision_path = dialogue_result.get("decision_path", "dialogue_handled")
                
                # Actualizar estado conversacional
                updated_state = {**state, **state_updates}
                updated_state["last_message_ts"] = timestamp
                updated_state["last_intent"] = intent
                save_conversation_state(phone_from, updated_state)
                
                # HUMANIZER: Opcionalmente humanizar la respuesta
                humanized_text, humanize_meta = humanize_response_sync(response_text, updated_state)
                if humanize_meta.get("humanized"):
                    response_text = humanized_text
                    tracer.decision_path = f"{decision_path}->humanized"
                else:
                    tracer.decision_path = decision_path
                
                # Si hay assets, prepararlos para envío (TODO: implementar envío de imágenes)
                if reply_assets:
                    logger.info(
                        "Assets seleccionados para respuesta",
                        asset_count=len(reply_assets),
                        asset_ids=[a.get("image_id") for a in reply_assets[:3]]
                    )
            
            tracer.response_text = response_text
            
            # Enviar respuesta
            success, _ = await send_whatsapp_message(phone_from, response_text)
            
            if success:
                save_message(conversation_id, response_text, "luisa")
                # Obtener stage actualizado para logging
                current_stage = state.get("stage", "unknown")
                if 'updated_state' in locals():
                    current_stage = updated_state.get("stage", current_stage)
                
                logger.info(
                    "Mensaje WhatsApp procesado y respondido",
                    message_id=message_id[:20] if message_id else "unknown",
                    phone=phone_from[-4:],
                    intent=tracer.intent,
                    stage=current_stage
                )
            else:
                tracer.error = "Error enviando respuesta"
                logger.error(
                    "Error enviando respuesta WhatsApp",
                    message_id=message_id[:20] if message_id else "unknown",
                    phone=phone_from[-4:]
                )
    except Exception as e:
        logger.error(
            "Error procesando mensaje WhatsApp en background",
            message_id=message_id[:20] if message_id else "unknown",
            phone=phone_from[-4:],
            error=str(e)
        )


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
