"""
Sales Playbook: Copywriting y micro-empathía para LUISA.
Convierte respuestas rígidas en asesoría comercial natural.
"""
from typing import Dict, Any, Optional, Tuple
import re

from app.logging_config import logger


def craft_reply(intent: str, state: dict, user_text: str, context: dict = None) -> Dict[str, Any]:
    """
    Genera respuesta comercial usando playbook de ventas.
    
    Args:
        intent: Intención detectada
        state: Estado conversacional
        user_text: Texto del usuario
        context: Contexto adicional (opcional)
    
    Returns:
        {
            "reply_text": str,
            "stage_update": str o None,
            "slot_updates": dict,
            "decision_path": str
        }
    """
    text_lower = user_text.lower().strip()
    slots = state.get("slots", {})
    stage = state.get("stage", "discovery")
    
    # Routing por intent
    if intent == "buy_machine" or "comprar" in text_lower or "máquina" in text_lower or "maquina" in text_lower:
        return _handle_buy_machine(intent, state, user_text, text_lower, slots, context)
    elif intent == "spare_parts" or "repuesto" in text_lower:
        return _handle_spare_parts(intent, state, user_text, text_lower, slots)
    elif intent == "tech_support" or "garantía" in text_lower or "garantia" in text_lower:
        return _handle_tech_support(intent, state, user_text, text_lower, slots)
    elif intent == "business_advice" or "emprender" in text_lower or "montar negocio" in text_lower:
        return _handle_business_advice(intent, state, user_text, text_lower, slots, context)
    elif intent == "faq_hours_location" or "horario" in text_lower or "dirección" in text_lower or "direccion" in text_lower:
        return _handle_faq_hours_location(intent, state, user_text, text_lower, slots)
    elif intent == "sell_machine" or "vendo" in text_lower or "vender" in text_lower:
        return _handle_sell_machine(intent, state, user_text, text_lower, slots)
    else:
        return _handle_default(intent, state, user_text, text_lower, slots)


