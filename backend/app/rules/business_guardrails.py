"""
Guardrails para determinar si un mensaje está relacionado con el negocio.
Usa heurísticas y keywords, NO LLM, para mantener baja latencia y costo cero.
"""
import re
from typing import Tuple, Optional

from app.rules.keywords import (
    normalize_text,
    contains_any,
    FUERA_DEL_NEGOCIO,
    SALUDOS,
    DESPEDIDAS,
    CONFIRMACIONES,
    NEGACIONES,
    PRECIO,
    DISPONIBILIDAD,
    FORMAS_PAGO,
    COMPRAR,
    COTIZACION,
    ENVIO,
    INSTALACION,
    VISITA,
    GARANTIA,
    REPARACION,
    REPUESTOS,
    CAPACITACION,
    ASESORIA,
    MAQUINA_FAMILIAR,
    MAQUINA_INDUSTRIAL,
    FILETEADORA,
    USO_ROPA,
    USO_GORRAS,
    USO_CALZADO,
    USO_ACCESORIOS,
    USO_CUERO,
    PROMOCIONES,
    FOTOS,
    ESPECIFICACIONES,
    HORARIOS,
    UBICACION,
    IMPACTO_NEGOCIO,
    VOLUMEN_ALTO,
    VOLUMEN_BAJO
)


# Keywords específicos del negocio El Sastre
NEGOCIO_KEYWORDS = {
    # Productos
    "máquina", "maquina", "máquinas", "maquinas",
    "coser", "costura", "sastre", "tela", "telas",
    
    # Marcas que manejamos
    "singer", "kingter", "kansew", "ssgemsy", "union", "willcox",
    
    # Acciones del negocio
    "comprar", "vender", "reparar", "arreglar", "instalar",
    "enviar", "entregar", "cotizar", "pagar",
    
    # Contexto de costura
    "confección", "confeccion", "modista", "modistería",
    "taller", "producción", "produccion", "puntada", "puntadas",
    "ojal", "ojales", "hilo", "aguja", "prensatela", "bobina"
}

# Respuesta amigable cuando el mensaje está fuera del negocio
RESPUESTA_FUERA_NEGOCIO = (
    "Hola 😊 Yo te ayudo con máquinas de coser, repuestos, "
    "servicio técnico y asesoría del Sastre. ¿Qué necesitas sobre eso?"
)


from enum import Enum


class MessageType(Enum):
    """Clasificación de tipos de mensaje para gating de OpenAI."""
    EMPTY_OR_GIBBERISH = "empty_or_gibberish"  # ".", "jaja", "👍", "ok", solo emojis
    NON_BUSINESS = "non_business"  # programación, código, temas ajenos
    BUSINESS_FAQ = "business_faq"  # horarios, dirección, envíos, pagos, ubicación
    BUSINESS_CONSULT = "business_consult"  # venta/asesoría/repuestos/garantía/reparación


