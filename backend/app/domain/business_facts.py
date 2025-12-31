"""
Business Facts: Datos duros del negocio.
Nunca inventar: solo usar estos facts.
"""
from typing import List, Dict, Any

# Horarios y ubicación
BUSINESS_HOURS = {
    "weekdays": "Lunes a viernes: 9am-6pm",
    "saturday": "Sábados: 9am-2pm",
    "address": "Calle 34 #1-30, Montería, Córdoba, Colombia"
}

# Garantía
GUARANTEE = {
    "duration_months": 3,
    "coverage": "partes y mano de obra",
    "description": "Si algo falla, la revisamos sin costo"
}

# Promociones actuales (datos exactos)
PROMOTIONS = [
    {
        "name": "KINGTER KT-D3",
        "price": 1230000,
        "includes": ["mesa", "motor ahorrador", "instalación"],
        "category": "industrial",
        "best_for": ["gorras", "ropa", "producción ocasional"]
    },
    {
        "name": "KANSEW KS-8800",
        "price": 1300000,
        "includes": ["mesa", "motor ahorrador", "instalación"],
        "category": "industrial",
        "best_for": ["producción constante", "tela gruesa", "escalar"]
    }
]

# Precios base (rangos)
PRICE_RANGES = {
    "familiar": {
        "min": 400000,
        "max": 600000,
        "description": "desde $400.000"
    },
    "industrial": {
        "min": 1230000,
        "max": 1300000,
        "description": "desde $1.230.000"
    }
}

# Formas de pago
PAYMENT_METHODS = [
    "Addi",
    "Sistecrédito",
    "Efectivo",
    "Transferencia"
]

# Opciones de entrega
DELIVERY_OPTIONS = {
    "visit": "Visita a tienda en Montería",
    "shipping": "Envío a domicilio (coordinado según ciudad)"
}

# Disclaimers
DISCLAIMERS = {
    "stock": "Stock sujeto a disponibilidad",
    "shipping": "Envío a coordinar según ciudad/barrio",
    "prices": "Precios en promoción, sujetos a cambio"
}

# Repuestos disponibles
SPARE_PARTS_BRANDS = [
    "Singer",
    "KINGTER",
    "KANSEW",
    "Union"
]

# Servicios técnicos
TECH_SERVICES = [
    "Instalación",
    "Mantenimiento",
    "Reparación",
    "Garantía"
]


def get_business_facts_summary() -> str:
    """
    Retorna un resumen serializado de los facts para pasar a OpenAI.
    """
    facts = f"""
NEGOCIO: Almacén y Taller El Sastre

UBICACIÓN Y HORARIOS:
- Dirección: {BUSINESS_HOURS['address']}
- {BUSINESS_HOURS['weekdays']}
- {BUSINESS_HOURS['saturday']}

GARANTÍA:
- {GUARANTEE['duration_months']} meses en {GUARANTEE['coverage']}
- {GUARANTEE['description']}

PROMOCIONES ACTUALES:
"""
    for promo in PROMOTIONS:
        facts += f"- {promo['name']}: ${promo['price']:,} (incluye: {', '.join(promo['includes'])})\n"
    
    facts += f"""
PRECIOS BASE:
- Familiares: {PRICE_RANGES['familiar']['description']}
- Industriales: {PRICE_RANGES['industrial']['description']}

FORMAS DE PAGO:
- {', '.join(PAYMENT_METHODS)}

ENTREGA:
- Visita a tienda en Montería
- Envío a domicilio (coordinado según ciudad)

REPUESTOS:
- Disponibles para: {', '.join(SPARE_PARTS_BRANDS)}

SERVICIOS:
- {', '.join(TECH_SERVICES)}

DISCLAIMERS:
- {DISCLAIMERS['stock']}
- {DISCLAIMERS['shipping']}
- {DISCLAIMERS['prices']}
"""
    return facts


def get_promotions_for_context() -> List[Dict[str, Any]]:
    """Retorna promociones en formato para contexto de OpenAI."""
    return PROMOTIONS


def get_price_ranges_for_context() -> Dict[str, Any]:
    """Retorna rangos de precios para contexto de OpenAI."""
    return PRICE_RANGES

