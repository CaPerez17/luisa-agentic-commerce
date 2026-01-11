# Diseño: LLM Adapter para LUISA

**Product Architect + AI Engineer Design**  
**Objetivo**: Adapter que usa OpenAI SOLO como generador de texto, sin decisiones de negocio

---

## Principios de Diseño

### Reglas de Oro

1. **OpenAI NO decide estados**: Solo genera texto, no cambia `conversation_mode`, `state`, etc.
2. **OpenAI NO hace handoff**: No decide cuándo escalar a humano
3. **OpenAI NO responde solo**: Siempre devuelve `suggested_reply` para validación
4. **OpenAI solo devuelve TEXTO**: String puro, sin metadatos de decisión

### Separación de Responsabilidades

```
┌─────────────────────────────────────────────────────────┐
│           HEURÍSTICAS (Decision Maker)                   │
│  - Decide QUÉ decir (contenido, datos, productos)       │
│  - Decide CUÁNDO usar OpenAI (tipo_tarea)               │
│  - Decide estados (handoff, modo conversación)          │
│  - Valida respuesta sugerida                            │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ Llama a LLM Adapter
                    │ con: contexto + tipo_tarea
                    │
┌───────────────────▼─────────────────────────────────────┐
│         LLM ADAPTER (Text Generator Only)               │
│  - Recibe contexto estructurado                         │
│  - Genera texto sugerido                                │
│  - Retorna string puro                                  │
│  - NO decide nada                                       │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ suggested_reply (string)
                    │
┌───────────────────▼─────────────────────────────────────┐
│           HEURÍSTICAS (Validator)                       │
│  - Valida que no inventa datos                          │
│  - Asegura pregunta cerrada                             │
│  - Envía respuesta final                                │
└─────────────────────────────────────────────────────────┘
```

---

## Firma de Función

### Función Principal

```python
async def generate_suggested_reply(
    user_message: str,
    contexto_estructurado: Dict[str, Any],
    tipo_tarea: str,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Genera texto sugerido usando OpenAI.
    
    ATENCIÓN: Esta función SOLO genera texto. NO toma decisiones de negocio.
    
    Args:
        user_message: Mensaje del usuario (original, no normalizado)
        contexto_estructurado: Contexto del negocio estructurado:
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
                    "ciudad": "Montería"
                },
                "intent_detectado": "buscar_maquina_industrial",
                "confidence": 0.85
            }
        tipo_tarea: Tipo de tarea que debe realizar OpenAI:
            - "copy": Redactar texto comercial natural
            - "explicacion": Explicar concepto técnico o comparación
            - "objecion": Manejar objeción del cliente
            - "consulta_compleja": Responder consulta que requiere razonamiento
        conversation_history: Últimos N mensajes para contexto conversacional
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    
    Returns:
        Tuple[suggested_reply, metadata]:
            - suggested_reply: String con texto sugerido o None si falla
            - metadata: Dict con información del proceso:
                {
                    "success": bool,
                    "error": Optional[str],
                    "latency_ms": int,
                    "tokens_used": Optional[int],
                    "fallback_used": bool,
                    "task_type": str
                }
    
    Raises:
        No raises exceptions - siempre retorna Tuple[Optional[str], Dict]
    """
    pass
```

### Tipos de Tarea (Task Types)

```python
from enum import Enum

class LLMTaskType(str, Enum):
    """Tipos de tarea que puede realizar el LLM Adapter."""
    
    COPY = "copy"  # Redactar texto comercial natural
    EXPLICACION = "explicacion"  # Explicar concepto técnico/comparación
    OBJECION = "objecion"  # Manejar objeción del cliente
    CONSULTA_COMPLEJA = "consulta_compleja"  # Responder consulta compleja
```

---

## Flujo Paso a Paso

### 1. Validación de Entrada

```
1.1. Verificar OPENAI_ENABLED == true
     → Si no: retornar (None, {"success": False, "error": "openai_disabled"})
1.2. Verificar OPENAI_API_KEY presente
     → Si no: retornar (None, {"success": False, "error": "api_key_missing"})
1.3. Validar tipo_tarea en valores permitidos
     → Si no: retornar (None, {"success": False, "error": "invalid_task_type"})
1.4. Validar contexto_estructurado tiene datos mínimos
     → Si no: retornar (None, {"success": False, "error": "insufficient_context"})
```

