"""
Sales Dialogue Manager para LUISA.
Gestiona el estado conversacional y genera respuestas comerciales humanas.
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.services.intent_service import analyze_intent
from app.services.context_service import extract_context_from_history
from app.services.asset_service import select_catalog_asset
from app.logging_config import logger


def next_action(
    user_text: str,
    intent: str,
    state: dict,
    history: List[Dict[str, Any]],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determina la siguiente acción comercial basada en el estado conversacional.
    
    Args:
        user_text: Texto del usuario
        intent: Intención detectada
        state: Estado conversacional actual
        history: Historial de mensajes
        context: Contexto extraído del historial
    
    Returns:
        {
            "reply_text": str,
            "reply_assets": List[dict] opcional,
            "state_updates": dict,
            "decision_path": str
        }
    """
    from app.services.triage_service import (
        classify_triage_intent,
        generate_triage_greeting,
        parse_triage_response
    )
    
    text_lower = user_text.lower().strip()
    stage = state.get("stage", "discovery")
    slots = state.get("slots", {})
    last_question = state.get("last_question")
    asked_questions = state.get("asked_questions", {})
    
    # TRIAGE: Clasificar intención específica
    triage_intent, triage_confidence, is_ambiguous = classify_triage_intent(user_text)
    
    # Si está en stage triage, parsear respuesta del usuario
    if stage == "triage":
        parsed_intent = parse_triage_response(user_text)
        if parsed_intent:
            # Avanzar al stage correcto según intent parseado
            if parsed_intent == "buy_machine":
                return _handle_discovery(user_text, parsed_intent, text_lower, state, context)
            elif parsed_intent == "spare_parts":
                return _handle_spare_parts(user_text, text_lower, state)
            elif parsed_intent == "tech_support":
                return _handle_support_request(user_text, state)
            elif parsed_intent == "business_advice":
                return _handle_business_advice(user_text, text_lower, state, context)
    
    # Si el mensaje es ambiguo y NO hay estado previo, hacer triage
    if is_ambiguous and stage == "discovery" and not state.get("last_intent"):
        return {
            "reply_text": generate_triage_greeting(state),
            "reply_assets": None,
            "state_updates": {
                "stage": "triage",
                "last_question": "triage_menu",
                "pending_question": "triage_menu",
                "last_intent": "triage"
            },
            "decision_path": "triage_greeting"
        }
    
    # Si hay intención clara (no ambiguo), route directo
    if not is_ambiguous and triage_confidence >= 0.5:
        if triage_intent == "buy_machine":
            # Continuar con flujo normal de compra
            pass  # Caer al flujo normal
        elif triage_intent == "spare_parts":
            return _handle_spare_parts(user_text, text_lower, state)
        elif triage_intent == "tech_support":
            return _handle_support_request(user_text, state)
        elif triage_intent == "business_advice":
            return _handle_business_advice(user_text, text_lower, state, context)
        elif triage_intent == "faq_hours_location":
            return _handle_faq_hours_location(user_text, text_lower, state)
        elif triage_intent == "sell_machine":
            return _handle_sell_machine(user_text, text_lower, state)
    
    # Detectar cambio de intención
    intent_changed = _detect_intent_change(intent, text_lower, state)
    
    # FIX P0: Si el usuario pregunta "fotos" o similar, cambiar a stage photos
    if _is_photo_request(text_lower, intent):
        return _handle_photo_request(user_text, state, context, slots)
    
    # FIX P0: Si el usuario pregunta garantía/repuestos, responder directamente
    if _is_support_request(text_lower, intent):
        return _handle_support_request(user_text, state)
    
    # Si cambió de intención, responder la nueva intención primero
    if intent_changed and stage != "discovery":
        return _handle_intent_change(user_text, intent, text_lower, state, context)
    
    # Flujo normal según stage
    if stage == "discovery":
        return _handle_discovery(user_text, intent, text_lower, state, context)
    elif stage == "pricing":
        return _handle_pricing(user_text, intent, text_lower, state, context)
    elif stage == "visit":
        return _handle_visit(user_text, intent, text_lower, state, context)
    elif stage == "shipping":
        return _handle_shipping(user_text, intent, text_lower, state, context)
    elif stage == "photos":
        return _handle_photos(user_text, intent, text_lower, state, context)
    elif stage == "support":
        return _handle_support(user_text, intent, text_lower, state)
    elif stage == "triage":
        # Si sigue en triage sin respuesta clara, re-preguntar
        return {
            "reply_text": generate_triage_greeting(state),
            "reply_assets": None,
            "state_updates": {
                "last_question": "triage_menu"
            },
            "decision_path": "triage_repeat"
        }
    else:
        return _handle_default(user_text, intent, text_lower, state)


