"""
Servicio de generación de respuestas.
Integra reglas existentes + OpenAI como fallback opcional.
"""
import time
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import httpx

from app.config import (
    OPENAI_ENABLED,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_TEMPERATURE,
    OPENAI_TIMEOUT_SECONDS,
    BASE_DIR
)
from app.rules.business_guardrails import (
    is_business_related,
    get_off_topic_response,
    is_cacheable_query,
    classify_message_type,
    MessageType,
    get_response_for_message_type
)
from app.services.cache_service import get_cached_response, cache_response
from app.services.context_service import (
    format_context_for_prompt,
    format_history_for_prompt
)
from app.logging_config import logger


# Versión actual del prompt
PROMPT_VERSION = "v1"


def load_system_prompt() -> str:
    """Carga el prompt del sistema desde archivo."""
    prompt_path = BASE_DIR / "app" / "prompts" / f"luisa_system_prompt_{PROMPT_VERSION}.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error("Error cargando prompt", error=str(e))
        return ""


async def generate_openai_response(
    message: str,
    context: Dict[str, Any],
    history: List[Dict[str, Any]]
) -> Tuple[Optional[str], int]:
    """
    Genera respuesta usando OpenAI.
    
    Returns:
        Tuple[respuesta o None, latencia_ms]
    """
    from app.config import OPENAI_MAX_INPUT_CHARS

    if not OPENAI_ENABLED or not OPENAI_API_KEY:
        return None, 0

    start_time = time.time()

    # Preparar prompt
    system_prompt = load_system_prompt()
    if not system_prompt:
        return None, 0

    # Insertar contexto e historial
    system_prompt = system_prompt.replace("{context}", format_context_for_prompt(context))
    system_prompt = system_prompt.replace("{history}", format_history_for_prompt(history))
    system_prompt = system_prompt.replace("{message}", message)

    # Limitar caracteres de entrada para controlar costos
    if len(system_prompt) > OPENAI_MAX_INPUT_CHARS:
        # Recortar manteniendo el mensaje del usuario
        user_message = f"Contexto del cliente: {message}"
        context_summary = f"Cliente pregunta sobre máquinas de coser. Contexto: {context.get('tipo_maquina', 'desconocido')} - {context.get('uso', 'desconocido')}"

        # Construir prompt más corto
        system_prompt = f"""Eres Luisa, asesora comercial de Almacén y Taller El Sastre en Montería, Colombia.

NEGOCIO:
- Vendemos máquinas de coser familiares e industriales
- Servicio técnico y asesoría

ESTILO DE RESPUESTA (OBLIGATORIO):
1. Máximo 3 frases cortas
2. Siempre terminar con UNA pregunta cerrada (máximo 2 opciones)

{context_summary}

MENSAJE DEL CLIENTE:
{message}"""

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT_SECONDS) as client:
            response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "max_tokens": OPENAI_MAX_OUTPUT_TOKENS,
                "temperature": OPENAI_TEMPERATURE
            }
            )

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                data = response.json()
                text = data["choices"][0]["message"]["content"].strip()

                # Validar que no mencione ser IA/bot
                forbidden = ["soy un bot", "soy una ia", "asistente virtual", "soy un asistente"]
                if any(f in text.lower() for f in forbidden):
                    logger.warning("OpenAI generó texto prohibido", text=text[:100])
                    return None, latency_ms

                logger.info(
                    "OpenAI respuesta generada",
                    latency_ms=latency_ms,
                    tokens=data.get("usage", {}).get("total_tokens", 0)
                )
                return text, latency_ms
            else:
                logger.error(
                    "Error OpenAI",
                    status=response.status_code,
                    body=response.text[:200]
                )
                return None, latency_ms

    except httpx.TimeoutException:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning("OpenAI timeout", latency_ms=latency_ms)
        return None, latency_ms
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error("Error llamando OpenAI", error=str(e))
        return None, latency_ms


