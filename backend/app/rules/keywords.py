"""
Keywords centralizados para el sistema LUISA.
ÚNICA fuente de verdad para todas las listas de palabras clave.
"""
from typing import Set, Dict, List

# ============================================================================
# CONFIRMACIONES Y NEGACIONES
# ============================================================================

CONFIRMACIONES: Set[str] = {
    "si", "sí", "ok", "dale", "claro", "perfecto", "bueno", "vale",
    "está bien", "esta bien", "listo", "de acuerdo", "correcto",
    "exacto", "eso", "así es", "asi es", "afirmativo", "por favor",
    "muestrame", "muéstrame", "enséñame", "ensename", "a ver",
    "quiero ver", "me interesa", "manda", "envía", "envia",
    "pásame", "pasame", "dime", "cuáles", "cuales", "va", "oks", "okok"
}

NEGACIONES: Set[str] = {
    "no", "nop", "nel", "negativo", "otro", "otra", "diferente",
    "distinto", "distinta", "no esa", "no ese", "ninguno", "ninguna",
    "no me interesa", "no gracias", "paso", "mejor no", "no ahora",
    "más adelante", "mas adelante", "luego", "después", "despues"
}

# ============================================================================
# SALUDOS Y DESPEDIDAS
# ============================================================================

SALUDOS: Set[str] = {
    "hola", "buenos días", "buenos dias", "buenas tardes", "buenas noches",
    "buen día", "buen dia", "buenas", "saludos", "qué tal", "que tal",
    "hey", "holi", "alo", "aló"
}

DESPEDIDAS: Set[str] = {
    "gracias", "chau", "adiós", "adios", "nos vemos", "hasta luego",
    "perfecto gracias", "ok gracias", "listo gracias", "bye",
    "muchas gracias", "mil gracias", "te agradezco", "hasta pronto"
}

# ============================================================================
# COMERCIAL - PRECIOS Y COMPRA
# ============================================================================

PRECIO: Set[str] = {
    "precio", "precios", "cuánto cuesta", "cuanto cuesta",
    "cuánto vale", "cuanto vale", "valor", "costo",
    "precio de", "precio de la", "precio del", "cuánto es",
    "cuanto es", "qué precio", "que precio", "a cómo", "a como",
    "sale a", "está a", "esta a", "qué valor", "que valor"
}

DISPONIBILIDAD: Set[str] = {
    "disponible", "disponibles", "tienen", "hay", "stock",
    "inventario", "cuántas", "cuántos", "existe", "tienen en",
    "hay en", "disponibilidad", "en existencia", "hay stock",
    "tienen stock", "manejan"
}

FORMAS_PAGO: Set[str] = {
    "forma de pago", "formas de pago", "cómo pagar", "como pagar",
    "pago", "pagando", "addi", "sistecrédito", "sistecredito",
    "crédito", "credito", "financiación", "financiacion",
    "cuotas", "a plazos", "contado", "efectivo", "transferencia",
    "tarjeta", "nequi", "daviplata"
}

COMPRAR: Set[str] = {
    "comprar", "quiero comprar", "me interesa comprar",
    "necesito comprar", "voy a comprar", "ya hice el pago",
    "pagué", "pague", "lo quiero", "la quiero", "me la llevo",
    "listo para comprar", "cómo compro", "como compro"
}

COTIZACION: Set[str] = {
    "cotización", "cotizacion", "cotizar", "cotizame",
    "pasame cotización", "pásame cotización", "factura proforma",
    "presupuesto formal", "proforma"
}

ENVIO: Set[str] = {
    "envío", "envio", "enviar", "llegar", "entrega",
    "entregar", "envían", "envian", "hacen envío",
    "hacen envio", "a domicilio", "domicilio", "despacho",
    "mandan", "mandarlo", "tiempo de entrega", "cuándo llega",
    "cuando llega", "envían a", "envian a", "hacen envío a",
    "hacen envio a", "llegan a", "mandan a", "despachan a"
}

