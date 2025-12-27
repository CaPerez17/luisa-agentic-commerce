"""
Servicio de extracción de contexto conversacional.
"""
from typing import List, Dict, Any, Optional

from app.rules.keywords import (
    normalize_text,
    contains_any,
    extract_match,
    MAQUINA_FAMILIAR,
    MAQUINA_INDUSTRIAL,
    USO_ROPA,
    USO_GORRAS,
    USO_CALZADO,
    USO_ACCESORIOS,
    USO_HOGAR,
    USO_UNIFORMES,
    USO_CUERO,
    VOLUMEN_ALTO,
    VOLUMEN_BAJO,
    CIUDADES_MAP,
    MARCAS_MODELOS,
    PROMOCIONES,
    ESPECIFICACIONES,
    FOTOS
)


def extract_context_from_history(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extrae contexto de la conversación para reducir opciones progresivamente.
    """
    context = {
        "tipo_maquina": None,
        "uso": None,
        "volumen": None,
        "presupuesto": None,
        "ciudad": None,
        "marca_interes": None,
        "modelo_interes": None,
        "ultimo_tema": None,
        "esperando_confirmacion": False,
        "ultimo_asset_mostrado": None,
        "etapa_funnel": "exploracion",
        "turnos_conversacion": 0,
        "productos_mencionados": [],
        "preguntas_respondidas": []
    }
    
    if not history:
        return context
    
    # Analizar últimos 12 mensajes
    recent_history = history[-12:] if len(history) > 12 else history
    context["turnos_conversacion"] = len(recent_history)
    
    full_text = " ".join([msg.get("text", "").lower() for msg in recent_history])
    recent_text = " ".join([msg.get("text", "").lower() for msg in recent_history[-6:]])
    
    # Detectar tipo de máquina
    if contains_any(recent_text, MAQUINA_INDUSTRIAL):
        context["tipo_maquina"] = "industrial"
    elif contains_any(recent_text, MAQUINA_FAMILIAR):
        context["tipo_maquina"] = "familiar"
    elif contains_any(full_text, MAQUINA_INDUSTRIAL):
        context["tipo_maquina"] = "industrial"
    elif contains_any(full_text, MAQUINA_FAMILIAR):
        context["tipo_maquina"] = "familiar"
    
    # Detectar uso específico
    usos_detectados = []
    uso_map = {
        "ropa": USO_ROPA,
        "gorras": USO_GORRAS,
        "calzado": USO_CALZADO,
        "accesorios": USO_ACCESORIOS,
        "hogar": USO_HOGAR,
        "uniformes": USO_UNIFORMES,
        "cuero": USO_CUERO
    }
    
    for uso_key, keywords in uso_map.items():
        if contains_any(full_text, keywords):
            usos_detectados.append(uso_key)
    
    if usos_detectados:
        context["uso"] = usos_detectados[-1]
        if len(usos_detectados) > 1:
            context["usos_multiples"] = usos_detectados
    
    # Detectar volumen
    if contains_any(full_text, VOLUMEN_BAJO):
        context["volumen"] = "bajo"
    elif contains_any(full_text, VOLUMEN_ALTO):
        context["volumen"] = "alto"
    
    # Inferir tipo industrial si volumen alto
    if context["volumen"] == "alto" and not context["tipo_maquina"]:
        context["tipo_maquina"] = "industrial"
    
    # Detectar ciudad
    for ciudad_key, ciudad_val in CIUDADES_MAP.items():
        if ciudad_key in full_text:
            context["ciudad"] = ciudad_val
            break
    
    # Detectar marca/modelo
    productos_encontrados = []
    for keyword, (marca, modelo) in MARCAS_MODELOS.items():
        if keyword in full_text:
            if not context["marca_interes"]:
                context["marca_interes"] = marca
                if modelo:
                    context["modelo_interes"] = modelo
            producto = f"{marca} {modelo}" if modelo else marca
            if producto not in productos_encontrados:
                productos_encontrados.append(producto)
    context["productos_mencionados"] = productos_encontrados
    
    # Detectar último tema de Luisa
    luisa_messages = [msg for msg in recent_history if msg.get("sender") == "luisa"]
    if luisa_messages:
        last_luisa = luisa_messages[-1].get("text", "").lower()
        context["ultimo_tema"] = _detect_luisa_topic(last_luisa)
        context["esperando_confirmacion"] = "?" in last_luisa
    
    # Detectar presupuesto
    presupuesto_keywords = ["1.2", "1.3", "1.4", "1.5", "millón", "millones", "presupuesto"]
    if any(kw in full_text for kw in presupuesto_keywords):
        context["presupuesto"] = True
    
    # Detectar información ya dada
    preguntas = []
    for msg in luisa_messages:
        msg_text = msg.get("text", "").lower()
        if "$" in msg_text or ".000" in msg_text:
            preguntas.append("precio")
        if contains_any(msg_text, ESPECIFICACIONES):
            preguntas.append("especificaciones")
        if "aquí" in msg_text and contains_any(msg_text, FOTOS):
            preguntas.append("imagen")
        if "envío" in msg_text or "envio" in msg_text:
            preguntas.append("envio")
    context["preguntas_respondidas"] = list(set(preguntas))
    
    # Determinar etapa del funnel
    if context["ciudad"] or ("precio" in preguntas and context["marca_interes"]):
        context["etapa_funnel"] = "cierre"
    elif context["marca_interes"] or context["modelo_interes"] or "precio" in preguntas:
        context["etapa_funnel"] = "decision"
    elif context["tipo_maquina"] and context["uso"]:
        context["etapa_funnel"] = "consideracion"
    
    return context


def _detect_luisa_topic(luisa_msg: str) -> Optional[str]:
    """Detecta el tema del último mensaje de Luisa."""
    luisa_lower = luisa_msg.lower()
    
    if contains_any(luisa_lower, PROMOCIONES) or "ofertas disponibles" in luisa_lower:
        return "promocion"
    if contains_any(luisa_lower, ESPECIFICACIONES):
        return "especificaciones"
    if contains_any(luisa_lower, FOTOS) or "imagen" in luisa_lower:
        return "fotos"
    if "familiar o industrial" in luisa_lower:
        return "diagnostico_tipo"
    if "qué vas a fabricar" in luisa_lower or "que vas a fabricar" in luisa_lower:
        return "diagnostico_uso"
    if "producción constante" in luisa_lower or "pocas unidades" in luisa_lower:
        return "diagnostico_volumen"
    if "qué ciudad" in luisa_lower or "que ciudad" in luisa_lower:
        return "diagnostico_ciudad"
    if "te llamemos" in luisa_lower or "agendar" in luisa_lower:
        return "cierre_handoff"
    
    return None


def is_ready_for_close(context: Dict[str, Any]) -> bool:
    """Detecta si la conversación está lista para cerrar."""
    if context.get("ciudad"):
        return True
    if (context.get("tipo_maquina") == "industrial" and 
        context.get("uso") and context.get("volumen")):
        return True
    if context.get("presupuesto") and context.get("uso"):
        return True
    return False


def format_context_for_prompt(context: Dict[str, Any]) -> str:
    """Formatea el contexto para incluir en el prompt de OpenAI."""
    lines = []
    
    if context.get("tipo_maquina"):
        lines.append(f"- Tipo de máquina: {context['tipo_maquina']}")
    if context.get("uso"):
        lines.append(f"- Uso: {context['uso']}")
    if context.get("volumen"):
        lines.append(f"- Volumen de producción: {context['volumen']}")
    if context.get("ciudad"):
        lines.append(f"- Ciudad: {context['ciudad']}")
    if context.get("marca_interes"):
        marca = context['marca_interes']
        if context.get("modelo_interes"):
            marca += f" {context['modelo_interes']}"
        lines.append(f"- Interesado en: {marca}")
    if context.get("etapa_funnel"):
        lines.append(f"- Etapa: {context['etapa_funnel']}")
    
    return "\n".join(lines) if lines else "Sin contexto previo"


def format_history_for_prompt(history: List[Dict[str, Any]], max_messages: int = 6) -> str:
    """Formatea el historial para incluir en el prompt de OpenAI."""
    recent = history[-max_messages:] if len(history) > max_messages else history
    
    lines = []
    for msg in recent:
        sender = "Cliente" if msg.get("sender") == "customer" else "Luisa"
        text = msg.get("text", "")[:150]  # Limitar longitud
        lines.append(f"{sender}: {text}")
    
    return "\n".join(lines) if lines else "Sin historial"