def generate_openai_response_sync(
    message: str,
    context: Dict[str, Any],
    history: List[Dict[str, Any]]
) -> Tuple[Optional[str], int]:
    """
    Versión síncrona de generate_openai_response para uso en endpoints sync.
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si ya hay un loop corriendo, crear uno nuevo en un thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_openai_response(message, context, history)
                )
            return future.result(timeout=OPENAI_TIMEOUT_SECONDS + 2)
        else:
            return loop.run_until_complete(
            generate_openai_response(message, context, history)
            )
    except Exception as e:
        logger.error("Error en generate_openai_response_sync", error=str(e))
        return None, 0


class ResponseGenerator:
    """
    Generador de respuestas que combina:
    1. Cache para FAQs
    2. Guardrails para mensajes fuera del negocio
    3. Reglas existentes (del main.py legacy)
    4. OpenAI como fallback (opcional)
    """
    
    def __init__(self):
        self.openai_calls = 0
        self.cache_hits = 0
        self.rule_hits = 0
    
    def generate(
        self,
        message: str,
        context: Dict[str, Any],
        history: List[Dict[str, Any]],
        intent: Optional[str] = None,
        needs_escalation: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Genera una respuesta para el mensaje.
        
        Returns:
            Tuple[respuesta, metadata]
            metadata incluye: cache_hit, openai_called, prompt_version, business_related
        """
        metadata = {
            "cache_hit": False,
            "openai_called": False,
            "prompt_version": None,
            "business_related": True,
            "latency_ms": 0
        }
        
        start_time = time.time()
        
        # Paso 1: Verificar si es del negocio
        is_business, reason = is_business_related(message)
        metadata["business_related"] = is_business
        
        if not is_business:
            response = get_off_topic_response()
            metadata["latency_ms"] = int((time.time() - start_time) * 1000)
            return response, metadata
        
        # Paso 2: Verificar cache para FAQs
        if is_cacheable_query(message, intent):
            cached = get_cached_response(message)
            if cached:
                metadata["cache_hit"] = True
                self.cache_hits += 1
                metadata["latency_ms"] = int((time.time() - start_time) * 1000)
                return cached, metadata
        
        # Paso 3: Intentar generar con reglas existentes
        # (Esto se integra con la lógica del main.py legacy a través del adaptador)
        # Por ahora, solo usamos OpenAI si está habilitado y no tenemos respuesta de reglas
        
        # Paso 4: OpenAI como fallback (si está habilitado)
        if OPENAI_ENABLED and not needs_escalation:
            openai_response, openai_latency = generate_openai_response_sync(
            message, context, history
            )
            
            if openai_response:
                metadata["openai_called"] = True
                metadata["prompt_version"] = PROMPT_VERSION
                metadata["latency_ms"] = openai_latency
                self.openai_calls += 1
                
                # Cachear si es FAQ
                if is_cacheable_query(message, intent):
                    cache_response(message, openai_response)
        
            return openai_response, metadata
        
        # Si llegamos aquí, no tenemos respuesta
        # El main.py legacy manejará esto con sus reglas
        metadata["latency_ms"] = int((time.time() - start_time) * 1000)
        return "", metadata
    
    def stats(self) -> Dict[str, int]:
        """Retorna estadísticas del generador."""
        return {
            "openai_calls": self.openai_calls,
            "cache_hits": self.cache_hits,
            "rule_hits": self.rule_hits
        }


# Instancia global
response_generator = ResponseGenerator()


def try_openai_enhancement(
    message: str,
    context: Dict[str, Any],
    history: List[Dict[str, Any]],
    rules_response: str
) -> Tuple[str, bool]:
    """
    Intenta mejorar una respuesta de reglas con OpenAI.
    Solo si la respuesta de reglas es genérica.

    Returns:
        Tuple[respuesta_final, openai_used]
    """
    if not OPENAI_ENABLED:
        return rules_response, False

    # Solo mejorar respuestas genéricas cortas
    generic_patterns = [
        "¿buscas máquina familiar o industrial?",
        "¿qué vas a fabricar?",
        "¿producción constante o pocas unidades?"
    ]

    is_generic = any(p in rules_response.lower() for p in generic_patterns)

    if not is_generic:
        return rules_response, False

    # Verificar que es del negocio
    is_business, _ = is_business_related(message)
    if not is_business:
        return rules_response, False

    # Intentar con OpenAI
    openai_response, _ = generate_openai_response_sync(message, context, history)

    if openai_response:
        return openai_response, True

    return rules_response, False