# ============================================================================
# TÉCNICO - SERVICIO E INSTALACIÓN
# ============================================================================

INSTALACION: Set[str] = {
    "instalación", "instalacion", "instalar", "instalen", "instalo",
    "montar", "montaje", "dejan funcionando", "dejen funcionando",
    "configurar", "poner a funcionar", "armado", "vengan a instalar"
}

VISITA: Set[str] = {
    "visita", "visitar", "van a", "van al", "vayan a",
    "ir a mi", "vengan", "pueden ir"
}

GARANTIA: Set[str] = {
    "garantía", "garantia", "garantizado", "cobertura",
    "respaldo", "soporte", "servicio técnico", "servicio tecnico",
    "postventa", "post venta", "si se daña", "si se dana"
}

REPARACION: Set[str] = {
    "servicio", "reparación", "reparacion", "arreglar",
    "arreglo", "mantenimiento", "revisar", "revisión",
    "revision", "no funciona", "se dañó", "se dano",
    "está mala", "esta mala", "no prende", "no cose",
    "tiene problemas", "se trabó", "se trabo", "hace ruido",
    "no avanza la tela", "rompe el hilo", "salta puntadas", "desajustada"
}

REPUESTOS: Set[str] = {
    "repuestos", "repuesto", "accesorios", "accesorio",
    "piezas", "pieza", "partes", "aguja", "agujas",
    "hilo", "hilos", "pedal", "pie", "prensatela",
    "bobina", "canilla"
}

CAPACITACION: Set[str] = {
    "capacitación", "capacitacion", "enseñan", "ensenan",
    "curso", "cursos", "aprendo", "aprender", "clases",
    "tutorial", "cómo usar", "como usar", "instrucciones",
    "me enseñan", "me ensenan"
}

ASESORIA: Set[str] = {
    "asesoría", "asesoria", "asesorar", "asesoramiento",
    "recomiendas", "recomienda", "qué me recomiendas",
    "que me recomiendas", "me recomiendas", "recomiéndame",
    "recomiendame", "qué máquina", "que maquina",
    "cuál máquina", "cual maquina", "sugieres", "sugerencia",
    "aconsejas", "qué necesito", "que necesito",
    "cuál es la mejor", "cual es la mejor"
}

# ============================================================================
# TIPO DE MÁQUINA
# ============================================================================

MAQUINA_FAMILIAR: Set[str] = {
    "máquina familiar", "maquina familiar", "familiar",
    "familiares", "para casa", "doméstico", "domestico",
    "hogar", "uso personal", "máquinas familiares",
    "maquinas familiares", "uso doméstico", "uso domestico",
    "para el hogar", "casera"
}

MAQUINA_INDUSTRIAL: Set[str] = {
    "máquina industrial", "maquina industrial", "industrial",
    "industriales", "taller", "producción", "produccion",
    "emprendimiento", "negocio", "máquinas industriales",
    "maquinas industriales", "recta industrial", "para taller",
    "para producir", "profesional", "trabajo pesado"
}

FILETEADORA: Set[str] = {
    "fileteadora", "fileteadoras", "filetear", "orillos",
    "terminar prendas", "acabados", "overlock", "overlok",
    "remalladora", "remallado"
}

# ============================================================================
# USO ESPECÍFICO
# ============================================================================

USO_ROPA: Set[str] = {
    "ropa", "prendas", "camisas", "pantalones", "vestidos",
    "blusas", "faldas", "confección", "confeccion"
}

USO_GORRAS: Set[str] = {
    "gorras", "gorra", "cachuchas", "sombreros"
}

USO_CALZADO: Set[str] = {
    "calzado", "zapatos", "zapatillas", "tenis", "botas", "sandalias"
}

USO_ACCESORIOS: Set[str] = {
    "accesorios", "accesorio", "bolsos", "carteras", "morrales", "billeteras"
}

