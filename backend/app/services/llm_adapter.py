"""
LLM Adapter para LUISA.

Este módulo provee un adapter limpio que usa OpenAI SOLO como generador de texto sugerido.
NO toma decisiones de negocio (estados, handoff, etc.).

Principios:
- OpenAI NO decide estados
- OpenAI NO hace handoff
- OpenAI NO responde solo
- OpenAI solo devuelve TEXTO sugerido
"""
import time
from typing import Optional, Dict, Any, List, Tuple
import httpx

from app.config import (
    OPENAI_ENABLED,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MAX_INPUT_CHARS,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_CALLS_PER_CONVERSATION,
    OPENAI_CONVERSATION_TTL_HOURS,
    OPENAI_MAX_TOKENS_PER_CALL
)
from app.logging_config import logger


# Timeout duro: 5 segundos (no configurable por seguridad)
LLM_ADAPTER_TIMEOUT_SECONDS = 5.0
LLM_ADAPTER_MAX_REPLY_LENGTH = 500  # Máximo caracteres en respuesta
LLM_ADAPTER_MAX_HISTORY_MESSAGES = 6  # Máximo mensajes en historial


class LLMTaskType:
    """Tipos de tarea que puede realizar el LLM Adapter."""
    COPY = "copy"  # Redactar texto comercial natural
    EXPLICACION = "explicacion"  # Explicar concepto técnico/comparación
    OBJECION = "objecion"  # Manejar objeción del cliente
    CONSULTA_COMPLEJA = "consulta_compleja"  # Responder consulta compleja
    
    @classmethod
    def is_valid(cls, task_type: str) -> bool:
        """Valida que el tipo de tarea sea válido."""
        return task_type in [cls.COPY, cls.EXPLICACION, cls.OBJECION, cls.CONSULTA_COMPLEJA]


def _has_minimum_context(contexto: Dict[str, Any]) -> bool:
    """
    Valida que el contexto tiene datos mínimos necesarios.
    
    Mínimo requerido:
    - datos_negocio.horarios O datos_negocio.direccion
    - productos_recomendados O contexto_conversacion.intent_detectado
    """
    datos_negocio = contexto.get("datos_negocio", {})
    has_business_data = (
        datos_negocio.get("horarios") or
        datos_negocio.get("direccion")
    )
    
    contexto_conv = contexto.get("contexto_conversacion", {})
    has_product_or_intent = (
        contexto.get("productos_recomendados") or
        contexto_conv.get("intent_detectado")
    )
    
    return bool(has_business_data and has_product_or_intent)


def _load_system_prompt_template(task_type: str) -> str:
    """
    Carga la plantilla de system prompt según tipo de tarea.
    
    Plantillas predefinidas (NO generadas dinámicamente).
    """
    from app.domain.business_facts import (
        BUSINESS_HOURS, PAYMENT_METHODS
    )
    
    horarios = f"{BUSINESS_HOURS.get('weekdays', 'Lunes a viernes: 9am-6pm')}, {BUSINESS_HOURS.get('saturday', 'Sábados: 9am-2pm')}"
    direccion = BUSINESS_HOURS.get('address', 'Montería, Córdoba, Colombia')
    formas_pago = ', '.join(PAYMENT_METHODS) if PAYMENT_METHODS else 'Addi, Sistecrédito, Contado'
    
    base_context = f"""DATOS DEL NEGOCIO:
- Horarios: {horarios}
- Dirección: {direccion}
- Formas de pago: {formas_pago}
"""
    
    templates = {
        LLMTaskType.COPY: f"""Eres Luisa, asesora comercial de Almacén y Taller El Sastre en Montería, Colombia.

INSTRUCCIONES ESTRICTAS:
1. Redacta texto comercial natural y amigable
2. Usa SOLO los datos proporcionados en el contexto
3. NO inventes precios, horarios, direcciones
4. Siempre termina con UNA pregunta cerrada (máximo 2 opciones)
5. NO menciones que eres una IA o bot
6. Máximo 3 frases cortas

{base_context}
CONTEXTO DE LA CONVERSACIÓN:
{{contexto_conversacion}}

PRODUCTOS RECOMENDADOS:
{{productos}}
""",
        
        LLMTaskType.EXPLICACION: f"""Eres Luisa, asesora comercial experta en máquinas de coser.

INSTRUCCIONES:
1. Explica conceptos técnicos de forma simple
2. Usa analogías cuando ayude
3. Compara opciones de forma clara
4. NO inventes especificaciones técnicas
5. Siempre termina con pregunta cerrada

{base_context}
PRODUCTOS A EXPLICAR:
{{productos}}

CONTEXTO:
{{contexto_conversacion}}
""",
        
        LLMTaskType.OBJECION: f"""Eres Luisa, asesora comercial experta en manejo de objeciones.

INSTRUCCIONES:
1. Reconoce la preocupación del cliente con empatía
2. Ofrece alternativas reales (NO inventadas)
3. Usa SOLO productos y precios del contexto
4. No presiones, solo informa opciones
5. Termina con pregunta cerrada

{base_context}
ALTERNATIVAS DISPONIBLES:
{{productos}}

CONTEXTO:
{{contexto_conversacion}}
""",
        
        LLMTaskType.CONSULTA_COMPLEJA: f"""Eres Luisa, asesora comercial para emprendimientos y talleres.

INSTRUCCIONES:
1. Analiza la consulta del cliente
2. Genera respuesta estructurada usando SOLO datos proporcionados
3. Si necesitas información que no tienes, di que un asesor puede ayudar
4. Siempre termina con pregunta cerrada o sugerencia de siguiente paso

{base_context}
PRODUCTOS RELEVANTES:
{{productos}}

CONTEXTO COMPLETO:
{{contexto_conversacion}}
"""
    }
    
    return templates.get(task_type, templates[LLMTaskType.COPY])