def should_call_openai(intent: str, message_type: MessageType, text: str, context: dict, cache_hit: bool) -> bool:
    """
    Determina si se debe llamar a OpenAI basado en reglas estrictas de gating.

    Solo retorna True si:
    - OPENAI_ENABLED == true
    - message_type == BUSINESS_CONSULT
    - intent NO está en FAQ simples
    - cache_hit == false
    """
    if not OPENAI_ENABLED:
        return False

    if message_type != MessageType.BUSINESS_CONSULT:
        return False

    faq_intents = {
        "saludo", "despedida", "cierre", "envios", "pagos", "horarios",
        "direccion", "ubicacion", "telefono", "contacto", "promociones"
    }

    if intent in faq_intents:
        return False

    if cache_hit:
        return False

    has_robust_deterministic = context.get("has_robust_deterministic", False)
    if has_robust_deterministic:
        return False

    return True


def ensure_next_step_question(text: str, intent: str, context: dict) -> str:
    """
    Post-procesador: Asegura que la respuesta termine con una pregunta cerrada.
    """
    if not text or intent in {"saludo", "despedida", "confirmacion_pago", "cierre"}:
        return text

    if "?" in text:
        return text

    intent_questions = {
        "buscar_maquina_industrial": "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?",
        "buscar_maquina_familiar": "¿La necesitas para uso en casa o para emprendimiento?",
        "preguntar_precio": "¿Buscas máquina familiar (desde $400.000) o industrial (desde $1.230.000)?",
        "envios": "¿A qué ciudad o municipio sería el envío?",
        "pagos": "¿Prefieres Addi o Sistecrédito para financiamiento?",
        "repuesto_accesorio": "¿Me confirmas la marca de tu máquina o me envías foto de la placa?",
        "asesoria_negocio": "¿Vas a producir de forma ocasional o constante?",
        "horario": "¿Necesitas más información sobre ubicación o contacto?",
        "ubicacion": "¿Quieres que te guíe con direcciones o prefieres envío?",
        "catalogo": "¿Te intereso alguna máquina específica o necesitas recomendaciones?",
        "info_general": "¿Necesitas información sobre máquinas, repuestos o servicio técnico?"
    }

    question = intent_questions.get(intent)
    if question:
        if text.endswith(".") or text.endswith("!"):
            return f"{text} {question}"
        else:
            return f"{text}. {question}"

    return text


def _generate_fallback_response(text: str, context: dict, intent_result: dict) -> str:
    """Genera respuesta fallback."""
    intent = intent_result.get("intent", "")
    confidence = intent_result.get("confidence", 0)

    if confidence > 0.7:
        if intent == "buscar_maquina_industrial":
            return "Tenemos máquinas industriales desde $1.230.000. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        elif intent == "buscar_maquina_familiar":
            return "Tenemos máquinas familiares desde $400.000. ¿La necesitas para uso en casa o para emprendimiento?"

    return "¡Hola! 😊 ¿Buscas máquina familiar, industrial o repuesto?"


def _build_decision_path(
    business_related: bool,
    cache_checked: bool,
    asset_selected: bool,
    openai_called: bool,
    handoff_triggered: bool,
    question_appended: bool = False,
    message_type: str = None,
    openai_block_reason: str = None
) -> str:
    """Construye string de decision path para trazabilidad."""
    path_parts = []

    if message_type:
        path_parts.append(f"msg_{message_type}")

    if business_related:
        path_parts.append("business_ok")
    else:
        path_parts.append("business_rejected")
        return "->".join(path_parts)

    if cache_checked:
        path_parts.append("cache_hit")
        return "->".join(path_parts)

    path_parts.append("cache_miss")
    
    if asset_selected:
        path_parts.append("asset_selected")
    else:
        path_parts.append("asset_skipped")

    if openai_called:
        path_parts.append("openai_called_fallback")
    elif openai_block_reason:
        path_parts.append(f"openai_{openai_block_reason}")
    else:
        path_parts.append("openai_skipped")

    if handoff_triggered:
        path_parts.append("handoff_triggered")

    if question_appended:
        path_parts.append("question_appended")
    
    return "->".join(path_parts)