def _is_photo_request(text: str, intent: str) -> bool:
    """Detecta si el usuario está pidiendo fotos."""
    photo_keywords = ["foto", "fotos", "imagen", "imágenes", "catálogo", "catalogo", "ver", "muestra"]
    return any(kw in text for kw in photo_keywords) or intent in ["preguntar_catalogo", "ver_productos"]


def _is_support_request(text: str, intent: str) -> bool:
    """Detecta si es pregunta de soporte (garantía, repuestos)."""
    support_keywords = ["garantía", "garantia", "repuesto", "repuestos", "reparación", "reparacion", "arreglo"]
    return any(kw in text for kw in support_keywords) or intent in ["repuestos", "garantia"]


def _detect_intent_change(intent: str, text_lower: str, state: dict) -> bool:
    """Detecta si el usuario cambió de intención."""
    last_intent = state.get("last_intent")
    if not last_intent:
        return False
    
    # Intenciones que indican cambio de tema
    new_topic_intents = ["preguntar_catalogo", "preguntar_precio", "preguntar_garantia", 
                         "preguntar_repuestos", "preguntar_horarios", "preguntar_direccion"]
    
    if intent in new_topic_intents and intent != last_intent:
        return True
    
    # Detectar keywords de cambio
    change_keywords = ["foto", "precio", "garantía", "repuesto", "horario", "dirección"]
    if any(kw in text_lower for kw in change_keywords):
        return True
    
    return False


def _handle_photo_request(user_text: str, state: dict, context: dict, slots: dict) -> Dict[str, Any]:
    """Maneja solicitud de fotos."""
    product_type = slots.get("product_type") or context.get("tipo_maquina")
    use_case = slots.get("use_case") or context.get("uso")
    
    # Seleccionar assets relevantes
    assets = []
    if product_type:
        asset, handoff_required = select_catalog_asset(user_text, context)
        if asset and not handoff_required:
            assets.append(asset)
    
    # Respuesta base
    if product_type == "industrial":
        if use_case:
            reply = f"Sí, claro. Para {use_case} te recomiendo estas opciones industriales. Te mando 2-3 opciones con fotos."
        else:
            reply = "Sí, claro. ¿Qué vas a coser: ropa, gorras, calzado o accesorios? Te mando 2-3 opciones con fotos."
    elif product_type == "familiar":
        reply = "Sí, claro. Para casa tenemos varias opciones. Te mando 2-3 opciones con fotos."
    else:
        reply = "Sí, claro. ¿Qué tipo: industrial o familiar? Y ¿qué vas a coser? Te mando 2-3 opciones con fotos."
    
    # Pregunta de seguimiento (máximo 1)
    if not use_case and product_type:
        reply += "\n\n¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
    elif not product_type:
        reply += "\n\n¿Buscas para casa o para producción?"
    else:
        reply += "\n\n¿Presupuesto aproximado?"
    
    state_updates = {
        "stage": "photos",
        "last_intent": "preguntar_catalogo",
        "last_question": "product_type" if not product_type else ("use_case" if not use_case else "budget")
    }
    
    return {
        "reply_text": reply,
        "reply_assets": assets[:3] if assets else None,
        "state_updates": state_updates,
        "decision_path": "photo_request_handled"
    }


def _handle_support_request(user_text: str, state: dict) -> Dict[str, Any]:
    """Maneja preguntas de soporte (garantía, repuestos)."""
    text_lower = user_text.lower()
    
    if "garantía" in text_lower or "garantia" in text_lower:
        reply = (
            "Todas nuestras máquinas tienen garantía de 3 meses en partes y mano de obra. "
            "Si algo falla, la revisamos sin costo. ¿Qué máquina tienes o estás pensando comprar?"
        )
    elif "repuesto" in text_lower:
        reply = (
            "Sí, tenemos repuestos para las marcas que vendemos. "
            "¿Me confirmas la marca o me envías foto de la placa? Así te doy precio exacto."
        )
    else:
        reply = "Te puedo ayudar con garantía, repuestos o servicio técnico. ¿Qué necesitas?"
    
    state_updates = {
        "stage": "support",
        "last_intent": "repuestos" if "repuesto" in text_lower else "garantia"
    }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "support_request_handled"
    }