### 2. Construcción del Prompt

```
2.1. Cargar plantilla de prompt según tipo_tarea
     → Prompt templates predefinidos (no generados dinámicamente)
2.2. Insertar contexto estructurado en plantilla
     → Usar placeholders: {productos}, {datos_negocio}, {contexto_conversacion}
2.3. Insertar user_message en plantilla
     → Placeholder: {user_message}
2.4. Insertar historial conversacional (si existe)
     → Placeholder: {conversation_history}
2.5. Agregar instrucciones estrictas:
     → "NO inventes precios, horarios, direcciones"
     → "Usa SOLO los datos proporcionados"
     → "Siempre termina con UNA pregunta cerrada"
     → "NO menciones que eres una IA o bot"
```

### 3. Llamada a OpenAI con Timeout

```
3.1. Crear HTTP client con timeout duro (5 segundos)
3.2. Preparar request JSON:
     {
         "model": OPENAI_MODEL,
         "messages": [
             {"role": "system", "content": system_prompt},
             {"role": "user", "content": user_prompt}
         ],
         "max_tokens": OPENAI_MAX_OUTPUT_TOKENS,
         "temperature": OPENAI_TEMPERATURE
     }
3.3. Ejecutar POST con timeout de 5 segundos
3.4. Si timeout: retornar fallback
3.5. Si error HTTP: retornar fallback
3.6. Si status != 200: retornar fallback
```

### 4. Procesamiento de Respuesta

```
4.1. Extraer texto de response["choices"][0]["message"]["content"]
4.2. Validar que no está vacío
     → Si vacío: retornar fallback
4.3. Validar que no menciona ser "bot/IA"
     → Si menciona: retornar fallback
4.4. Validar longitud razonable (máx 500 caracteres)
     → Si muy largo: truncar o retornar fallback
4.5. Extraer metadata (tokens_used, latency_ms)
```

### 5. Generación de Fallback

```
5.1. Si falla cualquier paso anterior:
5.2. Generar respuesta fallback según tipo_tarea:
     - "copy": Respuesta genérica con datos estructurados
     - "explicacion": Explicación básica predefinida
     - "objecion": Respuesta estándar a objeción
     - "consulta_compleja": Respuesta genérica redirigiendo
5.3. Retornar fallback + metadata indicando fallback_used=True
```

---

## Pseudocódigo

### Función Principal