def build_response(
    text: str,
    conversation_id: str,
    channel: str = "api",
    customer_number: Optional[str] = None
) -> Dict[str, Any]:
    """
    Función principal del pipeline nuevo.
    Reemplaza generate_response() del legacy.

    Pipeline:
    1. business_guardrails.is_business_related (barato)
    2. cache_service (si aplica)
    3. intent/context/handoff/asset matching (reglas determinísticas)
    4. OpenAI SOLO como fallback de redacción/ventas si:
       - is_business_related==true
       - no hay respuesta determinística buena
       - OPENAI_ENABLED==true
    5. trace_service siempre guarda interacción
    
    Returns:
        {
            "text": "...",
            "asset": {...} opcional,
            "routed_notification": {...} opcional
        }
    """
    import time
    from app.services.trace_service import trace_interaction
    from app.services.context_service import extract_context_from_history
    from app.services.intent_service import analyze_intent
    from app.services.asset_service import select_catalog_asset
    from app.services.handoff_service import process_handoff
    from app.models.database import (
        create_or_update_conversation,
        save_message,
        get_conversation_history,
        get_conversation_mode
    )

    # Medición de latencia real con perf_counter
    start_time = time.perf_counter()

    # Inicializar respuesta
    result = {
        "text": "",
        "asset": None,
        "routed_notification": None
    }

    # Crear/obtener conversación
    create_or_update_conversation(conversation_id, customer_number, channel)

    # Verificar modo sombra
    mode = get_conversation_mode(conversation_id)
    if mode == "HUMAN_ACTIVE":
        # En modo humano, solo registrar (no responder)
        result["text"] = "En espera de respuesta humana"
        return result
    
    # Guardar mensaje del cliente
    save_message(conversation_id, text, "customer")

    # Obtener historial
    history = get_conversation_history(conversation_id)

    # Usar trace context manager
    with trace_interaction(conversation_id, channel, customer_number) as tracer:
            tracer.raw_text = text
            tracer.normalized_text = text.lower().strip()

            # Paso 1: Clasificar tipo de mensaje
            message_type = classify_message_type(text)
            tracer.message_type = message_type.value  # Guardar en trazas

            # Paso 2: Guardrails - ¿Es del negocio?
            is_business, reason = is_business_related(text)
            tracer.business_related = is_business

            # Respuestas especiales para tipos específicos de mensaje
            if message_type == MessageType.EMPTY_OR_GIBBERISH:
                result["text"] = get_response_for_message_type(message_type, text)
                tracer.decision_path = "->gibberish_handled"
                return result

            if message_type == MessageType.NON_BUSINESS:
                result["text"] = get_response_for_message_type(message_type, text)
                tracer.decision_path = "->non_business_handled"
                return result
    
            if not is_business:
                # Respuesta fija para fuera del negocio
                result["text"] = get_off_topic_response()
                return result
    
            # Paso 2: Intent y contexto
            intent_result = analyze_intent(text, history)
            tracer.intent = intent_result.get("intent")
            context = extract_context_from_history(history)

            # Paso 3: Verificar cache para FAQs (solo si no es saludo)
            cache_checked = False
            if tracer.intent not in ["saludo", "cierre", "despedida", "info_general"] and is_cacheable_query(text, tracer.intent):
                cached = get_cached_response(text)
                if cached:
                    tracer.cache_hit = True
                    result["text"] = cached
                    cache_checked = True

            # Paso 4: Seleccionar asset del catálogo (SOLO si intención lo permite)
            asset_selected = False
            handoff_required = False  # Inicializar
            if _should_select_asset(tracer.intent, text, context):
                catalog_item, handoff_required = select_catalog_asset(text, context)
                if catalog_item:
                    tracer.selected_asset_id = catalog_item.get("image_id")
                    result["asset"] = {
                        "image_id": catalog_item["image_id"],
                        "asset_url": f"/api/assets/{catalog_item['image_id']}",
                        "type": "image"
                    }
                    asset_selected = True

            # Paso 5: Verificar handoff
            handoff_triggered = False
            if handoff_required:
                # Procesar handoff
                handoff_success, notification_text, team = process_handoff(
                    conversation_id=conversation_id,
                    text=text,
                    context=context,
                    customer_phone=customer_number,
                    history=history
                )
                if handoff_success:
                    tracer.routed_team = team.value if team else None
                    result["routed_notification"] = {
                        "team": team.value if team else "comercial",
                        "text": notification_text
                    }
                    handoff_triggered = True

            # Paso 6: Generar respuesta de texto
            if not result["text"]:
                # Lógica especial para saludos
                if tracer.intent == "saludo":
                    result["text"] = "¡Hola! 😊 ¿Buscas máquina familiar, industrial o repuesto?"
                else:
                    # Determinar si se puede llamar OpenAI con gating estricto
                    can_call_openai = should_call_openai(
                        intent=tracer.intent,
                        message_type=message_type,
                        text=text,
                        context=context,
                        cache_hit=tracer.cache_hit
                    )

                    if can_call_openai:
                        # Llamar OpenAI con límites de input
                        text_for_openai = text[:OPENAI_MAX_INPUT_CHARS]
                        history_for_openai = history[-6:] if history else []  # Máximo 6 turnos

                        openai_response, openai_latency = generate_openai_response_sync(
                            text_for_openai, context, history_for_openai
                        )

                        if openai_response:
                            tracer.openai_called = True
                            tracer.prompt_version = PROMPT_VERSION
                            result["text"] = openai_response

                            # Cachear si es FAQ
                            if is_cacheable_query(text, tracer.intent):
                                cache_response(text, result["text"])
                        else:
                            # OpenAI falló, marcar como bloqueado por error
                            tracer.decision_path = tracer.decision_path.replace("->openai_called_fallback", "->openai_error")
                    else:
                        # Determinar por qué se bloqueó OpenAI
                        block_reason = "unknown"
                        if message_type != MessageType.BUSINESS_CONSULT:
                            block_reason = f"blocked_{message_type.value}"
                        elif tracer.intent in ["envios", "pagos", "horarios", "direccion", "ubicacion"]:
                            block_reason = "blocked_faq"
                        elif tracer.cache_hit:
                            block_reason = "blocked_cache_hit"
                        elif context.get("has_robust_deterministic"):
                            block_reason = "blocked_deterministic"

                        tracer.decision_path = f"{tracer.decision_path}->openai_{block_reason}"

                    # Si todavía no hay respuesta, usar fallback básico
                    if not result["text"]:
                        result["text"] = _generate_fallback_response(text, context, intent_result)

            # Paso 7: Ajustar asset si no fue incluido en respuesta final
            if result["asset"] and not asset_selected:
                # Si seleccionamos asset pero luego no lo incluimos, quitarlo de tracer
                tracer.selected_asset_id = None
                result["asset"] = None

            # Paso 8: Post-procesar para asegurar pregunta de siguiente paso
            original_text = result["text"]
            result["text"] = ensure_next_step_question(result["text"], tracer.intent, context)
            question_appended = original_text != result["text"]

            # Paso 9: Calcular decision_path para trazabilidad
            decision_path = _build_decision_path(
                is_business, cache_checked, asset_selected, tracer.openai_called, handoff_triggered,
                question_appended, message_type.value, None
            )
            tracer.decision_path = decision_path

            # Paso 10: Calcular response_len_chars
            tracer.response_len_chars = len(result["text"]) if result["text"] else 0

            # Guardar respuesta de Luisa
            if result["text"]:
                save_message(conversation_id, result["text"], "luisa")
    
    return result