USO_HOGAR: Set[str] = {
    "cortinas", "mantelería", "manteleria", "cojines",
    "lencería hogar", "lenceria hogar"
}

USO_UNIFORMES: Set[str] = {
    "uniformes", "dotación", "dotacion", "overoles"
}

USO_CUERO: Set[str] = {
    "cuero", "cueros", "marroquinería", "marroquineria"
}

# ============================================================================
# VOLUMEN DE PRODUCCIÓN
# ============================================================================

VOLUMEN_ALTO: Set[str] = {
    "constante", "muchas", "muchos", "producción constante",
    "produccion constante", "producción continua", "produccion continua",
    "continua", "diario", "todos los días", "clientes", "pedidos",
    "encargos", "alta producción", "alta produccion"
}

VOLUMEN_BAJO: Set[str] = {
    "pocas", "poca", "poco", "pocos", "ocasional", "esporádico",
    "esporadico", "hobby", "arreglos", "remiendos", "casual"
}

# ============================================================================
# IMPACTO DE NEGOCIO (triggers de handoff)
# ============================================================================

IMPACTO_NEGOCIO: Set[str] = {
    "montar negocio", "montar un negocio", "montar mi negocio",
    "emprendimiento", "emprender", "mi emprendimiento",
    "mi taller", "abrir taller", "mejorar mi negocio",
    "mejorar negocio", "hacer crecer", "crecer",
    "aumentar producción", "aumentar produccion",
    "escalar", "expandir"
}

# ============================================================================
# CIUDADES COLOMBIA
# ============================================================================

CIUDADES_MONTERIA: Set[str] = {"montería", "monteria"}

CIUDADES_OTRAS: Set[str] = {
    "bogotá", "bogota", "medellín", "medellin", "cali", "barranquilla",
    "cartagena", "santa marta", "manizales", "pereira", "armenia",
    "ibagué", "ibague", "villavicencio", "bucaramanga", "pasto",
    "neiva", "cúcuta", "cucuta", "sincelejo", "valledupar",
    "popayán", "popayan"
}

UBICACIONES_RURALES: Set[str] = {
    "municipio", "pueblo", "vereda", "corregimiento"
}

# Mapeo de ciudades normalizadas
CIUDADES_MAP: Dict[str, str] = {
    "montería": "montería", "monteria": "montería",
    "bogotá": "bogotá", "bogota": "bogotá",
    "medellín": "medellín", "medellin": "medellín",
    "cali": "cali",
    "barranquilla": "barranquilla",
    "cartagena": "cartagena",
    "bucaramanga": "bucaramanga",
    "pereira": "pereira",
    "manizales": "manizales",
    "ibagué": "ibagué", "ibague": "ibagué",
    "cúcuta": "cúcuta", "cucuta": "cúcuta",
    "villavicencio": "villavicencio",
    "santa marta": "santa marta",
    "pasto": "pasto",
    "neiva": "neiva",
    "armenia": "armenia",
    "sincelejo": "sincelejo",
    "valledupar": "valledupar",
    "popayán": "popayán", "popayan": "popayán"
}

# ============================================================================
# MARCAS Y MODELOS
# ============================================================================

MARCAS_MODELOS: Dict[str, tuple] = {
    "ssgemsy": ("SSGEMSY", "SG8802E"),
    "sg8802e": ("SSGEMSY", "SG8802E"),
    "union": ("UNION", "UN300"),
    "un300": ("UNION", "UN300"),
    "un350": ("UNION", "UN350"),
    "kansew": ("KANSEW", "KS653"),
    "ks653": ("KANSEW", "KS653"),
    "ks-8800": ("KANSEW", "KS-8800"),
    "ks8800": ("KANSEW", "KS-8800"),
    "singer": ("SINGER", None),
    "s0105": ("SINGER", "S0105"),
    "heavy duty": ("SINGER", "Heavy Duty"),
    "6705c": ("SINGER", "Heavy Duty 6705C"),
    "6705": ("SINGER", "Heavy Duty 6705C"),
    "kingter": ("KINGTER", "KT-D3"),
    "kt-d3": ("KINGTER", "KT-D3"),
    "ktd3": ("KINGTER", "KT-D3"),
    "willcox": ("WILLCOX", None),
    "wilcox": ("WILLCOX", None)
}