def _handle_buy_machine(intent: str, state: dict, user_text: str, text_lower: str, slots: dict, context: dict = None) -> Dict[str, Any]:
    """Maneja compra de máquina con playbook de ventas."""
    product_type = slots.get("product_type")
    use_case = slots.get("use_case")
    qty = slots.get("qty")
    budget = slots.get("budget")
    visit_or_delivery = slots.get("visit_or_delivery")
    
    # Caso 1: Usuario pide precio directo
    if "precio" in text_lower or "cuánto" in text_lower or "cuanto" in text_lower or "cuesta" in text_lower:
        if product_type == "industrial":
            reply = (
                "Listo 🙌 En promoción están:\n\n"
                "• KINGTER KT-D3: $1.230.000\n"
                "• KANSEW KS-8800: $1.300.000\n\n"
                "Ambas incluyen mesa, motor ahorrador e instalación."
            )
            # Pregunta de calificación (NO interrogatorio)
            if not use_case:
                reply += "\n\n¿La necesitas para producción constante o pocas unidades?"
                question = "use_case"
            elif not qty:
                reply += "\n\n¿Cuántas unidades al mes aprox?"
                question = "qty"
            else:
                reply += "\n\n¿Te separo una o quieres ver fotos primero?"
                question = "decision"
        else:
            reply = (
                "Los precios varían según el tipo:\n\n"
                "• Familiares: desde $400.000\n"
                "• Industriales: desde $1.230.000\n\n"
            )
            if not product_type:
                reply += "¿Buscas para casa o para producción?"
                question = "product_type"
            else:
                reply += "¿Te separo una o quieres ver fotos primero?"
                question = "decision"
        
        return {
            "reply_text": reply,
            "stage_update": "pricing",
            "slot_updates": {"last_question": question},
            "decision_path": "buy_machine_price"
        }
    
    # Caso 2: Usuario dice uso pero no volumen
    if use_case and not qty:
        # Detectar si menciona cantidad en el mensaje
        qty_match = re.search(r'(\d+)\s*(unidades|piezas|pares|máquinas|maquinas|gorras|prendas)', text_lower)
        if qty_match:
            qty = qty_match.group(1)
            slots["qty"] = qty
        else:
            reply = f"Perfecto, para {use_case}. ¿Cuántas al mes aprox?"
            return {
                "reply_text": reply,
                "stage_update": "pricing",
                "slot_updates": {"last_question": "qty"},
                "decision_path": "buy_machine_ask_qty"
            }
    
    # Caso 3: Usuario dice volumen -> recomendar 1-2 opciones con por qué + CTA
    if qty:
        qty_int = int(qty) if qty.isdigit() else 0
        
        if product_type == "industrial":
            if use_case == "gorras":
                if qty_int <= 30:
                    reply = (
                        f"Para {qty} gorras ocasional, KT-D3 te va bien; "
                        f"si piensas escalar, KS-8800 te dura más. "
                        f"¿Cuál te suena más: ahorrar hoy o pensar en crecimiento?"
                    )
                else:
                    reply = (
                        f"Para {qty} gorras al mes, KS-8800 es la mejor opción (más robusta). "
                        f"¿Te separo una o prefieres verla primero?"
                    )
            elif use_case == "ropa":
                reply = (
                    f"Para ropa, ambas funcionan bien. "
                    f"KT-D3 es más económica; KS-8800 aguanta más tela gruesa. "
                    f"¿Qué tipo de prendas: camisas, pantalones o ambas?"
                )
            else:
                reply = (
                    f"Para {use_case}, te recomiendo KS-8800 (más versátil). "
                    f"¿Te separo una o quieres ver fotos?"
                )
        else:
            reply = (
                f"Para casa, una familiar básica ($400.000) o intermedia ($600.000). "
                f"¿Qué tipo de costura haces: arreglos o proyectos?"
            )
        
        # CTA según contexto
        if visit_or_delivery == "visit":
            reply += "\n\n¿Te queda mejor venir hoy o mañana?"
            question = "visit_when"
        elif visit_or_delivery == "delivery":
            if not slots.get("city_filled"):
                reply += "\n\n¿En qué ciudad te encuentras para coordinar el envío?"
                question = "city"
            else:
                reply += f"\n\n¿Te separo una para envío a {slots.get('city')}?"
                question = "confirm"
        else:
            reply += "\n\n¿Te separo una o quieres ver fotos primero?"
            question = "decision"
        
        return {
            "reply_text": reply,
            "stage_update": "photos",
            "slot_updates": {"last_question": question},
            "decision_path": "buy_machine_recommendation"
        }
    
    # Default: preguntar siguiente dato clave
    if not product_type:
        reply = "¿Buscas máquina familiar (para casa) o industrial (para producción)?"
        question = "product_type"
    elif not use_case:
        reply = "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        question = "use_case"
    else:
        reply = "¿Cuántas unidades al mes aprox?"
        question = "qty"
    
    return {
        "reply_text": reply,
        "stage_update": "discovery",
        "slot_updates": {"last_question": question},
        "decision_path": "buy_machine_discovery"
    }


def _handle_spare_parts(intent: str, state: dict, user_text: str, text_lower: str, slots: dict) -> Dict[str, Any]:
    """Maneja repuestos con empatía."""
    reply = (
        "Sí, tenemos repuestos para las marcas que vendemos. "
        "De una, así te lo doy exacto. "
        "¿Me confirmas la marca o me envías foto de la placa?"
    )
    
    return {
        "reply_text": reply,
        "stage_update": "support",
        "slot_updates": {"last_question": "spare_parts_marca"},
        "decision_path": "spare_parts_handled"
    }


