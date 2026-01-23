"""
Servicio de integración con WhatsApp Cloud API.
"""
import httpx
from typing import Optional, Dict, Any, Tuple
import json
import asyncio
import time

from app.config import (
    WHATSAPP_ENABLED,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_API_VERSION,
    LUISA_HUMAN_NOTIFY_NUMBER,
    TECNICO_NOTIFY_NUMBER
)
from app.models.schemas import Team
from app.models.database import check_outbox_dedup
from app.logging_config import logger


# URL base de la API de WhatsApp
WHATSAPP_API_BASE = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"


async def send_whatsapp_message(
    to: str,
    text: str,
    retry_count: int = 2,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Envía un mensaje de WhatsApp.
    
    Args:
        to: Número de destino (con código de país, ej: +573142156486)
        text: Texto del mensaje
        retry_count: Número de reintentos en caso de fallo
        conversation_id: ID de conversación (opcional, para logging)
        message_id: ID del mensaje original (opcional, para logging)
    
    Returns:
        Tuple[success, message_id o error]
    """
    start_time = time.perf_counter()
    masked_phone = _mask_phone(to)
    error_code = None
    final_message_id = None
    
    try:
        if not WHATSAPP_ENABLED:
            error_code = "whatsapp_disabled"
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.error(
                "whatsapp_send_failed",
                conversation_id=conversation_id or "unknown",
                message_id=message_id or "unknown",
                to=masked_phone,
                error_code=error_code,
                latency_ms=latency_ms,
                error="WhatsApp deshabilitado"
            )
            return False, "WhatsApp deshabilitado"
        
        if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            error_code = "config_incomplete"
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.error(
                "whatsapp_send_failed",
                conversation_id=conversation_id or "unknown",
                message_id=message_id or "unknown",
                to=masked_phone,
                error_code=error_code,
                latency_ms=latency_ms,
                error="Configuración incompleta"
            )
            return False, "Configuración incompleta"
        
        # Limpiar número
        phone = to.replace("+", "").replace(" ", "").replace("-", "")
        
        # ANTI-SPAM GUARD: Verificar deduplicación de outbox
        if check_outbox_dedup(phone, text, ttl_seconds=120):
            error_code = "outbox_dedup"
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.info(
                "whatsapp_send_failed",
                conversation_id=conversation_id or "unknown",
                message_id=message_id or "unknown",
                to=masked_phone,
                error_code=error_code,
                latency_ms=latency_ms,
                text_preview=text[:50],
                decision_path="outgoing_dedup_skip"
            )
            return False, "Mensaje duplicado reciente (anti-spam)"
        
        url = f"{WHATSAPP_API_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }

        for attempt in range(retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        final_message_id = data.get("messages", [{}])[0].get("id")
                        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                        logger.info(
                            "whatsapp_send_success",
                            conversation_id=conversation_id or "unknown",
                            message_id=final_message_id or "unknown",
                            to=masked_phone,
                            latency_ms=latency_ms
                        )
                        return True, final_message_id
                    else:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                        error_code = f"http_{response.status_code}"
                        
                        # No reintentar en errores de validación
                        if response.status_code in [400, 401, 403]:
                            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                            logger.error(
                                "whatsapp_send_failed",
                                conversation_id=conversation_id or "unknown",
                                message_id=message_id or "unknown",
                                to=masked_phone,
                                error_code=error_code,
                                latency_ms=latency_ms,
                                error=error_msg,
                                attempt=attempt + 1
                            )
                            return False, error_msg
                    
            except httpx.TimeoutException:
                error_code = "timeout"
                if attempt == retry_count:
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                    logger.error(
                        "whatsapp_send_failed",
                        conversation_id=conversation_id or "unknown",
                        message_id=message_id or "unknown",
                        to=masked_phone,
                        error_code=error_code,
                        latency_ms=latency_ms,
                        attempt=attempt + 1
                    )
            except Exception as e:
                error_code = "exception"
                if attempt == retry_count:
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                    logger.error(
                        "whatsapp_send_failed",
                        conversation_id=conversation_id or "unknown",
                        message_id=message_id or "unknown",
                        to=masked_phone,
                        error_code=error_code,
                        latency_ms=latency_ms,
                        error=str(e),
                        attempt=attempt + 1
                    )
            
            # Esperar antes de reintentar
            if attempt < retry_count:
                await asyncio.sleep(1 * (attempt + 1))
        
        # Máximo de reintentos alcanzado
        error_code = "max_retries"
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        logger.error(
            "whatsapp_send_failed",
            conversation_id=conversation_id or "unknown",
            message_id=message_id or "unknown",
            to=masked_phone,
            error_code=error_code,
            latency_ms=latency_ms,
            error="Máximo de reintentos alcanzado"
        )
        return False, "Máximo de reintentos alcanzado"
    
    except Exception as e:
        # Catch-all para cualquier error no esperado
        error_code = "unexpected_error"
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        logger.error(
            "whatsapp_send_failed",
            conversation_id=conversation_id or "unknown",
            message_id=message_id or "unknown",
            to=masked_phone,
            error_code=error_code,
            latency_ms=latency_ms,
            error=str(e)
        )
        return False, str(e)


async def send_internal_notification(notification_text: str, team: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Envía una notificación interna según el equipo.
    
    Args:
        notification_text: Texto de la notificación
        team: "comercial" → LUISA humana, "tecnica" → Técnico, None → LUISA humana (default)
    
    El bot solo puede enviar notificaciones unidireccionales (no conversaciones).
    """
    if team == "tecnica" and TECNICO_NOTIFY_NUMBER:
        destination = TECNICO_NOTIFY_NUMBER
    else:
        destination = LUISA_HUMAN_NOTIFY_NUMBER
    
    return await send_whatsapp_message(destination, notification_text)


def parse_webhook_message(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parsea el cuerpo de un webhook de WhatsApp y extrae el mensaje.
    
    Returns:
        Dict con phone_from, text, message_id o None si no es un mensaje válido
    """
    try:
        entry = body.get("entry", [])
        if not entry:
            return None
        
        changes = entry[0].get("changes", [])
        if not changes:
            return None
        
        value = changes[0].get("value", {})
        
        # Verificar que hay mensajes
        messages = value.get("messages", [])
        if not messages:
            return None
        
        message = messages[0]
        
        # Solo procesar mensajes de texto por ahora
        if message.get("type") != "text":
            logger.info("Mensaje no es de texto, ignorando", type=message.get("type"))
            return None
        
        # Extraer datos
        phone_from = message.get("from", "")
        text = message.get("text", {}).get("body", "")
        message_id = message.get("id", "")
        timestamp = message.get("timestamp", "")
        
        # Obtener nombre del contacto si está disponible
        contacts = value.get("contacts", [])
        contact_name = None
        if contacts:
            contact_name = contacts[0].get("profile", {}).get("name")
        
        return {
            "phone_from": phone_from,
            "text": text,
            "message_id": message_id,
            "timestamp": timestamp,
            "contact_name": contact_name
        }
        
    except Exception as e:
        logger.error("Error parseando webhook WhatsApp", error=str(e))
        return None


def is_status_update(body: Dict[str, Any]) -> bool:
    """
    Verifica si el webhook es una actualización de estado (no un mensaje).
    """
    try:
        entry = body.get("entry", [])
        if not entry:
            return False
        
        changes = entry[0].get("changes", [])
        if not changes:
            return False
        
        value = changes[0].get("value", {})
        
        # Si tiene "statuses" y NO tiene "messages", es actualización de estado
        has_statuses = "statuses" in value and bool(value.get("statuses"))
        has_messages = "messages" in value and bool(value.get("messages"))
        
        return has_statuses and not has_messages
    except:
        return False


def analyze_webhook_event(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analiza el webhook para instrumentación forense.
    Compatible con la función en routers/whatsapp.py
    """
    try:
        entry = body.get("entry", [])
        if not entry:
            return {"event_kind": "unknown", "has_messages": False, "has_statuses": False}
        
        changes = entry[0].get("changes", [])
        if not changes:
            return {"event_kind": "unknown", "has_messages": False, "has_statuses": False}
        
        value = changes[0].get("value", {})
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
        
        return {
            "event_kind": event_kind,
            "has_messages": has_messages,
            "has_statuses": has_statuses
        }
    except:
        return {"event_kind": "error", "has_messages": False, "has_statuses": False}


def get_phone_conversation_id(phone: str) -> str:
    """
    Genera un ID de conversación a partir del número de teléfono.
    """
    # Limpiar número
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    return f"wa_{phone_clean}"


def _mask_phone(phone: str) -> str:
    """Enmascara número dejando últimos 4 dígitos."""
    digits = phone.replace("+", "").replace(" ", "").replace("-", "")
    if len(digits) <= 4:
        return "***" + digits
    return "***" + digits[-4:]


def format_phone_display(phone: str) -> str:
    """
    Formatea un número de teléfono para mostrar.
    """
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    if len(phone_clean) == 10:
        # Colombiano sin código de país
        return f"+57 {phone_clean[:3]} {phone_clean[3:6]} {phone_clean[6:]}"
    elif len(phone_clean) == 12 and phone_clean.startswith("57"):
        # Colombiano con código de país
        return f"+{phone_clean[:2]} {phone_clean[2:5]} {phone_clean[5:8]} {phone_clean[8:]}"
    else:
        return f"+{phone_clean}"