def classify_message_type(text: str) -> MessageType:
    """
    Clasifica el tipo de mensaje para determinar si puede usar OpenAI.

    Returns:
        MessageType enum
    """
    text_normalized = normalize_text(text)
    words = text_normalized.split()

    # EMPTY_OR_GIBBERISH: mensajes vacíos, cortos o sin sentido
    if not text_normalized or len(text_normalized) < 2:
        return MessageType.EMPTY_OR_GIBBERISH

    if len(words) <= 2:
        # Mensajes muy cortos sin contexto -> EMPTY_OR_GIBBERISH (prioridad alta)
        short_gibberish = ["ok", "si", "no", "👍", "👌", "😊", "🙂", "gracias", "vale", ".", "!", "?", "...", "jaja"]
        if len(text_normalized) <= 5 or text_normalized.lower() in short_gibberish:
            return MessageType.EMPTY_OR_GIBBERISH

        # Solo confirmaciones/negaciones/saludos -> BUSINESS_FAQ
        if contains_any(text, CONFIRMACIONES | NEGACIONES | SALUDOS | DESPEDIDAS):
            return MessageType.BUSINESS_FAQ

    # BLACKLIST ROBUSTA: señales claras de temas fuera del negocio
    blacklist_signals = {
        # Programación y tecnología
        "python", "javascript", "java", "react", "angular", "vue", "node", "npm", "pip", "django",
        "flask", "fastapi", "selenium", "docker", "kubernetes", "aws", "azure", "git", "github",
        "sql", "mysql", "postgresql", "mongodb", "redis", "html", "css", "typescript", "php",
        "ruby", "rust", "c++", "c#", "scala", "kotlin", "swift", "objective-c",
        "matlab", "sas", "tableau", "power bi", "excel vba", "macro", "script", "bash", "shell",
        "linux", "windows", "macos", "ubuntu", "debian", "centos", "redhat", "algorithm", "algoritmo",
        "bug", "debug", "error", "exception", "stacktrace", "null pointer", "syntax error",
        "compilation", "framework", "library", "api", "backend", "frontend", "fullstack",
        "programar", "programación", "código", "codigo", "programador", "desarrollo", "software",

        # Tareas académicas
        "tarea", "examen", "trabajo", "universidad", "colegio", "clase", "profesor", "estudiar",
        "ensayo", "monografía", "investigación", "tesis", "matemáticas", "física", "química",

        # Temas médicos y de salud
        "dolor", "medicina", "medicamento", "enfermedad", "síntoma", "sintoma", "doctor", "médico",
        "hospital", "clínica", "fiebre", "gripe", "covid", "coronavirus", "vacuna", "pastilla",
        "tableta", "inyección", "cirugía", "cirugia", "tratamiento", "diagnóstico", "diagnostico",
        
        # Otros temas no relacionados
        "política", "política", "religión", "religión", "fútbol", "futbol", "deporte", "música",
        "cine", "series", "netflix", "spotify", "instagram", "facebook", "twitter", "tiktok",
        "whatsapp", "telegram", "comida", "restaurante", "hotel", "viaje", "vacaciones", "turismo"
    }

    # Contar señales de blacklist (palabras completas, no substrings)
    words_in_text = set(text_normalized.split())
    blacklist_count = sum(1 for signal in blacklist_signals if signal in words_in_text)
    
    # Si hay señales claras de blacklist -> NON_BUSINESS
    if blacklist_count >= 2 or any(signal in text_normalized for signal in [
        "cómo hago un", "como hago un", "ayuda con", "necesito ayuda con", "problema con",
        "error en", "no funciona mi", "bug en", "código", "codigo"
    ]):
        return MessageType.NON_BUSINESS

    # BUSINESS_FAQ: preguntas simples sobre info básica del negocio
    faq_keywords = HORARIOS | UBICACION | {"telefono", "teléfono", "contacto", "dirección", "direccion"}
    if contains_any(text, faq_keywords):
        return MessageType.BUSINESS_FAQ

    # BUSINESS_FAQ: formas de pago, envíos, promociones
    if contains_any(text, FORMAS_PAGO | ENVIO | PROMOCIONES):
        return MessageType.BUSINESS_FAQ

    # BUSINESS_CONSULT: consultas complejas sobre productos/servicios
    consult_keywords = (
        MAQUINA_FAMILIAR | MAQUINA_INDUSTRIAL | FILETEADORA | REPUESTOS |
        INSTALACION | REPARACION | GARANTIA | CAPACITACION | ASESORIA |
        USO_ROPA | USO_GORRAS | USO_CALZADO | USO_ACCESORIOS | USO_CUERO |
        IMPACTO_NEGOCIO | {"emprender", "negocio", "taller", "producción", "produccion"}
    )

    if contains_any(text, consult_keywords):
        return MessageType.BUSINESS_CONSULT

    # BUSINESS_FAQ: preguntas sobre precio/disponibilidad (pueden ser simples)
    if contains_any(text, PRECIO | DISPONIBILIDAD):
        return MessageType.BUSINESS_FAQ

    # Default: si tiene keywords del negocio, BUSINESS_CONSULT
    negocio_signals = sum(1 for keyword in NEGOCIO_KEYWORDS if keyword in text_normalized)
    if negocio_signals > 0:
        return MessageType.BUSINESS_CONSULT

    # Si no clasifica claramente, asumir BUSINESS_CONSULT (ser permisivo)
    return MessageType.BUSINESS_CONSULT


