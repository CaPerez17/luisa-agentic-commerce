"""
Subagente de Análisis de Intención Primaria
Analiza el mensaje del usuario para determinar su intención principal y contexto.

Sistema mejorado con detección de:
- Confirmaciones/Negaciones
- Referencias a productos anteriores
- Comparaciones
- Seguimientos conversacionales
"""

from typing import Dict, List, Optional
from enum import Enum


class IntentType(Enum):
    """Tipos de intención primaria del usuario"""
    SALUDO = "saludo"
    DESPEDIDA = "despedida"
    SOLICITAR_FOTOS = "solicitar_fotos"
    PREGUNTAR_PRECIO = "preguntar_precio"
    PREGUNTAR_DISPONIBILIDAD = "preguntar_disponibilidad"
    BUSCAR_MAQUINA_FAMILIAR = "buscar_maquina_familiar"
    BUSCAR_MAQUINA_INDUSTRIAL = "buscar_maquina_industrial"
    BUSCAR_FILETEADORA = "buscar_fileteadora"
    BUSCAR_REPUESTOS = "buscar_repuestos"
    SOLICITAR_SERVICIO = "solicitar_servicio"
    SOLICITAR_INSTALACION = "solicitar_instalacion"
    SOLICITAR_ENVIO = "solicitar_envio"
    PREGUNTAR_FORMA_PAGO = "preguntar_forma_pago"
    CONFIRMAR_COMPRA = "confirmar_compra"
    BUSCAR_RECOMENDACION = "buscar_recomendacion"
    PREGUNTAR_CARACTERISTICAS = "preguntar_caracteristicas"
    PREGUNTAR_PROMOCIONES = "preguntar_promociones"
    # Nuevas intenciones para flujo conversacional
    CONFIRMAR = "confirmar"  # "si", "ok", "dale"
    NEGAR = "negar"  # "no", "otro", "diferente"
    REFERENCIA_PRODUCTO = "referencia_producto"  # "esa", "la primera", "la que dijiste"
    COMPARAR = "comparar"  # "cuál es mejor", "diferencia"
    PREGUNTAR_GARANTIA = "preguntar_garantia"
    PREGUNTAR_CAPACITACION = "preguntar_capacitacion"
    SOLICITAR_COTIZACION = "solicitar_cotizacion"
    INDEFINIDO = "indefinido"


