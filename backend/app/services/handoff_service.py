"""
Servicio de handoff y notificaciones internas.
ÚNICA fuente de verdad para reglas de escalamiento.
"""
from typing import Tuple, Optional, List
from datetime import datetime
import json
from pathlib import Path

from app.config import (
    TEST_NOTIFY_NUMBER, 
    OUTBOX_DIR,
    HANDOFF_COOLDOWN_MINUTES
)
from app.models.database import (
    save_handoff, 
    save_notification,
    set_conversation_mode,
    get_conversation
)
from app.models.schemas import Team, Priority, HandoffDecision, InternalNotification
from app.rules.keywords import (
    normalize_text,
    contains_any,
    extract_match,
    IMPACTO_NEGOCIO,
    INSTALACION,
    VISITA,
    ASESORIA,
    CAPACITACION,
    CIUDADES_OTRAS,
    UBICACIONES_RURALES,
    CIUDADES_MONTERIA,
    PRECIO,
    FORMAS_PAGO,
    DISPONIBILIDAD,
    ENVIO,
    URGENTE,
    PROBLEMAS,
    REPARACION,
    REPUESTOS,
    GARANTIA,
    USO_ROPA,
    USO_GORRAS,
    USO_CALZADO
)
from app.logging_config import logger


def should_handoff(text: str, context: dict) -> HandoffDecision:
    """
    Determina si debe hacer handoff obligatorio según reglas de negocio.
    ÚNICA FUENTE DE VERDAD - NO duplicar esta lógica en otro lugar.
    
    Returns:
        HandoffDecision con should_handoff, team, reason, priority
    """
    text_lower = normalize_text(text)
    
    # 🔴 URGENTE - Problemas críticos
    if contains_any(text, URGENTE):
        return HandoffDecision(
            should_handoff=True,
            team=Team.TECNICA,
            reason="Cliente requiere atención inmediata",
            priority=Priority.URGENT
        )
    
    # 🔴 PROBLEMAS - Reclamos, devoluciones
    if contains_any(text, PROBLEMAS):
        return HandoffDecision(
            should_handoff=True,
            team=Team.COMERCIAL,
            reason="Cliente con problema o reclamo",
            priority=Priority.HIGH
        )
    
    # 🟡 IMPACTO DE NEGOCIO - Emprendimiento, taller
    if contains_any(text, IMPACTO_NEGOCIO):
        return HandoffDecision(
            should_handoff=True,
            team=Team.COMERCIAL,
            reason="Cliente requiere asesoría para proyecto de negocio",
            priority=Priority.HIGH
        )
    
    # 🟡 SERVICIO DIFERENCIAL - Instalación, visita, capacitación
    if contains_any(text, INSTALACION | VISITA | CAPACITACION):
        return HandoffDecision(
            should_handoff=True,
            team=Team.TECNICA,
            reason="Cliente requiere servicio diferencial (instalación/visita/capacitación)",
            priority=Priority.HIGH
        )
    
    # 🟡 GEOGRÁFICO - Ciudad fuera de Montería
    if contains_any(text, CIUDADES_OTRAS | UBICACIONES_RURALES):
        ciudad = extract_match(text, CIUDADES_OTRAS) or "ubicación remota"
        return HandoffDecision(
            should_handoff=True,
            team=Team.COMERCIAL,
            reason=f"Cliente requiere coordinación logística - {ciudad}",
            priority=Priority.HIGH
        )
    
    # 🟡 REPARACIÓN - Servicio técnico
    if contains_any(text, REPARACION):
        return HandoffDecision(
            should_handoff=True,
            team=Team.TECNICA,
            reason="Cliente necesita servicio de reparación",
            priority=Priority.MEDIUM
        )
    
    # 🟢 DECISIÓN DE COMPRA - Precio, pago, disponibilidad
    # Solo si hay intención clara de compra
    tiene_precio = contains_any(text, PRECIO)
    tiene_pago = contains_any(text, FORMAS_PAGO)
    tiene_disponibilidad = contains_any(text, DISPONIBILIDAD)
    tiene_envio = contains_any(text, ENVIO)
    
    # Si tiene ciudad en contexto Y pregunta de precio/pago = momento de cierre
    if context.get("ciudad") and (tiene_precio or tiene_pago):
        return HandoffDecision(
            should_handoff=True,
            team=Team.COMERCIAL,
            reason="Cliente en etapa de cierre de venta",
            priority=Priority.HIGH
        )
    
    # 🔵 AMBIGÜEDAD CRÍTICA - Múltiples necesidades
    needs_detected = []
    if contains_any(text, USO_ROPA):
        needs_detected.append("ropa")
    if contains_any(text, USO_GORRAS):
        needs_detected.append("gorras")
    if contains_any(text, USO_CALZADO):
        needs_detected.append("calzado")
    
    if len(needs_detected) >= 2 and context.get("volumen") == "alto":
        return HandoffDecision(
            should_handoff=True,
            team=Team.COMERCIAL,
            reason=f"Cliente con múltiples necesidades ({', '.join(needs_detected)}) + producción constante",
            priority=Priority.MEDIUM
        )
    
    # No requiere handoff
    return HandoffDecision(
        should_handoff=False,
        team=None,
        reason="",
        priority=Priority.LOW
    )