```python
async def generate_suggested_reply(
    user_message: str,
    contexto_estructurado: Dict[str, Any],
    tipo_tarea: str,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Tuple[Optional[str], Dict[str, Any]]:
    
    start_time = time.perf_counter()
    metadata = {
        "success": False,
        "error": None,
        "latency_ms": 0,
        "tokens_used": None,
        "fallback_used": False,
        "task_type": tipo_tarea
    }
    
    # ============================================================
    # PASO 1: VALIDACIÓN DE ENTRADA
    # ============================================================
    
    if not OPENAI_ENABLED:
        metadata["error"] = "openai_disabled"
        metadata["latency_ms"] = 0
        return None, metadata
    
    if not OPENAI_API_KEY:
        metadata["error"] = "api_key_missing"
        metadata["latency_ms"] = 0
        return None, metadata
    
    if tipo_tarea not in [LLMTaskType.COPY, LLMTaskType.EXPLICACION, 
                          LLMTaskType.OBJECION, LLMTaskType.CONSULTA_COMPLEJA]:
        metadata["error"] = "invalid_task_type"
        metadata["latency_ms"] = 0
        return None, metadata
    
    if not _has_minimum_context(contexto_estructurado):
        metadata["error"] = "insufficient_context"
        metadata["latency_ms"] = 0
        return None, metadata
    
    # ============================================================
    # PASO 2: CONSTRUCCIÓN DEL PROMPT
    # ============================================================
    
    try:
        # Cargar plantilla según tipo de tarea
        system_prompt = _load_system_prompt_template(tipo_tarea)
        user_prompt = _load_user_prompt_template(tipo_tarea)
        
        # Insertar contexto estructurado
        system_prompt = _insert_context_into_prompt(
            system_prompt, 
            contexto_estructurado
        )
        
        # Insertar mensaje del usuario
        user_prompt = user_prompt.replace("{user_message}", user_message)
        
        # Insertar historial conversacional (si existe)
        if conversation_history:
            history_text = _format_conversation_history(conversation_history)
            user_prompt = user_prompt.replace("{conversation_history}", history_text)
        else:
            user_prompt = user_prompt.replace("{conversation_history}", "")
        
        # Limitar longitud de prompt (control de costos)
        if len(user_prompt) > OPENAI_MAX_INPUT_CHARS:
            user_prompt = _truncate_prompt(user_prompt, OPENAI_MAX_INPUT_CHARS)
    
    except Exception as e:
        logger.error("Error construyendo prompt", error=str(e), task_type=tipo_tarea)
        metadata["error"] = f"prompt_construction_error: {str(e)}"
        fallback_reply = _generate_fallback_reply(tipo_tarea, contexto_estructurado)
        metadata["fallback_used"] = True
        metadata["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        return fallback_reply, metadata
    
    # ============================================================
    # PASO 3: LLAMADA A OPENAI CON TIMEOUT
    # ============================================================
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:  # TIMEOUT DURO: 5s
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
                logger.warning(
                    "OpenAI API error",
                    status=response.status_code,
                    body=response.text[:200],
                    task_type=tipo_tarea
                )
                fallback_reply = _generate_fallback_reply(tipo_tarea, contexto_estructurado)
                metadata["error"] = f"http_error_{response.status_code}"
                metadata["fallback_used"] = True
                return fallback_reply, metadata
            
            # Extraer respuesta
            data = response.json()
            suggested_reply = data["choices"][0]["message"]["content"].strip()
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            metadata["tokens_used"] = tokens_used
    
    except httpx.TimeoutException:
        logger.warning("OpenAI timeout", task_type=tipo_tarea)
        fallback_reply = _generate_fallback_reply(tipo_tarea, contexto_estructurado)
        metadata["error"] = "timeout_5s"
        metadata["fallback_used"] = True
        metadata["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        return fallback_reply, metadata
    
    except Exception as e:
        logger.error("OpenAI exception", error=str(e), task_type=tipo_tarea)
        fallback_reply = _generate_fallback_reply(tipo_tarea, contexto_estructurado)
        metadata["error"] = f"exception: {str(e)}"
        metadata["fallback_used"] = True
        metadata["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        return fallback_reply, metadata
    
    # ============================================================
    # PASO 4: VALIDACIÓN DE RESPUESTA
    # ============================================================
    
    # Validar que no está vacía
    if not suggested_reply or len(suggested_reply.strip()) == 0:
        logger.warning("OpenAI returned empty response", task_type=tipo_tarea)
        fallback_reply = _generate_fallback_reply(tipo_tarea, contexto_estructurado)
        metadata["error"] = "empty_response"
        metadata["fallback_used"] = True
        return fallback_reply, metadata
    
    # Validar que no menciona ser bot/IA
    forbidden_phrases = [
        "soy un bot", "soy una ia", "soy un asistente virtual",
        "soy una inteligencia artificial", "soy un chatbot"
    ]
    reply_lower = suggested_reply.lower()
    if any(phrase in reply_lower for phrase in forbidden_phrases):
        logger.warning("OpenAI mentioned being AI", task_type=tipo_tarea)
        fallback_reply = _generate_fallback_reply(tipo_tarea, contexto_estructurado)
        metadata["error"] = "forbidden_ai_mention"
        metadata["fallback_used"] = True
        return fallback_reply, metadata
    
    # Validar longitud razonable
    if len(suggested_reply) > 500:
        suggested_reply = suggested_reply[:497] + "..."
        logger.warning("OpenAI response truncated", original_len=len(suggested_reply))
    
    # ============================================================
    # PASO 5: RETORNAR RESPUESTA SUGERIDA
    # ============================================================
    
    metadata["success"] = True
    logger.info(
        "OpenAI suggested reply generated",
        task_type=tipo_tarea,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
        reply_length=len(suggested_reply)
    )
    
    return suggested_reply, metadata
```

### Funciones Auxiliares