def _load_user_prompt_template(task_type: str) -> str:
    """
    Carga la plantilla de user prompt según tipo de tarea.
    """
    templates = {
        LLMTaskType.COPY: """Redacta respuesta comercial natural para este mensaje del cliente:

"{user_message}"

{conversation_history}

Usa los datos del contexto estructurado proporcionado en el system prompt.""",
        
        LLMTaskType.EXPLICACION: """El cliente pregunta:

"{user_message}"

{conversation_history}

Explica usando los productos y datos proporcionados en el system prompt.""",
        
        LLMTaskType.OBJECION: """El cliente tiene esta objeción:

"{user_message}"

{conversation_history}

Maneja la objeción con empatía y ofrece alternativas reales.""",
        
        LLMTaskType.CONSULTA_COMPLEJA: """El cliente consulta:

"{user_message}"

{conversation_history}

Responde usando el contexto completo proporcionado en el system prompt."""
    }
    
    return templates.get(task_type, templates[LLMTaskType.COPY])


def _insert_context_into_prompt(prompt: str, contexto: Dict[str, Any]) -> str:
    """
    Inserta el contexto estructurado en el prompt usando placeholders.
    """
    # Insertar contexto de conversación
    contexto_conv = contexto.get("contexto_conversacion", {})
    if contexto_conv:
        contexto_text = "\n".join([f"- {k}: {v}" for k, v in contexto_conv.items() if v])
    else:
        contexto_text = "- No hay contexto conversacional específico"
    prompt = prompt.replace("{contexto_conversacion}", contexto_text)
    
    # Insertar productos recomendados
    productos = contexto.get("productos_recomendados", [])
    if productos:
        productos_text = "\n".join([
            f"- {p.get('nombre', 'N/A')}: ${p.get('precio', 0):,} - {', '.join(p.get('caracteristicas', []))}"
            for p in productos[:3]  # Máximo 3 productos
        ])
    else:
        productos_text = "- No hay productos específicos recomendados aún."
    prompt = prompt.replace("{productos}", productos_text)
    
    return prompt


def _format_conversation_history(history: Optional[List[Dict[str, str]]]) -> str:
    """
    Formatea el historial conversacional para el prompt.
    """
    if not history:
        return ""
    
    # Tomar últimos N mensajes
    recent_history = history[-LLM_ADAPTER_MAX_HISTORY_MESSAGES:]
    
    formatted = "Historial reciente:\n"
    for msg in recent_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        # Truncar mensajes largos
        if len(content) > 200:
            content = content[:197] + "..."
        formatted += f"{role.capitalize()}: {content}\n"
    
    return formatted