def route_case(intent: str, context: dict, text: str) -> Tuple[Optional[Team], str, Priority]:
    """
    Enruta un caso al equipo apropiado.
    
    Returns:
        Tuple[team, motivo_simple, prioridad]
    """
    decision = should_handoff(text, context)
    return decision.team, decision.reason, decision.priority


def build_internal_notification(
    team: Team,
    customer_phone: str,
    customer_name: Optional[str],
    summary_bullets: List[str],
    next_step: str
) -> str:
    """
    Construye el texto de notificación interna en ESPAÑOL.
    Sin anglicismos.
    """
    if team == Team.COMERCIAL:
        header = "💰 ATENCIÓN COMERCIAL"
    else:
        header = "⚙️ ATENCIÓN TÉCNICA"
    
    # Formatear número
    phone_display = customer_phone if customer_phone.startswith("+") else f"+{customer_phone}"
    
    # Construir mensaje
    lines = [header, ""]
    
    if customer_name:
        lines.append(f"Cliente: {customer_name}")
    lines.append(f"Número: {phone_display}")
    lines.append("")
    
    lines.append("Resumen del caso:")
    for bullet in summary_bullets[:5]:  # Máximo 5 bullets
        lines.append(f"• {bullet}")
    lines.append("")
    
    lines.append("Siguiente paso recomendado:")
    lines.append(next_step)
    
    return "\n".join(lines)