def _handle_tech_support(intent: str, state: dict, user_text: str, text_lower: str, slots: dict) -> Dict[str, Any]:
    """Maneja soporte técnico/garantía."""
    if "garantía" in text_lower or "garantia" in text_lower:
        reply = (
            "Todas nuestras máquinas tienen garantía de 3 meses en partes y mano de obra. "
            "Si algo falla, la revisamos sin costo. "
            "¿Qué máquina tienes o estás pensando comprar?"
        )
    else:
        # Soporte técnico
        reply = (
            "Te puedo ayudar. Para darte la mejor solución: "
            "¿Qué síntoma tiene (no prende, ruido, etc.)? "
            "¿Marca/modelo? "
            "¿La compraste aquí o en otro lado?"
        )
    
    return {
        "reply_text": reply,
        "stage_update": "support",
        "slot_updates": {"last_question": "tech_support_info"},
        "decision_path": "tech_support_handled"
    }


def _handle_business_advice(intent: str, state: dict, user_text: str, text_lower: str, slots: dict, context: dict = None) -> Dict[str, Any]:
    """Maneja asesoría para montar negocio."""
    use_case = slots.get("use_case") or (context.get("uso") if context else None)
    budget = slots.get("budget")
    qty = slots.get("qty")
    
    # Detectar tipo de producto mencionado
    if "gorra" in text_lower:
        use_case = "gorras"
    elif "ropa" in text_lower:
        use_case = "ropa"
    
    # Si ya tiene datos clave, dar mini plan
    if use_case:
        if use_case == "gorras":
            reply = (
                "Para empezar con gorras: recta industrial + insumos (agujas/hilo). "
                "Luego fileteadora si escalas. "
            )
        elif use_case == "ropa":
            reply = (
                "Para empezar con ropa: recta industrial + fileteadora (para orillos). "
                "Luego overlock si haces prendas completas. "
            )
        else:
            reply = (
                f"Para empezar con {use_case}: recta industrial básica. "
                "Luego agregas según crezcas. "
            )
        
        # Pregunta siguiente
        if not budget:
            reply += "¿Presupuesto aproximado?"
            question = "budget"
        elif not qty:
            reply += "¿Cuántas unidades al mes planeas?"
            question = "qty"
        else:
            reply += "¿Te separo una o quieres ver opciones?"
            question = "decision"
    else:
        # Preguntar 1 cosa clave
        if not budget:
            reply = "¿Presupuesto aproximado para empezar?"
            question = "budget"
        elif not qty:
            reply = "¿Cuántas unidades al mes planeas?"
            question = "qty"
        else:
            reply = "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
            question = "use_case"
    
    return {
        "reply_text": reply,
        "stage_update": "discovery",
        "slot_updates": {"last_question": question, "use_case": use_case} if use_case else {"last_question": question},
        "decision_path": "business_advice_handled"
    }


def _handle_faq_hours_location(intent: str, state: dict, user_text: str, text_lower: str, slots: dict) -> Dict[str, Any]:
    """Maneja FAQ de horarios/ubicación."""
    if "horario" in text_lower or "hora" in text_lower:
        reply = (
            "Estamos en Calle 34 #1-30, Montería.\n\n"
            "🕘 Lunes a viernes: 9am-6pm\n"
            "🕘 Sábados: 9am-2pm\n\n"
        )
    else:
        reply = (
            "Estamos en Calle 34 #1-30, Montería.\n\n"
            "🕘 Lunes a viernes: 9am-6pm\n"
            "🕘 Sábados: 9am-2pm\n\n"
        )
    
    # Cerrar con día/hora (visit) o envío
    if "visitar" in text_lower or "pasar" in text_lower or "visita" in text_lower:
        reply += "¿Te queda mejor venir hoy o mañana?"
        question = "visit_when"
        stage = "visit"
    else:
        reply += "¿Quieres pasar o prefieres envío a domicilio?"
        question = "visit_or_delivery"
        stage = "visit"
    
    return {
        "reply_text": reply,
        "stage_update": stage,
        "slot_updates": {"last_question": question},
        "decision_path": "faq_hours_location_handled"
    }