def _handle_intent_change(user_text: str, intent: str, text_lower: str, state: dict, context: dict) -> Dict[str, Any]:
    """Maneja cambio de intención en medio de otra conversación."""
    # Responder la nueva intención primero
    if _is_photo_request(text_lower, intent):
        return _handle_photo_request(user_text, state, context, state.get("slots", {}))
    elif "precio" in text_lower or intent == "preguntar_precio":
        return _handle_pricing(user_text, intent, text_lower, state, context)
    elif "horario" in text_lower or intent == "preguntar_horarios":
        reply = (
            "Nuestro horario:\n\n"
            "📍 Calle 34 #1-30, Montería\n"
            "🕘 Lunes a viernes: 9am-6pm\n"
            "🕘 Sábados: 9am-2pm\n\n"
        )
        # Retomar hilo anterior si hay uno pendiente
        pending = state.get("pending_question")
        if pending == "city":
            city = state.get("slots", {}).get("city")
            if city and city.lower() != "montería" and city.lower() != "monteria":
                reply += f"Veo que mencionaste {city}. ¿Vas a venir a Montería a la tienda o prefieres que te coordinemos envío?"
            else:
                reply += "¿Quieres pasar o prefieres envío a domicilio?"
        else:
            reply += "¿Quieres pasar o prefieres envío a domicilio?"
        
        return {
            "reply_text": reply,
            "reply_assets": None,
            "state_updates": {"last_intent": intent, "stage": "visit"},
            "decision_path": "intent_change_handled"
        }
    else:
        # Default: responder y retomar
        return _handle_default(user_text, intent, text_lower, state)


def _handle_discovery(user_text: str, intent: str, text_lower: str, state: dict, context: dict) -> Dict[str, Any]:
    """Maneja etapa de descubrimiento (identificar necesidad)."""
    slots = state.get("slots", {})
    asked_questions = state.get("asked_questions", {})
    
    # Detectar tipo de máquina
    if "industrial" in text_lower:
        slots["product_type"] = "industrial"
        state_updates = {
            "slots": slots,
            "stage": "pricing",
            "last_intent": intent
        }
        return {
            "reply_text": "Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?",
            "reply_assets": None,
            "state_updates": state_updates,
            "decision_path": "discovery_industrial"
        }
    
    if "familiar" in text_lower or "casa" in text_lower or "hogar" in text_lower:
        slots["product_type"] = "familiar"
        state_updates = {
            "slots": slots,
            "stage": "pricing",
            "last_intent": intent
        }
        return {
            "reply_text": "Para casa una máquina familiar funciona bien. ¿Qué tipo de costura haces: arreglos, proyectos o costura creativa?",
            "reply_assets": None,
            "state_updates": state_updates,
            "decision_path": "discovery_familiar"
        }
    
    # Si no ha respondido, preguntar tipo
    if not slots.get("product_type"):
        if "product_type" not in asked_questions:
            state_updates = {
                "last_question": "product_type",
                "asked_questions": {**asked_questions, "product_type": datetime.utcnow().isoformat()}
            }
            return {
                "reply_text": "¿Buscas máquina familiar (para casa) o industrial (para producción)?",
                "reply_assets": None,
                "state_updates": state_updates,
                "decision_path": "discovery_ask_type"
            }
    
    return _handle_default(user_text, intent, text_lower, state)


def _handle_pricing(user_text: str, intent: str, text_lower: str, state: dict, context: dict) -> Dict[str, Any]:
    """Maneja etapa de precios."""
    slots = state.get("slots", {})
    product_type = slots.get("product_type") or context.get("tipo_maquina")
    
    # Detectar uso
    use_cases = {
        "ropa": ["ropa", "vestido", "camisa", "pantalón"],
        "gorras": ["gorra", "gorras", "sombrero"],
        "calzado": ["zapato", "zapatos", "calzado"],
        "accesorios": ["accesorio", "accesorios", "bolso", "mochila"]
    }
    
    detected_use = None
    for use, keywords in use_cases.items():
        if any(kw in text_lower for kw in keywords):
            detected_use = use
            break
    
    if detected_use:
        slots["use_case"] = detected_use
    
    # Detectar cantidad
    qty_match = re.search(r'(\d+)\s*(unidades|piezas|pares|máquinas)', text_lower)
    if qty_match:
        slots["qty"] = qty_match.group(1)
    
    # Respuesta según tipo
    if product_type == "industrial":
        reply = (
            "Las industriales en promoción:\n\n"
            "• KINGTER KT-D3: $1.230.000\n"
            "• KANSEW KS-8800: $1.300.000\n\n"
            "Incluyen mesa, motor ahorrador e instalación."
        )
    else:
        reply = (
            "Los precios varían según el tipo:\n\n"
            "• Familiares: desde $400.000\n"
            "• Industriales: desde $1.230.000\n\n"
        )
    
    # Pregunta siguiente (máximo 1)
    if not slots.get("use_case") and product_type == "industrial":
        reply += "\n\n¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        state_updates = {
            "slots": slots,
            "last_question": "use_case",
            "last_intent": intent
        }
    elif not context.get("ciudad") and not slots.get("city"):
        reply += "\n\n¿En qué ciudad te encuentras para coordinar el envío?"
        state_updates = {
            "slots": slots,
            "stage": "shipping",
            "last_question": "city",
            "last_intent": intent
        }
    else:
        reply += "\n\n¿Te separo una o quieres que te mande 2 opciones con fotos?"
        state_updates = {
            "slots": slots,
            "stage": "photos",
            "last_intent": intent
        }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "pricing_handled"
    }