def _should_select_asset(intent: str, text: str, context: dict) -> bool:
    """
    Determina si debe seleccionar asset basado en intención y señales de producto.
    """
    # Intenciones que PERMITEN selección de assets
    asset_allowed_intents = {
        "venta_maquina", "asesoria_negocio", "repuesto_accesorio",
        "soporte_tecnico", "garantia", "instalacion_servicio",
        "comparacion_maquinas", "buscar_maquina_familiar", "buscar_maquina_industrial",
        "buscar_fileteadora", "solicitar_fotos", "preguntar_precio"
    }

    if intent not in asset_allowed_intents:
        return False

    # Verificar señales de producto en texto o contexto
    from app.rules.keywords import (
        contains_any, MAQUINA_FAMILIAR, MAQUINA_INDUSTRIAL, FILETEADORA,
        USO_ROPA, USO_GORRAS, USO_CALZADO, USO_ACCESORIOS, USO_CUERO,
        REPUESTOS, MARCAS_MODELOS
    )

    # Señales de producto
    product_signals = (
        MAQUINA_FAMILIAR | MAQUINA_INDUSTRIAL | FILETEADORA |
        USO_ROPA | USO_GORRAS | USO_CALZADO | USO_ACCESORIOS | USO_CUERO |
        REPUESTOS
    )

    has_product_signals = contains_any(text, product_signals)

    # Verificar marcas/modelos específicos
    has_brand_signals = any(keyword in text.lower() for keyword in MARCAS_MODELOS.keys())

    # Verificar contexto
    has_context_signals = (
        context.get("tipo_maquina") or
        context.get("marca_interes") or
        context.get("modelo_interes") or
        context.get("uso")
    )

    return has_product_signals or has_brand_signals or has_context_signals


