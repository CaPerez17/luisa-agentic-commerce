"""
Triage Service: Detecta intención específica y maneja mensajes ambiguos.
Para WhatsApp real: no asumir que todos quieren comprar máquina.
"""
from typing import Dict, Any, Optional, Tuple
import re

from app.rules.keywords import normalize_text, select_variant, TRIAGE_FIRST_VARIANTES, TRIAGE_RETRY_VARIANTES
from app.logging_config import logger


# Intents específicos para triage
TRIAGE_INTENTS = {
    "buy_machine": "buy_machine",
    "spare_parts": "spare_parts",
    "tech_support": "tech_support",
    "business_advice": "business_advice",
    "sell_machine": "sell_machine",
    "faq_hours_location": "faq_hours_location",
    "other": "other"
}


def classify_triage_intent(text: str) -> Tuple[str, float, bool]:
    """
    Clasifica la intención del usuario en categorías de triage.
    
    Returns:
        Tuple[intent, confidence, is_ambiguous]
        - intent: uno de TRIAGE_INTENTS
        - confidence: 0.0-1.0
        - is_ambiguous: True si el mensaje es ambiguo (necesita triage)
    """
    text_lower = normalize_text(text)
    words = text_lower.split()
    
    # Keywords por intent
    buy_machine_keywords = [
        "industrial", "familiar", "máquina", "maquina", "precio", "promo", "promoción",
        "recta", "fileteadora", "overlock", "singer", "kingter", "kansew", "union",
        "comprar", "quiero", "necesito", "busco", "cotización", "cotizacion"
    ]
    
    spare_parts_keywords = [
        "repuesto", "repuestos", "pieza", "piezas", "aguja", "agujas", "bobina", "bobinas",
        "prensatela", "prensatelas", "motor", "correa", "correas", "placa", "placa de identificación"
    ]
    
    tech_support_keywords = [
        "daño", "dano", "no prende", "no funciona", "ruido", "ruidoso", "mantenimiento",
        "instalación", "instalacion", "arreglo", "arreglar", "garantía", "garantia",
        "soporte", "reparación", "reparacion", "falla", "fallas", "problema", "problemas"
    ]
    
    business_advice_keywords = [
        "montar negocio", "emprender", "qué me recomiendas", "que me recomiendas",
        "quiero empezar", "consejo", "asesoría", "asesoria", "qué necesito", "que necesito",
        "recomendación", "recomendacion", "qué máquina conviene", "que maquina conviene"
    ]
    
    faq_hours_location_keywords = [
        "horario", "horarios", "dirección", "direccion", "ubicación", "ubicacion",
        "cómo llegar", "como llegar", "abren", "cierran", "cuándo abren", "cuando abren",
        "dónde están", "donde estan", "dirección de la tienda", "direccion de la tienda"
    ]
    
    sell_machine_keywords = [
        "vendo", "tengo una máquina", "tengo una maquina", "quiero vender", "usada", "usadas",
        "segunda", "segunda mano", "consignación", "consignacion", "tengo para vender"
    ]
    
    # Detectar intents con keywords (reglas determinísticas)
    intent_scores = {}
    
    # buy_machine
    buy_score = sum(1 for kw in buy_machine_keywords if kw in text_lower)
    if buy_score > 0:
        intent_scores["buy_machine"] = min(buy_score / 2.0, 1.0)  # Normalizar
    
    # spare_parts
    spare_score = sum(1 for kw in spare_parts_keywords if kw in text_lower)
    if spare_score > 0:
        intent_scores["spare_parts"] = min(spare_score / 2.0, 1.0)
    
    # tech_support
    tech_score = sum(1 for kw in tech_support_keywords if kw in text_lower)
    if tech_score > 0:
        intent_scores["tech_support"] = min(tech_score / 2.0, 1.0)
    
    # business_advice
    advice_score = sum(1 for kw in business_advice_keywords if kw in text_lower)
    if advice_score > 0:
        intent_scores["business_advice"] = min(advice_score / 2.0, 1.0)
    
    # faq_hours_location
    faq_score = sum(1 for kw in faq_hours_location_keywords if kw in text_lower)
    if faq_score > 0:
        intent_scores["faq_hours_location"] = min(faq_score / 2.0, 1.0)
    
    # sell_machine
    sell_score = sum(1 for kw in sell_machine_keywords if kw in text_lower)
    if sell_score > 0:
        intent_scores["sell_machine"] = min(sell_score / 2.0, 1.0)
    
    # Si hay un intent con score alto, retornarlo
    if intent_scores:
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        if best_intent[1] >= 0.5:  # Threshold de confianza
            return best_intent[0], best_intent[1], False
    
    # Si el mensaje es muy corto o ambiguo (hola, buenas, info, etc.)
    ambiguous_keywords = ["hola", "buenas", "buenos", "buen", "días", "dias", "tardes", "noches",
                          "info", "información", "informacion", "ayuda", "👋", "🤝"]
    
    is_ambiguous = (
        len(words) <= 3 and any(kw in text_lower for kw in ambiguous_keywords)
    ) or (
        len(words) <= 2
    )
    
    if is_ambiguous:
        return "other", 0.3, True
    
    # Default: other
    return "other", 0.3, True


