"""
Servicio de integración con WhatsApp Cloud API.
"""
import httpx
from typing import Optional, Dict, Any, Tuple
import json
import asyncio

from app.config import (
    WHATSAPP_ENABLED,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_API_VERSION,
    TEST_NOTIFY_NUMBER
)
from app.models.database import check_outbox_dedup
from app.logging_config import logger


# URL base de la API de WhatsApp
WHATSAPP_API_BASE = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"


async def send_whatsapp_message(
    to: str,
    text: str,
    retry_count: int = 2
) -> Tuple[bool, Optional[str]]:
    """
    Envía un mensaje de WhatsApp.
    
    Args:
        to: Número de destino (con código de país, ej: +573142156486)
        text: Texto del mensaje
        retry_count: Número de reintentos en caso de fallo
    
    Returns:
        Tuple[success, message_id o error]
    """
    if not WHATSAPP_ENABLED:
        logger.warning("WhatsApp deshabilitado, mensaje no enviado", to=_mask_phone(to))
        return False, "WhatsApp deshabilitado"
    
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WhatsApp no configurado correctamente")
        return False, "Configuración incompleta"
    
    # Limpiar número
    phone = to.replace("+", "").replace(" ", "").replace("-", "")
    
    # ANTI-SPAM GUARD: Verificar deduplicación de outbox
    if check_outbox_dedup(phone, text, ttl_seconds=120):
        logger.info(
            "Mensaje WhatsApp bloqueado (outbox dedup)",
            to=_mask_phone(phone),
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
    
    masked_phone = _mask_phone(phone)

    for attempt in range(retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    message_id = data.get("messages", [{}])[0].get("id")
                    logger.info(
                        "Mensaje WhatsApp enviado",
                        to=masked_phone,
                        message_id=message_id
                    )
                    return True, message_id
                else:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                    logger.warning(
                        "Error enviando WhatsApp",
                        to=masked_phone,
                        status_code=response.status_code,
                        error=error_msg,
                        attempt=attempt + 1
                    )
                    
                    # No reintentar en errores de validación
                    if response.status_code in [400, 401, 403]:
                        return False, error_msg
                
        except httpx.TimeoutException:
            logger.warning("Timeout enviando WhatsApp", to=masked_phone, attempt=attempt + 1)
        except Exception as e:
            logger.error("Error inesperado enviando WhatsApp", error=str(e), attempt=attempt + 1)
        
        # Esperar antes de reintentar
        if attempt < retry_count:
            await asyncio.sleep(1 * (attempt + 1))
    
    return False, "Máximo de reintentos alcanzado"


async def send_internal_notification(notification_text: str) -> Tuple[bool, Optional[str]]:
    """
    Envía una notificación interna al número de prueba.
    """
    return await send_whatsapp_message(TEST_NOTIFY_NUMBER, notification_text)


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