```python
def _has_minimum_context(contexto: Dict[str, Any]) -> bool:
    """
    Valida que el contexto tiene datos mínimos necesarios.
    
    Mínimo requerido:
    - datos_negocio.horarios O datos_negocio.direccion
    - productos_recomendados O contexto_conversacion.intent_detectado
    """
    has_business_data = (
        contexto.get("datos_negocio", {}).get("horarios") or
        contexto.get("datos_negocio", {}).get("direccion")
    )
    
    has_product_or_intent = (
        contexto.get("productos_recomendados") or
        contexto.get("contexto_conversacion", {}).get("intent_detectado")
    )
    
    return has_business_data and has_product_or_intent


def _load_system_prompt_template(tipo_tarea: str) -> str:
    """
    Carga la plantilla de system prompt según tipo de tarea.
    
    Plantillas predefinidas (NO generadas dinámicamente).
    """
    templates = {
        LLMTaskType.COPY: """
Eres Luisa, asesora comercial de Almacén y Taller El Sastre en Montería, Colombia.

INSTRUCCIONES ESTRICTAS:
1. Redacta texto comercial natural y amigable
2. Usa SOLO los datos proporcionados en el contexto
3. NO inventes precios, horarios, direcciones
4. Siempre termina con UNA pregunta cerrada (máximo 2 opciones)
5. NO menciones que eres una IA o bot
6. Máximo 3 frases cortas

DATOS DEL NEGOCIO:
{datos_negocio}

CONTEXTO DE LA CONVERSACIÓN:
{contexto_conversacion}
""",
        
        LLMTaskType.EXPLICACION: """
Eres Luisa, asesora comercial experta en máquinas de coser.

INSTRUCCIONES:
1. Explica conceptos técnicos de forma simple
2. Usa analogías cuando ayude
3. Compara opciones de forma clara
4. NO inventes especificaciones técnicas
5. Siempre termina con pregunta cerrada

PRODUCTOS A EXPLICAR:
{productos}

CONTEXTO:
{contexto_conversacion}
""",
        
        LLMTaskType.OBJECION: """
Eres Luisa, asesora comercial experta en manejo de objeciones.

INSTRUCCIONES:
1. Reconoce la preocupación del cliente con empatía
2. Ofrece alternativas reales (NO inventadas)
3. Usa SOLO productos y precios del contexto
4. No presiones, solo informa opciones
5. Termina con pregunta cerrada

OBJECIÓN DEL CLIENTE:
{user_message}

ALTERNATIVAS DISPONIBLES:
{productos}

DATOS DEL NEGOCIO:
{datos_negocio}
""",
        
        LLMTaskType.CONSULTA_COMPLEJA: """
Eres Luisa, asesora comercial para emprendimientos y talleres.

INSTRUCCIONES:
1. Analiza la consulta del cliente
2. Genera respuesta estructurada usando SOLO datos proporcionados
3. Si necesitas información que no tienes, di que un asesor puede ayudar
4. Siempre termina con pregunta cerrada o sugerencia de siguiente paso

CONSULTA:
{user_message}

CONTEXTO COMPLETO:
{contexto_conversacion}

PRODUCTOS RELEVANTES:
{productos}

DATOS DEL NEGOCIO:
{datos_negocio}
"""
    }
    
    return templates.get(tipo_tarea, templates[LLMTaskType.COPY])


def _load_user_prompt_template(tipo_tarea: str) -> str:
    """
    Carga la plantilla de user prompt según tipo de tarea.
    """
    templates = {
        LLMTaskType.COPY: """
Redacta respuesta comercial natural para este mensaje del cliente:

"{user_message}"

{conversation_history}

Usa los datos del contexto estructurado proporcionado en el system prompt.
""",
        
        LLMTaskType.EXPLICACION: """
El cliente pregunta:

"{user_message}"

{conversation_history}

Explica usando los productos y datos proporcionados en el system prompt.
""",
        
        LLMTaskType.OBJECION: """
El cliente tiene esta objeción:

"{user_message}"

{conversation_history}

Maneja la objeción con empatía y ofrece alternativas reales.
""",
        
        LLMTaskType.CONSULTA_COMPLEJA: """
El cliente consulta:

"{user_message}"

{conversation_history}

Responde usando el contexto completo proporcionado en el system prompt.
"""
    }
    
    return templates.get(tipo_tarea, templates[LLMTaskType.COPY])


def _insert_context_into_prompt(prompt: str, contexto: Dict[str, Any]) -> str:
    """
    Inserta el contexto estructurado en el prompt usando placeholders.
    """
    # Insertar datos del negocio
    datos_negocio = contexto.get("datos_negocio", {})
    datos_text = "\n".join([f"- {k}: {v}" for k, v in datos_negocio.items()])
    prompt = prompt.replace("{datos_negocio}", datos_text)
    
    # Insertar contexto de conversación
    contexto_conv = contexto.get("contexto_conversacion", {})
    contexto_text = "\n".join([f"- {k}: {v}" for k, v in contexto_conv.items()])
    prompt = prompt.replace("{contexto_conversacion}", contexto_text)
    
    # Insertar productos recomendados
    productos = contexto.get("productos_recomendados", [])
    if productos:
        productos_text = "\n".join([
            f"- {p.get('nombre', 'N/A')}: ${p.get('precio', 0):,} - {', '.join(p.get('caracteristicas', []))}"
            for p in productos[:3]  # Máximo 3 productos
        ])
    else:
        productos_text = "No hay productos específicos recomendados aún."
    prompt = prompt.replace("{productos}", productos_text)
    
    return prompt


def _format_conversation_history(history: List[Dict[str, str]]) -> str:
    """
    Formatea el historial conversacional para el prompt.
    """
    if not history:
        return ""
    
    # Tomar últimos 6 mensajes
    recent_history = history[-6:]
    
    formatted = "Historial reciente:\n"
    for msg in recent_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        formatted += f"{role.capitalize()}: {content}\n"
    
    return formatted


def _truncate_prompt(prompt: str, max_chars: int) -> str:
    """
    Trunca el prompt manteniendo el mensaje del usuario.
    """
    if len(prompt) <= max_chars:
        return prompt
    
    # Intentar mantener user_message completo
    if "{user_message}" in prompt:
        # Extraer user_message placeholder
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


def _generate_fallback_reply(tipo_tarea: str, contexto: Dict[str, Any]) -> Optional[str]:
    """
    Genera respuesta fallback cuando OpenAI falla.
    
    Fallbacks predefinidos según tipo de tarea.
    """
    fallbacks = {
        LLMTaskType.COPY: _fallback_copy(contexto),
        LLMTaskType.EXPLICACION: _fallback_explicacion(contexto),
        LLMTaskType.OBJECION: _fallback_objecion(contexto),
        LLMTaskType.CONSULTA_COMPLEJA: _fallback_consulta_compleja(contexto)
    }
    
    return fallbacks.get(tipo_tarea, _fallback_default(contexto))


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
        return f"Entiendo tu situación. Tenemos opciones desde ${productos[-1].get('precio', 0):,} hasta ${productos[0].get('precio', 0):,}. ¿Cuál se ajusta mejor a tu presupuesto?"
    
    datos_negocio = contexto.get("datos_negocio", {})
    formas_pago = datos_negocio.get("formas_pago", [])
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
```