def _handle_visit(user_text: str, intent: str, text_lower: str, state: dict, context: dict) -> Dict[str, Any]:
    """Maneja etapa de visita a tienda."""
    slots = state.get("slots", {})
    city = slots.get("city") or context.get("ciudad")
    
    # Detectar si menciona ciudad distinta a Montería
    if "quiero pasar" in text_lower or "pasar" in text_lower or "visitar" in text_lower:
        # Extraer ciudad si menciona una
        city_match = re.search(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b', user_text)
        if city_match:
            mentioned_city = city_match.group(1)
            if mentioned_city.lower() not in ["montería", "monteria", "quiero", "pasar"]:
                slots["city"] = mentioned_city
                city = mentioned_city
        
        # Disambiguación humana
        if city and city.lower() not in ["montería", "monteria"]:
            reply = (
                f"Perfecto. ¿Vas a venir a Montería a la tienda o prefieres que te coordinemos envío a {city}?"
            )
            state_updates = {
                "slots": {**slots, "city": city},
                "last_question": "visit_or_delivery",
                "last_intent": intent
            }
        else:
            reply = (
                "Perfecto. Estamos en Calle 34 #1-30, Montería.\n\n"
                "🕘 Lunes a viernes: 9am-6pm\n"
                "🕘 Sábados: 9am-2pm\n\n"
                "¿Qué día te viene mejor?"
            )
            state_updates = {
                "slots": slots,
                "last_question": "visit_date",
                "last_intent": intent
            }
    else:
        # Si ya dio ciudad, no preguntar de nuevo
        if city and "city" not in state.get("asked_questions", {}):
            reply = "¿Vas a venir a Montería a la tienda o prefieres envío a domicilio?"
            state_updates = {
                "slots": slots,
                "last_question": "visit_or_delivery",
                "last_intent": intent
            }
        else:
            reply = "¿Quieres pasar o prefieres envío a domicilio?"
            state_updates = {
                "slots": slots,
                "last_question": "visit_or_delivery",
                "last_intent": intent
            }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "visit_handled"
    }


def _handle_shipping(user_text: str, intent: str, text_lower: str, state: dict, context: dict) -> Dict[str, Any]:
    """Maneja etapa de envío."""
    slots = state.get("slots", {})
    asked_questions = state.get("asked_questions", {})
    
    # Extraer ciudad
    city_match = re.search(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b', user_text)
    if city_match:
        city = city_match.group(1)
        if city.lower() not in ["quiero", "pasar", "envío", "envio", "domicilio"]:
            slots["city"] = city
    
    # Si ya tiene ciudad, no preguntar de nuevo
    if slots.get("city") and "city" in asked_questions:
        reply = f"Perfecto, envío a {slots['city']}. ¿Te separo una máquina o quieres ver fotos primero?"
        state_updates = {
            "slots": slots,
            "stage": "photos",
            "last_intent": intent
        }
    else:
        reply = "¿En qué ciudad o municipio sería el envío?"
        state_updates = {
            "slots": slots,
            "last_question": "city",
            "asked_questions": {**asked_questions, "city": datetime.utcnow().isoformat()},
            "last_intent": intent
        }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "shipping_handled"
    }