def create_summary_bullets(text: str, context: dict, history: List[dict] = None) -> List[str]:
    """Crea bullets de resumen del caso."""
    bullets = []
    
    # Último mensaje del cliente
    if text:
        bullets.append(f"Último mensaje: \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
    
    # Tipo de máquina
    if context.get("tipo_maquina"):
        tipo = "industrial" if context["tipo_maquina"] == "industrial" else "familiar"
        bullets.append(f"Busca máquina {tipo}")
    
    # Uso específico
    if context.get("uso"):
        bullets.append(f"Para fabricar: {context['uso']}")
    
    # Ciudad
    if context.get("ciudad"):
        bullets.append(f"Ubicación: {context['ciudad'].title()}")
    
    # Marca de interés
    if context.get("marca_interes"):
        bullets.append(f"Interesado en: {context['marca_interes']}")
    
    # Etapa del funnel
    etapa = context.get("etapa_funnel", "exploracion")
    etapa_display = {
        "exploracion": "Explorando opciones",
        "consideracion": "Considerando opciones",
        "decision": "Listo para decidir",
        "cierre": "Listo para cerrar"
    }.get(etapa, etapa)
    bullets.append(f"Etapa: {etapa_display}")
    
    return bullets


def get_next_step_suggestion(team: Team, context: dict) -> str:
    """Sugiere el siguiente paso según el equipo y contexto."""
    if team == Team.COMERCIAL:
        if context.get("ciudad"):
            return f"Coordinar envío e instalación a {context['ciudad'].title()}"
        elif context.get("etapa_funnel") == "cierre":
            return "Cerrar venta: confirmar producto, forma de pago y entrega"
        else:
            return "Contactar para asesorar sobre la mejor opción según su proyecto"
    else:  # TECNICA
        if contains_any(context.get("ultimo_mensaje", ""), REPARACION):
            return "Coordinar diagnóstico de la máquina"
        elif contains_any(context.get("ultimo_mensaje", ""), INSTALACION):
            return "Agendar visita de instalación y capacitación"
        else:
            return "Resolver consulta técnica y ofrecer servicio"


def process_handoff(
    conversation_id: str,
    text: str,
    context: dict,
    customer_phone: str,
    customer_name: Optional[str] = None,
    history: List[dict] = None
) -> Tuple[bool, Optional[str], Optional[Team]]:
    """
    Procesa un handoff completo: evalúa, notifica, persiste.
    
    Returns:
        Tuple[handoff_triggered, notification_text, team]
    """
    decision = should_handoff(text, context)
    
    if not decision.should_handoff:
        return False, None, None
    
    team = decision.team
    
    # Crear resumen
    context["ultimo_mensaje"] = text
    summary_bullets = create_summary_bullets(text, context, history)
    next_step = get_next_step_suggestion(team, context)
    
    # Construir notificación
    notification_text = build_internal_notification(
        team=team,
        customer_phone=customer_phone,
        customer_name=customer_name,
        summary_bullets=summary_bullets,
        next_step=next_step
    )
    
    # Guardar handoff en DB
    summary = "\n".join([f"• {b}" for b in summary_bullets])
    save_handoff(
        conversation_id=conversation_id,
        reason=decision.reason,
        priority=decision.priority.value,
        summary=summary,
        suggested_response=next_step,
        customer_name=customer_name,
        routed_team=team.value if team else None
    )
    
    # Guardar notificación en DB
    notification_id = save_notification(
        conversation_id=conversation_id,
        team=team.value if team else "comercial",
        notification_text=notification_text,
        destination_number=TEST_NOTIFY_NUMBER
    )
    
    # Guardar en outbox (JSON para debug/integración)
    _save_to_outbox(conversation_id, decision, notification_text)
    
    # Activar modo humano para silenciar respuestas automáticas
    set_conversation_mode(conversation_id, "HUMAN_ACTIVE")

    # Log
    logger.info(
        "Handoff procesado",
        conversation_id=conversation_id,
        team=team.value if team else None,
        priority=decision.priority.value,
        reason=decision.reason
    )
    
    # Imprimir notificación para demo
    print("\n" + "=" * 60)
    print("📱 NOTIFICACIÓN INTERNA")
    print("=" * 60)
    print(notification_text)
    print("=" * 60 + "\n")
    
    return True, notification_text, team


def _save_to_outbox(conversation_id: str, decision: HandoffDecision, notification_text: str):
    """Guarda handoff en outbox como JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"handoff_{conversation_id}_{timestamp}.json"
    filepath = OUTBOX_DIR / filename
    
    data = {
        "conversation_id": conversation_id,
        "team": decision.team.value if decision.team else None,
        "reason": decision.reason,
        "priority": decision.priority.value,
        "notification_text": notification_text,
        "timestamp": datetime.now().isoformat(),
        "destination": TEST_NOTIFY_NUMBER
    }
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Error guardando en outbox", error=str(e))


def generate_handoff_message(text: str, reason: str, priority: str, ciudad: Optional[str] = None) -> str:
    """
    Genera mensaje de handoff para el cliente.
    """
    text_lower = normalize_text(text)
    
    # Detectar si está en Montería
    esta_en_monteria = contains_any(text, CIUDADES_MONTERIA) or (ciudad and ciudad.lower() in ["montería", "monteria"])
    
    # Handoff por impacto de negocio o servicio diferencial
    if any(kw in reason.lower() for kw in ["proyecto de negocio", "servicio diferencial", "asesoría", "instalación"]):
        if esta_en_monteria:
            return (
                "En este punto lo mejor es que uno de nuestros asesores te acompañe "
                "directamente para elegir la mejor opción según tu proyecto.\n\n"
                "¿Prefieres que te llamemos para agendar una cita con el asesor "
                "o agendamos una visita del equipo a tu taller?"
            )
        else:
            return (
                "En este punto lo mejor es que uno de nuestros asesores te acompañe "
                "directamente para elegir la mejor opción según tu proyecto.\n\n"
                "¿Prefieres que te llamemos para agendar una cita con el asesor?"
            )
    
    # Handoff geográfico
    if "coordinación logística" in reason.lower() or "ubicación" in reason.lower():
        return (
            "Para coordinar el envío e instalación a tu ubicación, "
            "lo mejor es que uno de nuestros asesores te contacte directamente.\n\n"
            "¿Prefieres que te llamemos para agendar la entrega e instalación?"
            )
    
    # Handoff por decisión de compra
    if "cierre" in reason.lower() or "compra" in reason.lower():
        if esta_en_monteria:
            return (
                "Para coordinar el pago y la entrega, lo mejor es que "
                "uno de nuestros asesores te acompañe.\n\n"
                "¿Prefieres que te llamemos para agendar la entrega "
                "o prefieres pasar por el almacén?"
            )
        else:
            return (
                "Para coordinar el pago y el envío, lo mejor es que "
                "uno de nuestros asesores te contacte directamente.\n\n"
                "¿Prefieres que te llamemos para agendar el envío?"
            )
    
    # Handoff urgente
    if priority == "urgent":
        return (
            "Esto requiere atención inmediata. "
            "Estoy conectándote con nuestro equipo especializado.\n\n"
            "¿Prefieres que te llamemos ahora mismo?"
        )
    
    # Handoff genérico
    if priority == "high":
        return (
            "En este punto lo mejor es que uno de nuestros asesores "
            "te acompañe directamente.\n\n"
            "¿Prefieres que te llamemos para agendar una cita?"
        )

    return "Perfecto, lo estoy revisando con nuestro equipo y te respondo en breve."