---

## Ejemplo de Uso

### Caso 1: Redacción Comercial (COPY)

```python
# Heurísticas determinan QUÉ decir
contexto = {
    "productos_recomendados": [
        {
            "nombre": "Singer 4423",
            "precio": 1800000,
            "caracteristicas": ["Velocidad alta", "Motor fuerte", "Para producción"]
        }
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
        "intent_detectado": "buscar_maquina_industrial"
    }
}

# LLM Adapter solo redacta
suggested_reply, metadata = await generate_suggested_reply(
    user_message="Quiero una máquina para producir ropa constante",
    contexto_estructurado=contexto,
    tipo_tarea=LLMTaskType.COPY,
    conversation_history=None
)

# Resultado esperado:
# suggested_reply = "Para producción constante de ropa, la Singer 4423 es excelente. 
#                    Cuesta $1.800.000 y tiene velocidad alta y motor fuerte. 
#                    ¿Te interesa esta opción o prefieres ver otras máquinas?"
# metadata = {"success": True, "latency_ms": 1200, "tokens_used": 85, ...}
```

### Caso 2: Manejo de Objeción

```python
contexto = {
    "productos_recomendados": [
        {"nombre": "Singer 4423", "precio": 1800000},
        {"nombre": "Kingter KT-D3", "precio": 1230000}
    ],
    "datos_negocio": {
        "formas_pago": ["Addi", "Sistecrédito", "Contado"]
    },
    "contexto_conversacion": {
        "intent_detectado": "buscar_maquina_industrial"
    }
}

suggested_reply, metadata = await generate_suggested_reply(
    user_message="Es muy caro, no tengo ese presupuesto",
    contexto_estructurado=contexto,
    tipo_tarea=LLMTaskType.OBJECION
)

# Resultado esperado:
# suggested_reply = "Entiendo tu situación. Tenemos opciones desde $1.230.000. 
#                    También ofrecemos financiamiento con Addi o Sistecrédito para 
#                    pagar a cuotas. ¿Cuál opción te conviene más?"
```