def _handle_photos(user_text: str, intent: str, text_lower: str, state: dict, context: dict) -> Dict[str, Any]:
    """Maneja etapa de mostrar fotos."""
    slots = state.get("slots", {})
    product_type = slots.get("product_type") or context.get("tipo_maquina")
    use_case = slots.get("use_case") or context.get("uso")
    
    # Seleccionar assets
    assets = []
    asset, handoff_required = select_catalog_asset(user_text, context)
    if asset and not handoff_required:
        assets.append(asset)
    
    # Si el usuario está confuso
    if "no sé" in text_lower or "cual" in text_lower or "cuál" in text_lower:
        if product_type == "industrial":
            reply = (
                "Te recomiendo 2 opciones:\n\n"
                "• KINGTER KT-D3: $1.230.000 - Ideal para gorras y ropa\n"
                "• KANSEW KS-8800: $1.300.000 - Más robusta, para producción constante\n\n"
                "¿Te separo una o quieres ver fotos de ambas?"
            )
        else:
            reply = (
                "Para casa te recomiendo empezar con una familiar básica ($400.000) o una intermedia ($600.000). "
                "¿Te mando fotos de ambas para que veas cuál te gusta más?"
            )
        state_updates = {
            "slots": slots,
            "last_question": "choice",
            "last_intent": intent
        }
    else:
        reply = "Perfecto. ¿Te separo una o quieres ver más opciones?"
        state_updates = {
            "slots": slots,
            "last_question": "decision",
            "last_intent": intent
        }
    
    return {
        "reply_text": reply,
        "reply_assets": assets[:3] if assets else None,
        "state_updates": state_updates,
        "decision_path": "photos_handled"
    }


def _handle_support(user_text: str, intent: str, text_lower: str, state: dict) -> Dict[str, Any]:
    """Maneja etapa de soporte."""
    return _handle_support_request(user_text, state)


def _handle_spare_parts(user_text: str, text_lower: str, state: dict) -> Dict[str, Any]:
    """Maneja solicitud de repuestos."""
    reply = (
        "Sí, tenemos repuestos para las marcas que vendemos. "
        "¿Me confirmas la marca o me envías foto de la placa? Así te doy precio exacto."
    )
    state_updates = {
        "stage": "support",
        "last_intent": "spare_parts",
        "last_question": "spare_parts_marca"
    }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "spare_parts_handled"
    }


def _handle_business_advice(user_text: str, text_lower: str, state: dict, context: dict) -> Dict[str, Any]:
    """Maneja asesoría para montar negocio."""
    # Detectar tipo de negocio mencionado
    if "gorra" in text_lower or "gorras" in text_lower:
        reply = (
            "Perfecto, para gorras te recomiendo una industrial recta. "
            "¿Vas a producir de forma ocasional o constante?"
        )
    elif "ropa" in text_lower:
        reply = (
            "Para ropa necesitas una industrial recta. "
            "¿Qué tipo de prendas: camisas, pantalones, vestidos?"
        )
    else:
        reply = (
            "Te puedo ayudar a elegir la máquina ideal. "
            "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        )
    
    state_updates = {
        "stage": "discovery",
        "last_intent": "business_advice",
        "last_question": "business_type"
    }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "business_advice_handled"
    }


def _handle_faq_hours_location(user_text: str, text_lower: str, state: dict) -> Dict[str, Any]:
    """Maneja preguntas de horarios y ubicación."""
    if "horario" in text_lower or "hora" in text_lower or "abren" in text_lower or "cierran" in text_lower:
        reply = (
            "Nuestro horario:\n\n"
            "📍 Calle 34 #1-30, Montería\n"
            "🕘 Lunes a viernes: 9am-6pm\n"
            "🕘 Sábados: 9am-2pm\n\n"
            "¿Quieres pasar o prefieres envío a domicilio?"
        )
    else:
        reply = (
            "Estamos en Calle 34 #1-30, Montería.\n\n"
            "🕘 Lunes a viernes: 9am-6pm\n"
            "🕘 Sábados: 9am-2pm\n\n"
            "¿Cómo te puedo ayudar más?"
        )
    
    state_updates = {
        "stage": "visit",
        "last_intent": "faq_hours_location"
    }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "faq_hours_location_handled"
    }


def _handle_sell_machine(user_text: str, text_lower: str, state: dict) -> Dict[str, Any]:
    """Maneja solicitud de vender máquina (consignación)."""
    reply = (
        "Para vender o consignar máquinas, necesito que me envíes:\n"
        "• Foto de la máquina\n"
        "• Marca y modelo (o foto de la placa)\n"
        "• Estado (nueva, usada, reparada)\n\n"
        "Con eso te doy una valoración."
    )
    state_updates = {
        "stage": "support",
        "last_intent": "sell_machine",
        "last_question": "sell_machine_info"
    }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "sell_machine_handled"
    }


def _handle_default(user_text: str, intent: str, text_lower: str, state: dict) -> Dict[str, Any]:
    """Maneja casos por defecto."""
    reply = "¿Buscas máquina familiar (para casa) o industrial (para producción)?"
    state_updates = {
        "stage": "discovery",
        "last_intent": intent
    }
    
    return {
        "reply_text": reply,
        "reply_assets": None,
        "state_updates": state_updates,
        "decision_path": "default_handled"
    }