def _generate_fallback_response(text: str, context: dict, intent_result: dict) -> str:
    """
    Genera respuesta fallback cuando no hay respuesta específica.
    """
    intent = intent_result.get("intent", "")
    confidence = intent_result.get("confidence", 0)

    # Si hay confianza alta en el intent, usar respuesta específica
    if confidence > 0.7:
        if intent == "buscar_maquina_industrial":
            return "Tenemos máquinas industriales desde $1.230.000. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        elif intent == "buscar_maquina_familiar":
            return "Tenemos máquinas familiares desde $400.000. ¿La necesitas para uso en casa o para emprendimiento?"

    # Respuesta genérica
    return "¡Hola! 😊 ¿Buscas máquina familiar, industrial o repuesto?"


def should_call_openai(intent: str, message_type: MessageType, text: str, context: dict, cache_hit: bool) -> bool:
    """
    Determina si se debe llamar a OpenAI basado en reglas estrictas de gating.

    Solo retorna True si:
    - OPENAI_ENABLED == true
    - message_type == BUSINESS_CONSULT
    - intent NO está en FAQ simples
    - cache_hit == false
    - y no hay respuesta determinística robusta
    """
    # OpenAI debe estar habilitado
    if not OPENAI_ENABLED:
        return False

    # Solo para consultas complejas del negocio
    if message_type != MessageType.BUSINESS_CONSULT:
        return False

    # NO llamar para FAQ simples (incluso si son BUSINESS_CONSULT)
    faq_intents = {
        "saludo", "despedida", "cierre", "envios", "pagos", "horarios",
        "direccion", "ubicacion", "telefono", "contacto", "promociones"
    }

    if intent in faq_intents:
        return False

    # NO llamar si ya tenemos respuesta del cache
    if cache_hit:
        return False

    # Verificar si hay señal de respuesta determinística robusta
    # (esto se determina por el contexto del pipeline)
    has_robust_deterministic = context.get("has_robust_deterministic", False)
    if has_robust_deterministic:
        return False

    # Si pasa todos los filtros, se puede llamar OpenAI
    return True