def generate_triage_greeting(state: Optional[dict] = None, ambiguous_turns: int = 0, conversation_id: Optional[str] = None) -> str:
    """
    Genera el mensaje de triage para mensajes ambiguos.
    Versión humana: saludo + pregunta abierta guiada.
    
    Args:
        state: Estado conversacional (si existe, puede retomar contexto)
        ambiguous_turns: Número de turnos ambiguos consecutivos
        conversation_id: ID de la conversación para selección determinística de variante
    
    Returns:
        Mensaje de triage humano (sin menú numerado si es primer turno)
    """
    # Si hay estado previo reciente, retomar con contexto
    if state and state.get("last_intent"):
        last_intent = state.get("last_intent")
        slots = state.get("slots", {})
        
        # Si venía de compra de máquina
        if last_intent in ["buy_machine", "buscar_maquina_industrial", "buscar_maquina_familiar"]:
            product_type = slots.get("product_type")
            if product_type:
                return f"¡Dale! 😊 ¿Seguimos con las {product_type}es o necesitas repuesto?"
            return "¡Dale! 😊 ¿Seguimos con las máquinas o necesitas repuesto?"
    
    # Usar conversation_id o phone_from del state como identificador determinístico
    variant_key = conversation_id if conversation_id else (state.get("phone_from", "") if state else "")
    if not variant_key:
        variant_key = "default"  # Fallback si no hay identificador
    
    # Si es el primer turno ambiguo: saludo humano + pregunta cerrada con variación
    if ambiguous_turns == 0:
        return select_variant(variant_key, TRIAGE_FIRST_VARIANTES)
    
    # Si lleva 2+ turnos ambiguos: ofrecer opciones en lenguaje humano con variación
    return select_variant(variant_key, TRIAGE_RETRY_VARIANTES)


def parse_triage_response(text: str) -> Optional[str]:
    """
    Parsea la respuesta del usuario al triage.
    
    Returns:
        Intent correspondiente o None si no se puede parsear
    """
    text_lower = normalize_text(text)
    
    # Detectar número (1, 2, 3, 4)
    number_match = re.search(r'\b([1-4])\b', text_lower)
    if number_match:
        num = int(number_match.group(1))
        mapping = {
            1: "buy_machine",
            2: "spare_parts",
            3: "tech_support",
            4: "business_advice"
        }
        return mapping.get(num)
    
    # Detectar por keywords en la respuesta
    if any(kw in text_lower for kw in ["comprar", "máquina", "maquina", "precio", "industrial", "familiar"]):
        return "buy_machine"
    
    if any(kw in text_lower for kw in ["repuesto", "repuestos", "pieza", "aguja", "bobina"]):
        return "spare_parts"
    
    if any(kw in text_lower for kw in ["soporte", "garantía", "garantia", "reparación", "reparacion", "arreglo"]):
        return "tech_support"
    
    if any(kw in text_lower for kw in ["asesoría", "asesoria", "consejo", "recomendación", "recomendacion", "emprender", "negocio"]):
        return "business_advice"
    
    return None