def _handle_sell_machine(intent: str, state: dict, user_text: str, text_lower: str, slots: dict) -> Dict[str, Any]:
    """Maneja venta/consignación de máquina."""
    reply = (
        "Podemos revisarla/recibirla si está buena. "
        "¿Qué marca y en qué estado está?"
    )
    
    return {
        "reply_text": reply,
        "stage_update": "support",
        "slot_updates": {"last_question": "sell_machine_info"},
        "decision_path": "sell_machine_handled"
    }


def _handle_default(intent: str, state: dict, user_text: str, text_lower: str, slots: dict) -> Dict[str, Any]:
    """Maneja casos por defecto."""
    reply = "¿Buscas máquina familiar (para casa) o industrial (para producción)?"
    
    return {
        "reply_text": reply,
        "stage_update": "discovery",
        "slot_updates": {"last_question": "product_type"},
        "decision_path": "default_handled"
    }


def pick_one_question(intent: str, state: dict) -> Optional[str]:
    """
    Elige LA pregunta más importante faltante según slots.
    Prioridad determinística, 1 pregunta por turno.
    
    Returns:
        Pregunta a hacer o None si no falta nada crítico
    """
    slots = state.get("slots", {})
    
    if intent == "buy_machine":
        # Prioridad: use_case -> qty -> budget -> visit_or_delivery -> city (solo si envío)
        if not slots.get("use_case"):
            return "use_case"
        elif not slots.get("qty"):
            return "qty"
        elif not slots.get("budget"):
            return "budget"
        elif not slots.get("visit_or_delivery"):
            return "visit_or_delivery"
        elif slots.get("visit_or_delivery") == "delivery" and not slots.get("city_filled"):
            return "city"
        else:
            return None
    
    elif intent == "business_advice":
        # Prioridad: budget OR qty OR product_type
        if not slots.get("budget"):
            return "budget"
        elif not slots.get("qty"):
            return "qty"
        elif not slots.get("product_type"):
            return "product_type"
        else:
            return None
    
    elif intent in ["spare_parts", "tech_support"]:
        # Prioridad: marca/modelo -> síntoma -> foto placa
        if not slots.get("marca"):
            return "marca"
        elif intent == "tech_support" and not slots.get("sintoma"):
            return "sintoma"
        elif not slots.get("foto_placa"):
            return "foto_placa"
        else:
            return None
    
    return None


def handle_objection(text_lower: str, state: dict) -> Optional[Dict[str, Any]]:
    """
    Maneja objeciones comunes (muy caro, solo averiguando, etc.).
    
    Returns:
        Respuesta a objeción o None si no es objeción
    """
    slots = state.get("slots", {})
    
    # Objeción: muy caro
    if any(kw in text_lower for kw in ["muy caro", "caro", "costoso", "no tengo", "no alcanza"]):
        reply = (
            "Entiendo. Tenemos opciones:\n\n"
            "• Financiación con Addi o Sistecrédito\n"
            "• Usadas en buen estado (pregunta por disponibilidad)\n"
            "• Familiares desde $400.000\n\n"
            "¿Qué presupuesto manejas?"
        )
        return {
            "reply_text": reply,
            "stage_update": "pricing",
            "slot_updates": {"last_question": "budget"},
            "decision_path": "objection_too_expensive"
        }
    
    # Objeción: solo averiguando
    if any(kw in text_lower for kw in ["solo averiguando", "solo estoy viendo", "información", "informacion", "solo info"]):
        reply = (
            "Sin problema. Te mando 2 opciones y listo. "
            "¿Industrial o familiar?"
        )
        return {
            "reply_text": reply,
            "stage_update": "discovery",
            "slot_updates": {"last_question": "product_type"},
            "decision_path": "objection_just_browsing"
        }
    
    return None