### Caso 3: Timeout (Fallback)

```python
suggested_reply, metadata = await generate_suggested_reply(
    user_message="Quiero comprar una máquina",
    contexto_estructurado=contexto,
    tipo_tarea=LLMTaskType.COPY
)

# Si OpenAI tarda >5s:
# suggested_reply = "Para tu proyecto, te recomiendo Singer 4423 que cuesta $1.800.000. 
#                    ¿Te interesa conocer más detalles o prefieres ver otras opciones?"
# metadata = {
#     "success": False,
#     "error": "timeout_5s",
#     "fallback_used": True,
#     "latency_ms": 5000
# }
```

---

## Diagrama de Flujo Completo

```
┌─────────────────────────────────────────────────────────┐
│  HEURÍSTICAS: Deciden usar LLM Adapter                  │
│  - Determinan contexto_estructurado                     │
│  - Seleccionan tipo_tarea (COPY/EXPLICACION/OBJECION)   │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ generate_suggested_reply()
                    │
┌───────────────────▼─────────────────────────────────────┐
│  LLM ADAPTER                                            │
│                                                         │
│  1. VALIDACIÓN                                          │
│     ├─ OPENAI_ENABLED? → No: retornar None             │
│     ├─ API_KEY presente? → No: retornar None           │
│     ├─ tipo_tarea válido? → No: retornar None          │
│     └─ contexto suficiente? → No: retornar None        │
│                                                         │
│  2. CONSTRUCCIÓN PROMPT                                 │
│     ├─ Cargar plantilla (tipo_tarea)                   │
│     ├─ Insertar contexto_estructurado                   │
│     ├─ Insertar user_message                           │
│     ├─ Insertar conversation_history                   │
│     └─ Truncar si > OPENAI_MAX_INPUT_CHARS             │
│                                                         │
│  3. LLAMADA OPENAI (timeout 5s)                        │
│     ├─ Crear HTTP client (timeout=5.0)                 │
│     ├─ POST /v1/chat/completions                       │
│     ├─ Timeout? → Generar fallback                     │
│     ├─ Error HTTP? → Generar fallback                  │
│     └─ Status != 200? → Generar fallback               │
│                                                         │
│  4. VALIDACIÓN RESPUESTA                                │
│     ├─ Vacía? → Generar fallback                       │
│     ├─ Menciona "bot/IA"? → Generar fallback           │
│     ├─ Muy larga? → Truncar                            │
│     └─ Extraer tokens_used, latency_ms                 │
│                                                         │
│  5. RETORNAR                                            │
│     └─ Tuple[suggested_reply, metadata]                │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ suggested_reply (string)
                    │ metadata (dict)
                    │
┌───────────────────▼─────────────────────────────────────┐
│  HEURÍSTICAS: Validan y usan respuesta                  │
│  - Validan que no inventa datos                         │
│  - Aseguran pregunta cerrada                            │
│  - Envían respuesta final                               │
└─────────────────────────────────────────────────────────┘
```

---

## Validaciones y Seguridad

### Validaciones Estrictas

1. **No inventar datos**:
   - Prompt incluye instrucción: "NO inventes precios, horarios, direcciones"
   - Fallback si respuesta contiene datos no proporcionados (validación opcional post-LLM)