# ============================================================================
# PROMOCIONES
# ============================================================================

PROMOCIONES: Set[str] = {
    "promoción", "promocion", "promociones", "promociones de navidad",
    "promoción navideña", "promocion navidena", "oferta", "ofertas",
    "descuento", "descuentos", "rebaja", "rebajas", "especial",
    "tienen promoción", "hay promoción", "promoción navidad",
    "ganga", "oportunidad", "liquidación", "liquidacion",
    "precio especial", "navidad", "navideña", "navidena"
}

# ============================================================================
# FOTOS E IMÁGENES
# ============================================================================

FOTOS: Set[str] = {
    "fotos", "foto", "imágenes", "imagenes", "imagen",
    "muéstrame", "muestrame", "ver fotos", "quiero ver",
    "tienes fotos", "tiene fotos", "muestra", "fotografía",
    "fotografia", "regalame fotos", "regálame fotos",
    "puedes mostrarme", "muéstrame fotos", "envíame foto",
    "enviame foto", "pásame fotos", "pasame fotos",
    "mándame", "mandame"
}

# ============================================================================
# ESPECIFICACIONES
# ============================================================================

ESPECIFICACIONES: Set[str] = {
    "especificaciones", "especificacion", "características",
    "caracteristicas", "qué tiene", "que tiene",
    "incluye", "trae", "viene con", "specs",
    "detalles técnicos", "detalles tecnicos",
    "ficha técnica", "ficha tecnica", "datos", "info",
    "información técnica", "informacion tecnica"
}

# ============================================================================
# HORARIOS Y UBICACIÓN
# ============================================================================

HORARIOS: Set[str] = {
    "horario", "horarios", "hora", "cuándo abren", "cuando abren",
    "están abiertos", "estan abiertos", "abierto", "cierran"
}

UBICACION: Set[str] = {
    "dónde quedan", "donde quedan", "ubicación", "ubicacion",
    "dirección", "direccion", "cómo llego", "como llego"
}

# ============================================================================
# URGENCIA Y PROBLEMAS
# ============================================================================

URGENTE: Set[str] = {
    "urgente", "ya", "inmediato", "ahora mismo", "emergencia",
    "roto", "defectuoso", "reclamo", "demanda", "abogado", "legal"
}

PROBLEMAS: Set[str] = {
    "problema", "error", "no llegó", "perdido", "equivocado",
    "devolución", "reembolso", "cancelar", "cancelación",
    "insatisfecho", "mal servicio", "defectuoso", "rota", "roto",
    "reclamo", "queja", "mal estado", "llegó roto", "producto roto"
}

# ============================================================================
# ANTI-ABUSO / FUERA DEL NEGOCIO
# ============================================================================

FUERA_DEL_NEGOCIO: Set[str] = {
    # Programación y tecnología
    "programar", "programación", "código", "codigo", "python",
    "javascript", "java", "react", "angular", "software",
    "aplicación", "aplicacion", "app", "desarrollo", "programador",
    "bug", "debug", "api", "backend", "frontend", "base de datos",
    "sql", "html", "css", "algoritmo", "función", "funcion",
    
    # Tareas académicas
    "tarea", "examen", "trabajo escolar", "universidad",
    "colegio", "clase de", "profesor", "estudiar", "ensayo",
    "monografía", "monografia", "investigación", "investigacion",
    
    # Temas personales/sensibles
    "médico", "medico", "doctor", "enfermedad", "síntomas",
    "sintomas", "receta", "medicina", "abogado", "legal",
    "demanda", "divorcio", "psicólogo", "psicologo",
    
    # Otros servicios no relacionados
    "comida", "restaurante", "hotel", "vuelo", "viaje",
    "carro", "moto", "celular", "computador", "laptop",
    "televisor", "nevera", "lavadora"
}

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def normalize_text(text: str) -> str:
    """Normaliza texto para comparación."""
    return text.lower().strip()