def is_business_related(text: str) -> Tuple[bool, str]:
    """
    Determina si el mensaje está relacionado con el negocio.
    Ahora usa classify_message_type internamente.
    
    Returns:
        Tuple[bool, str]: (es_del_negocio, razón)
    """
    message_type = classify_message_type(text)

    if message_type == MessageType.EMPTY_OR_GIBBERISH:
        return True, "empty_or_gibberish"  # Permitir pero tratar diferente

    if message_type == MessageType.NON_BUSINESS:
        return False, "non_business"

    return True, f"business_{message_type.value}"


def get_response_for_message_type(message_type: MessageType, text: str, conversation_id: Optional[str] = None) -> str:
    """
    Retorna la respuesta apropiada según el tipo de mensaje.
    """
    if message_type == MessageType.EMPTY_OR_GIBBERISH:
        # Selección determinística de variante de saludo
        variant_key = conversation_id if conversation_id else "default"
        return select_variant(variant_key, SALUDO_VARIANTES)

    if message_type == MessageType.NON_BUSINESS:
        return "¡Hola! 😊 Te ayudo con máquinas, repuestos y servicio técnico.\n¿Qué necesitas?"

    # Para BUSINESS_FAQ y BUSINESS_CONSULT, usar el pipeline normal
    return ""


def get_off_topic_response() -> str:
    """Retorna la respuesta para mensajes fuera del negocio."""
    return RESPUESTA_FUERA_NEGOCIO


def is_sensitive_query(text: str) -> bool:
    """
    Detecta si es una consulta sensible que NO debe cachearse.
    """
    text_normalized = normalize_text(text)
    
    sensitive_patterns = [
        # Datos personales
        r'\b\d{10}\b',  # Números de teléfono
        r'\b\d{3}\s?\d{3}\s?\d{4}\b',  # Teléfonos con espacios
        r'@\w+\.\w+',  # Emails
        r'cedula|cédula|cc\s*\d+',  # Documentos
        
        # Pagos/Transacciones
        r'(ya\s+)?pag[ué|ue|o]',  # "ya pagué", "pagué", "pago"
        r'transferencia',
        r'comprobante',
        r'recibo',
        r'factura',
        
        # Reclamos
        r'reclamo',
        r'queja',
        r'devoluc',
        r'reembolso'
    ]
    
    for pattern in sensitive_patterns:
        if re.search(pattern, text_normalized, re.IGNORECASE):
            return True
    
    return False


def is_cacheable_query(text: str, intent: str = None) -> bool:
    """
    Determina si una consulta puede cachearse.
    """
    # Nunca cachear consultas sensibles
    if is_sensitive_query(text):
        return False
    
    text_normalized = normalize_text(text)
    
    # Intents cacheables
    cacheable_intents = {"horario", "direccion", "ubicacion", "envios", "pagos", "catalogo"}
    if intent and intent.lower() in cacheable_intents:
        return True
    
    # Consultas genéricas cacheables
    cacheable_keywords = [
        "horario",
        "dónde quedan", "donde quedan",
        "dirección", "direccion",
        "ubicación", "ubicacion",
        "formas de pago",
        "hacen envíos", "hacen envios",
        "qué máquinas", "que maquinas",
        "qué marcas", "que marcas"
    ]
    
    for keyword in cacheable_keywords:
        if keyword in text_normalized:
            return True
    
    return False