2. **No mencionar ser IA**:
   - Validación post-LLM: buscar frases prohibidas
   - Fallback automático si detecta

3. **Timeouts duros**:
   - HTTP client: `timeout=5.0` segundos
   - Si timeout: fallback inmediato
   - No reintentos (evitar latencia acumulada)

4. **Límites de longitud**:
   - Input: truncar a `OPENAI_MAX_INPUT_CHARS` (default: 1200)
   - Output: truncar a 500 caracteres
   - Historial: máximo 6 mensajes

### Manejo de Errores

| Error | Acción | Fallback |
|-------|--------|----------|
| `OPENAI_ENABLED=false` | Retornar None inmediato | No aplicar fallback (heurísticas deben manejar) |
| `API_KEY missing` | Retornar None inmediato | No aplicar fallback |
| `Timeout 5s` | Generar fallback | Respuesta predefinida según tipo_tarea |
| `HTTP error` | Generar fallback | Respuesta predefinida según tipo_tarea |
| `Empty response` | Generar fallback | Respuesta predefinida según tipo_tarea |
| `Forbidden phrase` | Generar fallback | Respuesta predefinida según tipo_tarea |

---

## Configuración Requerida

### Variables de Entorno

```bash
# Habilitación
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...

# Modelo y parámetros
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=180
OPENAI_MAX_INPUT_CHARS=1200
OPENAI_TEMPERATURE=0.4

# Timeout (hardcoded en código: 5 segundos)
# No configurable via env (seguridad: timeout duro)
```

### Constantes del Adapter

```python
LLM_ADAPTER_TIMEOUT_SECONDS = 5.0  # Timeout duro, no configurable
LLM_ADAPTER_MAX_REPLY_LENGTH = 500  # Máximo caracteres en respuesta
LLM_ADAPTER_MAX_HISTORY_MESSAGES = 6  # Máximo mensajes en historial
```

---

## Métricas y Observabilidad

### Metadata Retornada

```python
metadata = {
    "success": bool,           # True si OpenAI respondió exitosamente
    "error": Optional[str],    # Tipo de error si falla
    "latency_ms": int,         # Latencia total en milisegundos
    "tokens_used": Optional[int],  # Tokens consumidos (si éxito)
    "fallback_used": bool,     # True si se usó fallback
    "task_type": str           # Tipo de tarea solicitada
}
```

### Logs a Generar

```python
# Éxito
logger.info(
    "llm_adapter_success",
    task_type=tipo_tarea,
    latency_ms=latency_ms,
    tokens_used=tokens_used,
    reply_length=len(suggested_reply)
)

# Fallback
logger.warning(
    "llm_adapter_fallback",
    task_type=tipo_tarea,
    error=metadata["error"],
    latency_ms=latency_ms
)

# Errores
logger.error(
    "llm_adapter_error",
    task_type=tipo_tarea,
    error=metadata["error"],
    error_details=str(e)
)
```

---

## Resumen de Diseño

### Responsabilidades del Adapter

✅ **HACE:**
- Genera texto sugerido basado en contexto estructurado
- Maneja timeouts y errores graciosamente
- Retorna fallbacks cuando falla
- Valida respuestas básicas (no vacía, no menciona ser IA)

❌ **NO HACE:**
- No decide estados de conversación
- No hace handoff
- No decide qué productos recomendar
- No decide cuándo usar OpenAI (eso lo hacen las heurísticas)
- No valida datos de negocio (eso lo hacen las heurísticas post-LLM)

### Flujo Simplificado

1. **Heurísticas** → Deciden usar LLM → Preparan contexto estructurado
2. **LLM Adapter** → Genera texto sugerido → Retorna string
3. **Heurísticas** → Validan respuesta → Envían al cliente

### Garantías del Diseño

- ✅ **Timeout duro**: Nunca espera más de 5 segundos
- ✅ **Fallback garantizado**: Siempre retorna texto (o None si deshabilitado)
- ✅ **No excepciones**: Nunca lanza excepciones, siempre retorna Tuple
- ✅ **Sin decisiones**: Solo genera texto, no toma decisiones de negocio

---

**Última actualización**: 2025-01-05  
**Estado**: Diseño listo para implementación