def ensure_next_step_question(text: str, intent: str, context: dict) -> str:
    """
    Post-procesador: Asegura que la respuesta termine con una pregunta cerrada
    para mantener la conversación activa.
    """
    if not text:
        return text

    # NO modificar estos intents
    skip_intents = {"saludo", "despedida", "confirmacion_pago", "cierre"}
    if intent in skip_intents:
        return text

    # Si ya tiene pregunta, NO modificar
    if "?" in text:
        return text

    # Mapeo de intents a preguntas cerradas
    intent_questions = {
        # Búsqueda de máquinas
        "buscar_maquina_industrial": "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?",
        "buscar_maquina_familiar": "¿La necesitas para uso en casa o para emprendimiento?",
        "buscar_fileteadora": "¿Buscas fileteadora familiar o industrial?",

        # Información comercial
        "preguntar_precio": "¿Buscas máquina familiar (desde $400.000) o industrial (desde $1.230.000)?",
        "envios": "¿A qué ciudad o municipio sería el envío?",
        "pagos": "¿Prefieres Addi o Sistecrédito para financiamiento?",
        "garantia": "¿Es garantía por defecto de fábrica o por reparación?",

        # Servicio técnico
        "repuesto_accesorio": "¿Me confirmas la marca de tu máquina o me envías foto de la placa?",
        "soporte_tecnico": "¿Es problema con costura, motor o alimentación?",
        "instalacion_servicio": "¿Prefieres instalación en tu taller o domicilio?",

        # Asesoría
        "asesoria_negocio": "¿Vas a producir de forma ocasional o constante?",
        "comparacion_maquinas": "¿Buscas comparar precios, características o marcas específicas?",

        # Información general
        "horario": "¿Necesitas más información sobre ubicación o contacto?",
        "ubicacion": "¿Quieres que te guíe con direcciones o prefieres envío?",
        "catalogo": "¿Te intereso alguna máquina específica o necesitas recomendaciones?",

        # Otros informativos
        "info_general": "¿Necesitas información sobre máquinas, repuestos o servicio técnico?"
    }

    # Buscar pregunta específica para este intent
    question = intent_questions.get(intent)

    if question:
        # Añadir la pregunta al final
        if text.endswith(".") or text.endswith("!"):
            return f"{text} {question}"
        else:
            return f"{text}. {question}"

    # Si no hay pregunta específica, usar genérica pero solo para intents informativos
    # Evitar frases prohibidas como "cuéntame más" o "qué necesitas"
    return text


def _build_decision_path(
    business_related: bool,
    cache_checked: bool,
    asset_selected: bool,
    openai_called: bool,
    handoff_triggered: bool,
    question_appended: bool = False,
    message_type: str = None,
    openai_block_reason: str = None
) -> str:
    """Construye string de decision path para trazabilidad."""
    path_parts = []

    # Tipo de mensaje
    if message_type:
        path_parts.append(f"msg_{message_type}")

    if business_related:
        path_parts.append("business_ok")
    else:
        path_parts.append("business_rejected")
        return "->".join(path_parts)

    if cache_checked:
        path_parts.append("cache_hit")
        return "->".join(path_parts)

    path_parts.append("cache_miss")

    if asset_selected:
        path_parts.append("asset_selected")
    else:
        path_parts.append("asset_skipped")

    if openai_called:
        path_parts.append("openai_called_fallback")
    elif openai_block_reason:
        path_parts.append(f"openai_{openai_block_reason}")
    else:
        path_parts.append("openai_skipped")

    if handoff_triggered:
        path_parts.append("handoff_triggered")

    if question_appended:
        path_parts.append("question_appended")

    return "->".join(path_parts)


def _generate_fallback_response(text: str, context: dict, intent_result: dict) -> str:
    """Respuesta básica cuando no hay OpenAI ni reglas específicas."""
    text_lower = text.lower()
    intent = intent_result.get("intent", "")

    # Saludos
    if intent == "saludo" or any(w in text_lower for w in ["hola", "buenas"]):
        return "¡Hola! 👋 Soy Luisa. ¿Buscas máquina familiar o industrial?"

    # Promociones
    if intent == "preguntar_promociones" or "promoción" in text_lower:
        return "Sí, tenemos promoción navideña con KINGTER KT-D3 y KANSEW KS-8800. ¿Cuál te interesa?"

    # Precio
    if intent == "preguntar_precio" or "precio" in text_lower:
        return "Los precios varían por máquina. ¿Buscas familiar o industrial?"

    # Default
    if context.get("tipo_maquina"):
        if not context.get("uso"):
            return "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        return "¿En qué ciudad te encuentras para coordinar envío?"
    else:
        return "¿Buscas máquina familiar (para casa) o industrial (para producción)?"
