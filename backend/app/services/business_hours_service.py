"""
Servicio para manejar horario de trabajo y cola de mensajes fuera de horario.

⚠️ ADVERTENCIA CRÍTICA: Este servicio es solo para uso temporal si NO hay otra opción
que usar un número personal como bot. 

🚨 RIESGOS DE USAR NÚMERO PERSONAL:
- El bot puede interrumpir conversaciones personales
- El bot puede tener acceso a información personal
- Puede causar confusión entre mensajes personales y del negocio
- NO hay separación personal/profesional

✅ SOLUCIÓN IDEAL: Obtener un número separado para LUISA bot (WhatsApp Business API)

Ver: docs/deployment/NUMERO_PERSONAL_VS_NUMERO_SEPARADO.md
"""
from typing import Tuple, Optional
from datetime import datetime, time, timezone, timedelta

from app.config import (
    BUSINESS_HOURS_START,
    BUSINESS_HOURS_END,
    BUSINESS_HOURS_NEW_CONVERSATION_CUTOFF,
    BUSINESS_HOURS_ENABLED
)
from app.logging_config import logger

# Colombia está en UTC-5 (no cambia por DST)
COLOMBIA_UTC_OFFSET = timedelta(hours=-5)


def _get_colombia_time(now: Optional[datetime] = None) -> datetime:
    """
    Convierte timestamp UTC a hora de Colombia (UTC-5).
    
    Args:
        now: Timestamp actual (si None, usa datetime.now())
    
    Returns:
        datetime en zona horaria de Colombia (UTC-5)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    
    # Convertir a UTC si no está en UTC
    now_utc = now.astimezone(timezone.utc)
    
    # Colombia está en UTC-5 (sin DST)
    colombia_time = now_utc + COLOMBIA_UTC_OFFSET
    
    return colombia_time


def is_within_business_hours(now: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Verifica si estamos dentro del horario de trabajo.
    
    Args:
        now: Timestamp actual (si None, usa datetime.now())
    
    Returns:
        Tuple[is_within_hours, reason]
        - is_within_hours: True si está en horario, False si no
        - reason: Razón (ej: "within_hours", "after_cutoff", "before_start", etc.)
    """
    if not BUSINESS_HOURS_ENABLED:
        return True, "business_hours_disabled"
    
    now_colombia = _get_colombia_time(now)
    current_hour = now_colombia.hour
    current_weekday = now_colombia.weekday()  # 0 = lunes, 6 = domingo
    
    # Domingos: cerrado
    if current_weekday == 6:  # Domingo
        return False, "sunday_closed"
    
    # Verificar horario
    if current_hour < BUSINESS_HOURS_START:
        return False, f"before_start_{current_hour}h"
    
    if current_hour >= BUSINESS_HOURS_END:
        return False, f"after_end_{current_hour}h"
    
    return True, "within_hours"


def can_start_new_conversation(now: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Verifica si podemos iniciar una nueva conversación.
    
    Después de BUSINESS_HOURS_NEW_CONVERSATION_CUTOFF, no se inician nuevas
    conversaciones, pero se pueden continuar las existentes.
    
    Args:
        now: Timestamp actual (si None, usa datetime.now())
    
    Returns:
        Tuple[can_start, reason]
    """
    if not BUSINESS_HOURS_ENABLED:
        return True, "business_hours_disabled"
    
    is_within, reason = is_within_business_hours(now)
    
    if not is_within:
        return False, reason
    
    now_colombia = _get_colombia_time(now)
    current_hour = now_colombia.hour
    
    if current_hour >= BUSINESS_HOURS_NEW_CONVERSATION_CUTOFF:
        return False, f"after_cutoff_{current_hour}h"
    
    return True, "can_start"


def get_out_of_hours_message() -> str:
    """Genera mensaje automático para fuera de horario."""
    return (
        "¡Hola! 😊\n\n"
        "Nuestro horario de atención es de 8am a 9pm, de lunes a sábado.\n\n"
        "Tu mensaje quedó registrado y te responderemos a primera hora. "
        "Si es urgente, puedes escribirnos después de las 8am.\n\n"
        "¡Gracias por contactarnos! 🙏"
    )