def _truncate_prompt(prompt: str, max_chars: int) -> str:
    """
    Trunca el prompt manteniendo el mensaje del usuario cuando sea posible.
    """
    if len(prompt) <= max_chars:
        return prompt
    
    # Intentar mantener user_message completo
    if "{user_message}" in prompt:
        parts = prompt.split("{user_message}")
        if len(parts) == 2:
            before = parts[0]
            after = parts[1]
            # Truncar solo "before" y "after", mantener placeholder
            available_chars = max_chars - len("{user_message}")
            before_chars = int(available_chars * 0.6)
            after_chars = available_chars - before_chars
            before = before[-before_chars:] if len(before) > before_chars else before
            after = after[:after_chars] if len(after) > after_chars else after
            return before + "{user_message}" + after
    
    # Si no hay placeholder, truncar directamente
    return prompt[:max_chars-3] + "..."


def _generate_fallback_reply(task_type: str, contexto: Dict[str, Any]) -> Optional[str]:
    """
    Genera respuesta fallback cuando OpenAI falla.
    
    Fallbacks predefinidos según tipo de tarea.
    """
    if task_type == LLMTaskType.COPY:
        return _fallback_copy(contexto)
    elif task_type == LLMTaskType.EXPLICACION:
        return _fallback_explicacion(contexto)
    elif task_type == LLMTaskType.OBJECION:
        return _fallback_objecion(contexto)
    elif task_type == LLMTaskType.CONSULTA_COMPLEJA:
        return _fallback_consulta_compleja(contexto)
    else:
        return _fallback_default(contexto)


def _fallback_copy(contexto: Dict[str, Any]) -> str:
    """Fallback para redacción comercial."""
    productos = contexto.get("productos_recomendados", [])
    if productos:
        producto = productos[0]
        nombre = producto.get("nombre", "máquina")
        precio = producto.get("precio", 0)
        return f"Para tu proyecto, te recomiendo {nombre} que cuesta ${precio:,}. ¿Te interesa conocer más detalles o prefieres ver otras opciones?"
    
    intent = contexto.get("contexto_conversacion", {}).get("intent_detectado", "máquina")
    return f"Entiendo que buscas información sobre {intent}. ¿Qué te gustaría saber específicamente: precios, características o disponibilidad?"


def _fallback_explicacion(contexto: Dict[str, Any]) -> str:
    """Fallback para explicación técnica."""
    productos = contexto.get("productos_recomendados", [])
    if productos:
        return f"Te puedo dar más detalles sobre {productos[0].get('nombre', 'estas máquinas')}. ¿Qué te interesa saber: características técnicas, precio o disponibilidad?"
    
    return "Puedo explicarte más sobre nuestras máquinas. ¿Qué te gustaría saber: tipos, precios o características?"


def _fallback_objecion(contexto: Dict[str, Any]) -> str:
    """Fallback para manejo de objeciones."""
    productos = contexto.get("productos_recomendados", [])
    if len(productos) > 1:
        precios = sorted([p.get("precio", 0) for p in productos if p.get("precio")])
        if precios:
            return f"Entiendo tu situación. Tenemos opciones desde ${precios[0]:,} hasta ${precios[-1]:,}. ¿Cuál se ajusta mejor a tu presupuesto?"
    
    datos_negocio = contexto.get("datos_negocio", {})
    formas_pago = datos_negocio.get("formas_pago", [])
    if not formas_pago:
        from app.domain.business_facts import PAYMENT_METHODS
        formas_pago = PAYMENT_METHODS if PAYMENT_METHODS else ["Addi", "Sistecrédito"]
    
    if formas_pago:
        return f"Entiendo. Ofrecemos financiamiento con {', '.join(formas_pago[:2])} para que puedas pagar a cuotas. ¿Te interesa esa opción?"
    
    return "Entiendo tu preocupación. Un asesor puede ayudarte a encontrar la mejor opción para ti. ¿Quieres que te contacten?"


def _fallback_consulta_compleja(contexto: Dict[str, Any]) -> str:
    """Fallback para consultas complejas."""
    intent = contexto.get("contexto_conversacion", {}).get("intent_detectado", "")
    if intent:
        return f"Para ayudarte mejor con {intent}, un asesor puede darte información detallada y personalizada. ¿Quieres que te contacten o prefieres información general primero?"
    
    return "Tu consulta es importante. Para darte la mejor respuesta, ¿prefieres que un asesor te contacte o quieres información general primero?"


def _fallback_default(contexto: Dict[str, Any]) -> str:
    """Fallback genérico."""
    return "¡Hola! 😊 ¿En qué puedo ayudarte: máquinas familiares, industriales o repuestos?"