def contains_any(text: str, keywords: Set[str]) -> bool:
    """Verifica si el texto contiene alguna de las palabras clave."""
    text_lower = normalize_text(text)
    return any(keyword in text_lower for keyword in keywords)


def extract_match(text: str, keywords: Set[str]) -> str | None:
    """Extrae la primera palabra clave que coincide."""
    text_lower = normalize_text(text)
    for keyword in keywords:
        if keyword in text_lower:
            return keyword
    return None


def get_all_comercial_keywords() -> Set[str]:
    """Retorna todos los keywords que indican consulta comercial."""
    return PRECIO | DISPONIBILIDAD | FORMAS_PAGO | COMPRAR | COTIZACION | ENVIO | PROMOCIONES


def get_all_tecnico_keywords() -> Set[str]:
    """Retorna todos los keywords que indican consulta técnica."""
    return INSTALACION | VISITA | GARANTIA | REPARACION | REPUESTOS | CAPACITACION


def get_all_handoff_triggers() -> Set[str]:
    """Retorna todos los keywords que pueden triggear handoff."""
    return (
        IMPACTO_NEGOCIO |
        INSTALACION |
        VISITA |
        CIUDADES_OTRAS |
        UBICACIONES_RURALES |
        PRECIO |
        FORMAS_PAGO |
        URGENTE |
        PROBLEMAS
    )


# ============================================================================
# VARIANTES DE COPY (Selección Determinística)
# ============================================================================

SALUDO_VARIANTES = [
    "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?",
    "¡Hola! 😊 Soy Luisa. ¿Te ayudo con máquinas familiares, industriales o repuestos?"
]

TRIAGE_FIRST_VARIANTES = [
    "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?",
    "¡Hola! 😊 Soy Luisa. ¿Qué necesitas: máquinas, repuestos o servicio técnico?"
]

TRIAGE_RETRY_VARIANTES = [
    "¿Es por máquinas, repuestos o servicio técnico?",
    "¿Necesitas máquinas, repuestos o soporte?"
]

HUMAN_ACTIVE_VARIANTES = [
    "¡Hola! 😊 Un asesor te va a contactar pronto.\n¿Quieres que pase tu nombre y barrio para que todo esté listo?",
    "¡Hola! 👋 Un asesor te contactará pronto.\n¿Te ayudo con tu nombre y ubicación mientras tanto?"
]

HANDOFF_LLAMAMOS_PASAS_MONTERIA_VARIANTES = [
    "Para coordinar pago y entrega, un asesor te va a acompañar.\n¿Te llamamos para agendar o prefieres pasar por el almacén?",
    "Para coordinar pago y entrega, te acompaña un asesor.\n¿Prefieres que te llamemos o pasas por el almacén?"
]

HANDOFF_LLAMAMOS_PASAS_FUERA_VARIANTES = [
    "Para tu proyecto, lo mejor es que un asesor te acompañe personalmente.\n¿Te llamamos para agendar cita o prefieres que vayamos a tu taller?",
    "Para tu proyecto, lo mejor es que un asesor te acompañe.\n¿Preferimos llamarte para agendar o vamos a tu taller?"
]


def select_variant(conversation_id: str, variants: List[str]) -> str:
    """
    Selecciona una variante determinísticamente basado en el conversation_id.
    
    Args:
        conversation_id: ID de la conversación (determinístico)
        variants: Lista de variantes disponibles
    
    Returns:
        Variante seleccionada (determinística para la misma conversación)
    """
    if not variants:
        return ""
    if len(variants) == 1:
        return variants[0]
    
    # Hash determinístico: siempre mismo resultado para mismo conversation_id
    hash_value = hash(conversation_id) % len(variants)
    return variants[hash_value]