class IntentAnalyzer:
    """
    Analizador de intención primaria del usuario.
    Sistema mejorado con detección contextual y patrones conversacionales.
    """
    
    def __init__(self):
        # Patrones de palabras clave por intención (ordenados por especificidad)
        self.intent_patterns = {
            # === INTENCIONES DE FLUJO CONVERSACIONAL (prioridad alta) ===
            IntentType.CONFIRMAR: [
                "si", "sí", "ok", "dale", "claro", "perfecto", "bueno", "vale",
                "está bien", "esta bien", "listo", "de acuerdo", "correcto",
                "exacto", "eso", "así es", "asi es", "afirmativo", "por favor",
                "muestrame", "muéstrame", "enséñame", "ensename", "a ver", 
                "quiero ver", "me interesa"
            ],
            IntentType.NEGAR: [
                "no", "nop", "nel", "negativo", "otro", "otra", "diferente",
                "distinto", "distinta", "no esa", "no ese", "ninguno", "ninguna",
                "no me interesa", "no gracias", "paso", "mejor no", "no ahora",
                "más adelante", "mas adelante", "luego", "después", "despues"
            ],
            IntentType.REFERENCIA_PRODUCTO: [
                "esa", "esa máquina", "esa maquina", "la que dijiste", "la que mencionaste",
                "la primera", "la segunda", "primera opción", "primera opcion",
                "segunda opción", "segunda opcion", "esa que me mostraste",
                "la de la foto", "la de la imagen", "la barata", "la cara",
                "la más económica", "la mas economica", "la mejor", "la premium"
            ],
            IntentType.COMPARAR: [
                "cuál es mejor", "cual es mejor", "diferencia", "diferencias",
                "comparar", "comparación", "comparacion", "versus", "vs",
                "qué diferencia", "que diferencia", "mejor entre", "entre estas",
                "cuál me conviene", "cual me conviene", "ventajas", "desventajas"
            ],
            
            # === INTENCIONES DE SALUDO/DESPEDIDA ===
            IntentType.SALUDO: [
                "hola", "buenos días", "buenos dias", "buenas tardes", "buenas noches", 
                "buen día", "buen dia", "buenas", "saludos", "qué tal", "que tal",
                "hey", "holi"
            ],
            IntentType.DESPEDIDA: [
                "gracias", "chau", "adiós", "adios", "nos vemos", "hasta luego",
                "perfecto gracias", "ok gracias", "listo gracias", "bye",
                "muchas gracias", "mil gracias", "te agradezco", "hasta pronto"
            ],
            
            # === INTENCIONES DE SOLICITUD DE INFORMACIÓN VISUAL ===
            IntentType.SOLICITAR_FOTOS: [
                "fotos", "foto", "imágenes", "imagenes", "imagen",
                "muéstrame", "muestrame", "ver fotos", "quiero ver",
                "tienes fotos", "tiene fotos", "muestra", "fotografía",
                "fotografia", "regalame fotos", "regálame fotos",
                "puedes mostrarme", "muéstrame fotos", "envíame foto", "enviame foto",
                "pásame fotos", "pasame fotos", "mándame", "mandame"
            ],
            
            # === INTENCIONES DE PRECIO Y DISPONIBILIDAD ===
            IntentType.PREGUNTAR_PRECIO: [
                "precio", "precios", "cuánto cuesta", "cuanto cuesta",
                "cuánto vale", "cuanto vale", "valor", "costo",
                "precio de", "precio de la", "precio del", "cuánto es",
                "cuanto es", "qué precio", "que precio", "a cómo", "a como",
                "sale a", "está a", "esta a"
            ],
            IntentType.PREGUNTAR_DISPONIBILIDAD: [
                "disponible", "disponibles", "tienen", "hay", "stock",
                "inventario", "cuántas", "cuántos", "existe", "tienen en",
                "hay en", "disponibilidad", "en existencia", "hay stock",
                "tienen stock", "manejan"
            ],
            
            # === INTENCIONES DE BÚSQUEDA DE PRODUCTOS ===
            IntentType.BUSCAR_MAQUINA_FAMILIAR: [
                "máquina familiar", "maquina familiar", "familiar",
                "familiares", "para casa", "doméstico", "domestico",
                "hogar", "uso personal", "máquinas familiares",
                "maquinas familiares", "uso doméstico", "uso domestico",
                "para el hogar", "casera"
            ],
            IntentType.BUSCAR_MAQUINA_INDUSTRIAL: [
                "máquina industrial", "maquina industrial", "industrial",
                "industriales", "taller", "producción", "produccion",
                "emprendimiento", "negocio", "máquinas industriales",
                "maquinas industriales", "recta industrial", "para taller",
                "para producir", "profesional", "trabajo pesado"
            ],
            IntentType.BUSCAR_FILETEADORA: [
                "fileteadora", "fileteadoras", "filetear", "orillos",
                "terminar prendas", "acabados", "overlock", "overlok",
                "remalladora", "remallado"
            ],
            IntentType.BUSCAR_REPUESTOS: [
                "repuestos", "repuesto", "accesorios", "accesorio",
                "piezas", "pieza", "partes", "aguja", "agujas",
                "hilo", "hilos", "pedal", "pie", "prensatela",
                "bobina", "canilla"
            ],
            
            # === INTENCIONES DE SERVICIO ===
            IntentType.SOLICITAR_SERVICIO: [
                "servicio", "reparación", "reparacion", "arreglar",
                "arreglo", "mantenimiento", "revisar", "revisión",
                "revision", "no funciona", "se dañó", "se dano",
                "está mala", "esta mala", "no prende", "no cose",
                "tiene problemas"
            ],
            IntentType.SOLICITAR_INSTALACION: [
                "instalación", "instalacion", "instalar", "instalen",
                "montar", "montaje", "dejan funcionando", "dejen funcionando",
                "configurar", "poner a funcionar", "armado"
            ],
            IntentType.SOLICITAR_ENVIO: [
                "envío", "envio", "enviar", "llegar", "entrega",
                "entregar", "envían", "envian", "hacen envío",
                "hacen envio", "a domicilio", "domicilio", "despacho",
                "mandan", "mandarlo", "tiempo de entrega", "cuándo llega",
                "cuando llega"
            ],
            
            # === INTENCIONES DE PAGO Y COMPRA ===
            IntentType.PREGUNTAR_FORMA_PAGO: [
                "forma de pago", "formas de pago", "cómo pagar",
                "como pagar", "pago", "pagando", "addi", "sistecrédito",
                "sistecredito", "crédito", "credito", "financiación",
                "financiacion", "cuotas", "a plazos", "contado",
                "efectivo", "transferencia", "tarjeta", "nequi", "daviplata"
            ],
            IntentType.CONFIRMAR_COMPRA: [
                "comprar", "quiero comprar", "me interesa comprar", 
                "necesito comprar", "voy a comprar", "ya hice el pago",
                "pagué", "pague", "lo quiero", "la quiero", "me la llevo",
                "va", "listo para comprar", "cómo compro", "como compro"
            ],
            IntentType.SOLICITAR_COTIZACION: [
                "cotización", "cotizacion", "cotizar", "cotizame",
                "pasame cotización", "pásame cotización", "factura proforma",
                "presupuesto formal"
            ],
            
            # === INTENCIONES DE ASESORÍA ===
            IntentType.BUSCAR_RECOMENDACION: [
                "recomendación", "recomendacion", "recomiendas",
                "recomienda", "qué me recomiendas", "que me recomiendas",
                "me recomiendas", "recomiéndame", "recomiendame",
                "qué máquina", "que maquina", "cuál máquina", "cual maquina",
                "sugieres", "sugerencia", "aconsejas", "qué necesito",
                "que necesito", "cuál es la mejor", "cual es la mejor"
            ],
            IntentType.PREGUNTAR_CARACTERISTICAS: [
                "características", "caracteristicas", "especificaciones",
                "qué tiene", "que tiene", "incluye", "trae", "viene con",
                "specs", "detalles técnicos", "detalles tecnicos",
                "ficha técnica", "ficha tecnica", "datos", "info",
                "información técnica", "informacion tecnica"
            ],
            IntentType.PREGUNTAR_GARANTIA: [
                "garantía", "garantia", "garantizado", "cobertura",
                "respaldo", "soporte", "servicio técnico", "servicio tecnico",
                "postventa", "post venta", "si se daña", "si se dana"
            ],
            IntentType.PREGUNTAR_CAPACITACION: [
                "capacitación", "capacitacion", "enseñan", "ensenan",
                "curso", "cursos", "aprendo", "aprender", "clases",
                "tutorial", "cómo usar", "como usar", "instrucciones"
            ],
            
            # === INTENCIONES DE PROMOCIONES ===
            IntentType.PREGUNTAR_PROMOCIONES: [
                "promoción", "promocion", "promociones", "promociones de navidad",
                "promoción navideña", "promocion navidena", "oferta", "ofertas",
                "descuento", "descuentos", "rebaja", "rebajas", "especial",
                "tienen promoción", "hay promoción", "promoción navidad",
                "ganga", "oportunidad", "liquidación", "liquidacion",
                "precio especial"
            ]
        }
        
        # Patrones de confirmación contextual (para respuestas cortas)
        self.confirmation_patterns = [
            "si", "sí", "ok", "dale", "claro", "perfecto", "bueno", "vale",
            "está bien", "esta bien", "listo", "de acuerdo", "correcto",
            "exacto", "eso", "así es", "asi es", "va", "oks", "okok"
        ]
        
        # Patrones de negación contextual
        self.negation_patterns = [
            "no", "nop", "nel", "negativo", "no gracias", "paso",
            "mejor no", "no ahora", "luego", "después", "despues"
        ]
    
    def analyze(self, text: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Analiza el mensaje y determina la intención primaria.
        Sistema mejorado con detección contextual.
        
        Returns:
            Dict con:
                - intent: IntentType
                - confidence: float (0-1)
                - context: Dict con información adicional extraída
                - requires_asset: bool (si necesita mostrar asset)
                - requires_handoff: bool (si requiere escalamiento humano)
                - is_confirmation: bool (si es confirmación contextual)
                - is_negation: bool (si es negación contextual)
                - last_luisa_topic: str (tema del último mensaje de Luisa)
        """
        text_lower = text.lower().strip()
        conversation_history = conversation_history or []
        
        # Primero: detectar si es respuesta corta (confirmación/negación contextual)
        is_short_response = len(text_lower.split()) <= 3
        is_confirmation = False
        is_negation = False
        last_luisa_topic = None
        
        # Analizar el último mensaje de Luisa para contexto
        if conversation_history:
            luisa_messages = [msg for msg in conversation_history if msg.get("sender") == "luisa"]
            if luisa_messages:
                last_luisa_msg = luisa_messages[-1].get("text", "").lower()
                last_luisa_topic = self._detect_luisa_topic(last_luisa_msg)
        
        # Detectar confirmación/negación contextual en respuestas cortas
        if is_short_response:
            if any(pattern in text_lower for pattern in self.confirmation_patterns):
                is_confirmation = True
            if any(pattern in text_lower for pattern in self.negation_patterns):
                is_negation = True
        
        # Detectar intención primaria
        intent_scores = {}
        for intent_type, patterns in self.intent_patterns.items():
            score = 0
            matches = []
            for pattern in patterns:
                if pattern in text_lower:
                    # Dar más peso a matches exactos de frases completas
                    if " " in pattern:
                        score += 2  # Frases completas valen más
                    else:
                        score += 1
                    matches.append(pattern)
            
            if score > 0:
                # Normalizar score por cantidad de patrones con un factor logarítmico
                # para no penalizar intenciones con muchos patrones
                import math
                normalized_score = score / (1 + math.log(len(patterns)))
                intent_scores[intent_type] = {
                    "score": normalized_score,
                    "matches": matches,
                    "raw_score": score
                }
        
        # Determinar intención primaria (mayor score)
        primary_intent = IntentType.INDEFINIDO
        confidence = 0.0
        
        if intent_scores:
            # Ordenar por score y seleccionar el mejor
            sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1]["score"], reverse=True)
            primary_intent = sorted_intents[0][0]
            confidence = sorted_intents[0][1]["score"]
            
            # Si es respuesta corta y detectamos confirmación, ajustar intención según contexto
            if is_short_response and is_confirmation and last_luisa_topic:
                # Si la confirmación NO es una intención fuerte, usar contexto
                if confidence < 0.5 or primary_intent in [IntentType.CONFIRMAR, IntentType.INDEFINIDO]:
                    primary_intent = IntentType.CONFIRMAR
                    confidence = 0.8
        
        # Si no hay ninguna intención y es respuesta corta
        if primary_intent == IntentType.INDEFINIDO and is_short_response:
            if is_confirmation:
                primary_intent = IntentType.CONFIRMAR
                confidence = 0.7
            elif is_negation:
                primary_intent = IntentType.NEGAR
                confidence = 0.7
        
        # Extraer contexto adicional
        context = self._extract_context(text_lower, conversation_history, primary_intent)
        
        # Determinar si requiere asset
        requires_asset = primary_intent in [
            IntentType.SOLICITAR_FOTOS,
            IntentType.BUSCAR_MAQUINA_FAMILIAR,
            IntentType.BUSCAR_MAQUINA_INDUSTRIAL,
            IntentType.BUSCAR_FILETEADORA,
            IntentType.BUSCAR_RECOMENDACION,
            IntentType.PREGUNTAR_CARACTERISTICAS,
            IntentType.REFERENCIA_PRODUCTO
        ]
        
        # Si es confirmación y el último tema de Luisa era promociones, requiere asset
        if is_confirmation and last_luisa_topic == "promocion":
            requires_asset = True
        
        # Determinar si requiere handoff
        requires_handoff = primary_intent in [
            IntentType.PREGUNTAR_PRECIO,
            IntentType.PREGUNTAR_DISPONIBILIDAD,
            IntentType.SOLICITAR_SERVICIO,
            IntentType.SOLICITAR_INSTALACION,
            IntentType.SOLICITAR_ENVIO,
            IntentType.PREGUNTAR_FORMA_PAGO,
            IntentType.CONFIRMAR_COMPRA,
            IntentType.SOLICITAR_COTIZACION
        ]
        
        return {
            "intent": primary_intent,
            "confidence": confidence,
            "context": context,
            "requires_asset": requires_asset,
            "requires_handoff": requires_handoff,
            "is_confirmation": is_confirmation,
            "is_negation": is_negation,
            "last_luisa_topic": last_luisa_topic,
            "intent_scores": {k.value: v["score"] for k, v in intent_scores.items()}
        }
    
    def _detect_luisa_topic(self, luisa_msg: str) -> Optional[str]:
        """Detecta el tema del último mensaje de Luisa para contexto"""
        luisa_lower = luisa_msg.lower()
        
        # Promociones
        if any(word in luisa_lower for word in ["promoción", "promocion", "ofertas disponibles", 
                                                  "promociones navideñas", "te muestro las ofertas"]):
            return "promocion"
        
        # Especificaciones
        if any(word in luisa_lower for word in ["especificaciones", "características", "caracteristicas"]):
            return "especificaciones"
        
        # Fotos/Imágenes
        if any(word in luisa_lower for word in ["imagen", "foto", "te muestro"]):
            return "fotos"
        
        # Diagnóstico de tipo
        if any(word in luisa_lower for word in ["familiar o industrial", "¿buscas máquina", "¿buscas maquina"]):
            return "diagnostico_tipo"
        
        # Diagnóstico de uso
        if any(word in luisa_lower for word in ["qué vas a fabricar", "que vas a fabricar"]):
            return "diagnostico_uso"
        
        # Diagnóstico de volumen
        if any(word in luisa_lower for word in ["producción constante", "produccion constante", "pocas unidades"]):
            return "diagnostico_volumen"
        
        # Cierre/Ciudad
        if any(word in luisa_lower for word in ["qué ciudad", "que ciudad", "dónde te encuentras", "donde te encuentras"]):
            return "diagnostico_ciudad"
        
        # Handoff
        if any(word in luisa_lower for word in ["te llamemos", "agendar", "conectarte con"]):
            return "handoff"
        
        return None
    
    def _extract_context(self, text_lower: str, history: List[Dict], intent: IntentType) -> Dict:
        """
        Extrae contexto adicional del mensaje y el historial.
        Sistema mejorado con más categorías y detección.
        """
        context = {
            "tipo_maquina": None,
            "categoria": None,
            "uso": None,
            "ciudad": None,
            "presupuesto": None,
            "volumen": None,
            "marca_mencionada": None,
            "modelo_mencionado": None
        }
        
        # Detectar tipo de máquina
        if any(word in text_lower for word in ["familiar", "familiares", "casa", "doméstico", "domestico", "hogar", "personal"]):
            context["tipo_maquina"] = "familiar"
            context["categoria"] = "familiar"
        elif any(word in text_lower for word in ["fileteadora", "fileteadoras", "overlock", "overlok"]):
            # Fileteadoras pueden ser familiares o industriales
            if any(word in text_lower for word in ["industrial", "industriales", "taller"]):
                context["tipo_maquina"] = "industrial"
                context["categoria"] = "fileteadora_industrial"
            else:
                context["tipo_maquina"] = "familiar"
                context["categoria"] = "fileteadora_familiar"
        elif any(word in text_lower for word in ["industrial", "industriales", "taller", "producción", "produccion", "emprendimiento", "negocio"]):
            context["tipo_maquina"] = "industrial"
            context["categoria"] = "recta_industrial_mecatronica"
        
        # Detectar uso específico
        usos = {
            "ropa": ["ropa", "prendas", "camisas", "pantalones", "vestidos", "blusas", "faldas", "confección", "confeccion"],
            "gorras": ["gorras", "gorra", "cachuchas", "sombreros"],
            "calzado": ["calzado", "zapatos", "zapatillas", "tenis", "botas", "sandalias"],
            "accesorios": ["accesorios", "accesorio", "bolsos", "carteras", "morrales", "billeteras"],
            "hogar": ["cortinas", "mantelería", "manteleria", "cojines", "lencería hogar", "lenceria hogar"],
            "uniformes": ["uniformes", "dotación", "dotacion", "overoles"],
            "cuero": ["cuero", "cueros", "marroquinería", "marroquineria"]
        }
        for uso_key, palabras in usos.items():
            if any(word in text_lower for word in palabras):
                context["uso"] = uso_key
                break
        
        # Detectar ciudad (Colombia)
        ciudades = {
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
        for ciudad_key, ciudad_val in ciudades.items():
            if ciudad_key in text_lower:
                context["ciudad"] = ciudad_val
                break
        
        # Detectar volumen de producción
        if any(word in text_lower for word in ["constante", "muchas", "taller", "producción", "produccion", "continua", "diario", "negocio"]):
            context["volumen"] = "alto"
        elif any(word in text_lower for word in ["pocas", "poco", "ocasional", "esporádico", "esporadico", "hobby", "arreglos"]):
            context["volumen"] = "bajo"
        
        # Detectar marca/modelo
        marcas_modelos = {
            "kingter": ("KINGTER", "KT-D3"),
            "kt-d3": ("KINGTER", "KT-D3"),
            "ktd3": ("KINGTER", "KT-D3"),
            "kansew": ("KANSEW", None),
            "ks-8800": ("KANSEW", "KS-8800"),
            "ks8800": ("KANSEW", "KS-8800"),
            "ssgemsy": ("SSGEMSY", "SG8802E"),
            "sg8802e": ("SSGEMSY", "SG8802E"),
            "singer": ("SINGER", None),
            "heavy duty": ("SINGER", "Heavy Duty"),
            "union": ("UNION", None),
            "un300": ("UNION", "UN300")
        }
        for keyword, (marca, modelo) in marcas_modelos.items():
            if keyword in text_lower:
                context["marca_mencionada"] = marca
                if modelo:
                    context["modelo_mencionado"] = modelo
                break
        
        # Detectar presupuesto
        presupuestos = ["1.2", "1.3", "1.4", "1.5", "millón", "millones", "presupuesto", 
                        "1200", "1300", "1400", "1500", "un millón", "dos millones"]
        if any(word in text_lower for word in presupuestos):
            context["presupuesto"] = True
        
        # Usar historial si no hay contexto claro
        if not context["tipo_maquina"] and history:
            for msg in reversed(history[-6:]):  # Últimos 6 mensajes
                msg_text = msg.get("text", "").lower()
                if any(word in msg_text for word in ["familiar", "familiares", "casa", "hogar"]):
                    context["tipo_maquina"] = "familiar"
                    break
                elif any(word in msg_text for word in ["industrial", "industriales", "taller", "producción"]):
                    context["tipo_maquina"] = "industrial"
                    break
        
        return context


# Instancia global del analizador
intent_analyzer = IntentAnalyzer()