async def get_llm_suggestion(
    task_type: str,
    user_message: str,
    context: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    conversation_id: Optional[str] = None,
    reason_for_llm_use: Optional[str] = None
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Genera texto sugerido usando OpenAI.
    
    ATENCIÓN: Esta función SOLO genera texto. NO toma decisiones de negocio.
    
    Args:
        task_type: Tipo de tarea ("copy", "explicacion", "objecion", "consulta_compleja")
        user_message: Mensaje del usuario (original, no normalizado)
        context: Contexto estructurado del negocio:
            {
                "productos_recomendados": [
                    {"nombre": "Singer 4423", "precio": 1800000, "caracteristicas": [...]}
                ],
                "datos_negocio": {
                    "horarios": "Lunes a Sábado 8am-6pm",
                    "direccion": "Calle X #Y-Z, Montería",
                    "formas_pago": ["Addi", "Sistecrédito", "Contado"]
                },
                "contexto_conversacion": {
                    "tipo_maquina": "industrial",
                    "uso": "produccion_constante",
                    "volumen": "alto",
                    "ciudad": "Montería",
                    "intent_detectado": "buscar_maquina_industrial"
                }
            }
        conversation_history: Últimos N mensajes para contexto conversacional
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        conversation_id: ID de la conversación (opcional, para tracking de límites)
        reason_for_llm_use: Razón por la que se usa LLM (opcional, para logging)
    
    Returns:
        Tuple[suggested_reply, metadata]:
            - suggested_reply: String con texto sugerido o None si deshabilitado/límite excedido
            - metadata: Dict con información del proceso:
                {
                    "success": bool,
                    "error": Optional[str],
                    "latency_ms": int,
                    "tokens_used": Optional[int],
                    "fallback_used": bool,
                    "task_type": str,
                    "openai_call_count": int,  # Número de llamadas en esta conversación
                    "reason_for_llm_use": Optional[str],  # Razón de uso
                    "limit_exceeded": bool  # True si se excedió el límite
                }
    
    Nota: Nunca lanza excepciones - siempre retorna Tuple[Optional[str], Dict]
    """
    start_time = time.perf_counter()
    metadata = {
        "success": False,
        "error": None,
        "latency_ms": 0,
        "tokens_used": None,
        "fallback_used": False,
        "task_type": task_type,
        "openai_call_count": 0,
        "reason_for_llm_use": reason_for_llm_use,
        "limit_exceeded": False
    }
    
    # ============================================================
    # PASO 1: VALIDACIÓN DE ENTRADA
    # ============================================================
    
    if not OPENAI_ENABLED:
        metadata["error"] = "openai_disabled"
        metadata["latency_ms"] = 0
        logger.debug("LLM Adapter: OpenAI deshabilitado", task_type=task_type)
        return None, metadata
    
    # ============================================================
    # PASO 1.5: VERIFICAR LÍMITES DE USO POR CONVERSACIÓN
    # ============================================================
    
    if conversation_id:
        from app.models.database import (
            get_openai_call_count,
            reset_openai_call_count_if_expired,
            increment_openai_call_count
        )
        
        # Resetear contador si TTL expiró
        was_reset = reset_openai_call_count_if_expired(
            conversation_id, 
            OPENAI_CONVERSATION_TTL_HOURS
        )
        if was_reset:
            logger.info(
                "LLM Adapter: Contador OpenAI reseteado por TTL",
                conversation_id=conversation_id,
                ttl_hours=OPENAI_CONVERSATION_TTL_HOURS
            )
        
        # Obtener contador actual
        current_count = get_openai_call_count(conversation_id)
        metadata["openai_call_count"] = current_count
        
        # Verificar límite máximo de llamadas
        if current_count >= OPENAI_MAX_CALLS_PER_CONVERSATION:
            metadata["error"] = "max_calls_per_conversation_exceeded"
            metadata["limit_exceeded"] = True
            metadata["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            logger.warning(
                "LLM Adapter: Límite de llamadas excedido",
                conversation_id=conversation_id,
                current_count=current_count,
                max_calls=OPENAI_MAX_CALLS_PER_CONVERSATION,
                task_type=task_type,
                reason_for_llm_use=reason_for_llm_use
            )
            # Retornar None (no se puede llamar OpenAI)
            return None, metadata
    
    if not OPENAI_API_KEY:
        metadata["error"] = "api_key_missing"
        metadata["latency_ms"] = 0
        logger.warning("LLM Adapter: API key faltante", task_type=task_type)
        return None, metadata
    
    if not LLMTaskType.is_valid(task_type):
        metadata["error"] = "invalid_task_type"
        metadata["latency_ms"] = 0
        logger.warning("LLM Adapter: Tipo de tarea inválido", task_type=task_type)
        return None, metadata
    
    if not _has_minimum_context(context):
        metadata["error"] = "insufficient_context"
        metadata["latency_ms"] = 0
        logger.warning("LLM Adapter: Contexto insuficiente", task_type=task_type)
        return None, metadata
    
    # ============================================================
    # PASO 2: CONSTRUCCIÓN DEL PROMPT
    # ============================================================
    
    try:
        # Cargar plantilla según tipo de tarea
        system_prompt = _load_system_prompt_template(task_type)
        user_prompt = _load_user_prompt_template(task_type)
        
        # Insertar contexto estructurado
        system_prompt = _insert_context_into_prompt(system_prompt, context)
        
        # Insertar mensaje del usuario
        user_prompt = user_prompt.replace("{user_message}", user_message)
        
        # Insertar historial conversacional (si existe)
        history_text = _format_conversation_history(conversation_history)
        user_prompt = user_prompt.replace("{conversation_history}", history_text)
        
        # Limitar longitud de prompt (control de costos)
        if len(user_prompt) > OPENAI_MAX_INPUT_CHARS:
            user_prompt = _truncate_prompt(user_prompt, OPENAI_MAX_INPUT_CHARS)
            logger.debug("LLM Adapter: Prompt truncado", original_len=len(user_prompt), max_chars=OPENAI_MAX_INPUT_CHARS)
    
    except Exception as e:
        logger.error("LLM Adapter: Error construyendo prompt", error=str(e), task_type=task_type)
        metadata["error"] = f"prompt_construction_error: {str(e)}"
        fallback_reply = _generate_fallback_reply(task_type, context)
        metadata["fallback_used"] = True
        metadata["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        return fallback_reply, metadata
    
    # ============================================================
    # PASO 3: LLAMADA A OPENAI CON TIMEOUT
    # ============================================================
    
    # Inicializar variables antes del try
    suggested_reply = None
    tokens_used = 0
    latency_ms = 0
    
    try:
        async with httpx.AsyncClient(timeout=LLM_ADAPTER_TIMEOUT_SECONDS) as client:
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
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": OPENAI_MAX_OUTPUT_TOKENS,
                    "temperature": OPENAI_TEMPERATURE
                }
            )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            metadata["latency_ms"] = latency_ms
            
            # Verificar status HTTP
            if response.status_code != 200:
                error_body = response.text[:200] if hasattr(response, 'text') else "unknown"
                logger.warning(
                    "LLM Adapter: OpenAI API error",
                    status=response.status_code,
                    body=error_body,
                    task_type=task_type,
                    conversation_id=conversation_id if conversation_id else "unknown"
                )
                fallback_reply = _generate_fallback_reply(task_type, context)
                metadata["error"] = f"http_error_{response.status_code}"
                metadata["fallback_used"] = True
                return fallback_reply, metadata
            
            # Extraer respuesta
            data = response.json()
            suggested_reply = data["choices"][0]["message"]["content"].strip()
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            metadata["tokens_used"] = tokens_used
            
            # Validar límite de tokens por llamada (solo warning, no bloquear)
            if tokens_used > OPENAI_MAX_TOKENS_PER_CALL:
                logger.warning(
                    "LLM Adapter: Tokens excedidos en llamada",
                    conversation_id=conversation_id if conversation_id else "unknown",
                    tokens_used=tokens_used,
                    max_tokens=OPENAI_MAX_TOKENS_PER_CALL,
                    task_type=task_type,
                    reason_for_llm_use=reason_for_llm_use
                )
    
    except httpx.TimeoutException:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        metadata["latency_ms"] = latency_ms
        logger.warning(
            "LLM Adapter: OpenAI timeout",
            task_type=task_type,
            timeout_seconds=LLM_ADAPTER_TIMEOUT_SECONDS,
            conversation_id=conversation_id if conversation_id else "unknown",
            reason_for_llm_use=reason_for_llm_use
        )
        fallback_reply = _generate_fallback_reply(task_type, context)
        metadata["error"] = "timeout_5s"
        metadata["fallback_used"] = True
        return fallback_reply, metadata
    
    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        metadata["latency_ms"] = latency_ms
        logger.error(
            "LLM Adapter: OpenAI exception",
            error=str(e)[:100],
            task_type=task_type,
            conversation_id=conversation_id if conversation_id else "unknown",
            reason_for_llm_use=reason_for_llm_use
        )
        fallback_reply = _generate_fallback_reply(task_type, context)
        metadata["error"] = f"exception: {str(e)[:100]}"  # Limitar longitud del error
        metadata["fallback_used"] = True
        return fallback_reply, metadata
    
    # ============================================================
    # PASO 4: VALIDACIÓN DE RESPUESTA
    # ============================================================
    
    # Validar que no está vacía
    if not suggested_reply or len(suggested_reply.strip()) == 0:
        logger.warning("LLM Adapter: OpenAI returned empty response", task_type=task_type)
        fallback_reply = _generate_fallback_reply(task_type, context)
        metadata["error"] = "empty_response"
        metadata["fallback_used"] = True
        return fallback_reply, metadata
    
    # Validar que no menciona ser bot/IA
    forbidden_phrases = [
        "soy un bot", "soy una ia", "soy un asistente virtual",
        "soy una inteligencia artificial", "soy un chatbot",
        "asistente virtual", "inteligencia artificial"
    ]
    reply_lower = suggested_reply.lower()
    if any(phrase in reply_lower for phrase in forbidden_phrases):
        logger.warning("LLM Adapter: OpenAI mentioned being AI", task_type=task_type)
        fallback_reply = _generate_fallback_reply(task_type, context)
        metadata["error"] = "forbidden_ai_mention"
        metadata["fallback_used"] = True
        return fallback_reply, metadata
    
    # Validar longitud razonable
    if len(suggested_reply) > LLM_ADAPTER_MAX_REPLY_LENGTH:
        original_len = len(suggested_reply)
        suggested_reply = suggested_reply[:LLM_ADAPTER_MAX_REPLY_LENGTH-3] + "..."
        logger.warning("LLM Adapter: Response truncated", original_len=original_len, task_type=task_type)
    
    # ============================================================
    # PASO 5: INCREMENTAR CONTADOR DESPUÉS DE ÉXITO
    # ============================================================
    
    # Solo incrementar contador si la llamada fue exitosa y pasó todas las validaciones
    if conversation_id:
        from app.models.database import increment_openai_call_count
        
        new_count = increment_openai_call_count(conversation_id)
        metadata["openai_call_count"] = new_count
        
        logger.info(
            "LLM Adapter: Llamada OpenAI registrada",
            conversation_id=conversation_id,
            call_count=new_count,
            max_calls=OPENAI_MAX_CALLS_PER_CONVERSATION,
            task_type=task_type,
            reason_for_llm_use=reason_for_llm_use,
            tokens_used=tokens_used
        )
    
    # ============================================================
    # PASO 6: RETORNAR RESPUESTA SUGERIDA
    # ============================================================
    
    metadata["success"] = True
    logger.info(
        "LLM Adapter: Suggested reply generated",
        conversation_id=conversation_id if conversation_id else "unknown",
        task_type=task_type,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
        reply_length=len(suggested_reply),
        fallback_used=False,
        openai_call_count=metadata.get("openai_call_count", 0),
        reason_for_llm_use=reason_for_llm_use
    )
    
    return suggested_reply, metadata


def get_llm_suggestion_sync(
    task_type: str,
    user_message: str,
    context: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    conversation_id: Optional[str] = None,
    reason_for_llm_use: Optional[str] = None
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Versión síncrona de get_llm_suggestion para uso en endpoints sync.
    
    Wrapper que ejecuta la función async en un nuevo event loop.
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
                    get_llm_suggestion(
                        task_type, user_message, context, 
                        conversation_history, conversation_id, reason_for_llm_use
                    )
                )
            return future.result(timeout=LLM_ADAPTER_TIMEOUT_SECONDS + 2)
        else:
            return loop.run_until_complete(
                get_llm_suggestion(
                    task_type, user_message, context,
                    conversation_history, conversation_id, reason_for_llm_use
                )
            )
    except Exception as e:
        logger.error("LLM Adapter: Error en versión síncrona", error=str(e), task_type=task_type)
        # Retornar fallback
        fallback_reply = _generate_fallback_reply(task_type, context)
        return fallback_reply, {
            "success": False,
            "error": f"sync_wrapper_error: {str(e)}",
            "latency_ms": 0,
            "tokens_used": None,
            "fallback_used": True,
            "task_type": task_type,
            "openai_call_count": 0,
            "reason_for_llm_use": reason_for_llm_use,
            "limit_exceeded": False
        }

