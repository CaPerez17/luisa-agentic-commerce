# Implementación: LLM Adapter para LUISA

**Fecha**: 2025-01-05  
**Estado**: ✅ Completado

---

## Archivos Creados/Modificados

### 1. Archivo Nuevo

**`backend/app/services/llm_adapter.py`** (554 líneas)

- Módulo nuevo con el LLM Adapter
- Función principal: `get_llm_suggestion()` (async)
- Wrapper síncrono: `get_llm_suggestion_sync()`
- Helpers para plantillas, fallbacks, validaciones

### 2. Archivo Modificado

**`backend/app/services/response_service.py`** (+164 líneas, -10 líneas)

- Integración del LLM Adapter reemplazando `generate_openai_response_sync()`
- Helper: `_determine_llm_task_type()` - Determina tipo de tarea (copy/explicacion/objecion/consulta_compleja)
- Helper: `_prepare_context_for_llm_adapter()` - Prepara contexto estructurado

---

## Cambios Principales

### 1. Nuevo LLM Adapter (`llm_adapter.py`)

**Función Principal:**
```python
async def get_llm_suggestion(
    task_type: str,  # "copy", "explicacion", "objecion", "consulta_compleja"
    user_message: str,
    context: Dict[str, Any],  # Contexto estructurado
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Genera texto sugerido usando OpenAI.
    
    SOLO genera texto. NO toma decisiones de negocio.
    Retorna: (suggested_reply, metadata)
    """
```

**Características:**
- ✅ Timeout duro: 5 segundos
- ✅ Fallback garantizado si OpenAI falla
- ✅ Validación de respuesta (no vacía, no menciona ser IA)
- ✅ Logging seguro (sin secretos)
- ✅ Controlado por `OPENAI_ENABLED`

### 2. Integración en `response_service.py`

**Reemplazo de llamada antigua:**
```python
# ANTES:
openai_response, openai_latency = generate_openai_response_sync(
    text_for_openai, context, history_for_openai
)

# DESPUÉS:
task_type = _determine_llm_task_type(text, intent, context, message_type)
contexto_estructurado = _prepare_context_for_llm_adapter(context, intent, asset)

suggested_reply, adapter_metadata = get_llm_suggestion_sync(
    task_type=task_type,
    user_message=text,
    context=contexto_estructurado,
    conversation_history=history_formatted
)
```

**Ubicación:** Líneas 617-683 en `response_service.py`

---

## Diferencias Clave

### Antes vs Después

| Aspecto | Antes | Después |
|---------|-------|---------|
| **Función** | `generate_openai_response_sync()` | `get_llm_suggestion_sync()` |
| **Retorno** | `(text, latency_ms)` | `(suggested_reply, metadata)` |
| **Fallback** | Retorna `None` si falla | Genera fallback automáticamente |
| **Task Type** | No especificado | Determinado según contexto |
| **Contexto** | Formato genérico | Formato estructurado específico |
| **Validación** | Básica | Completa (vacío, IA, longitud) |
| **Timeout** | `OPENAI_TIMEOUT_SECONDS` (8s) | `5.0` segundos (duro) |

---

## Tipos de Tarea Soportados

1. **`LLMTaskType.COPY`** - Redacción comercial natural (Categoría B)
2. **`LLMTaskType.EXPLICACION`** - Explicación técnica/comparación (Categoría B)
3. **`LLMTaskType.OBJECION`** - Manejo de objeciones (Categoría C)
4. **`LLMTaskType.CONSULTA_COMPLEJA`** - Consultas complejas (Categoría C)

---

## Flujo de Integración

```
1. should_call_openai() → Determina si usar OpenAI
2. _determine_llm_task_type() → Determina tipo de tarea
3. _prepare_context_for_llm_adapter() → Prepara contexto estructurado
4. get_llm_suggestion_sync() → Genera texto sugerido
5. Validación y uso del texto sugerido
6. Post-procesamiento (ensure_next_step_question)
```

---

## Garantías del Diseño

✅ **OpenAI NO decide estados**: Solo genera texto, no cambia `conversation_mode`, `state`, etc.  
✅ **OpenAI NO hace handoff**: No decide cuándo escalar a humano  
✅ **OpenAI NO responde solo**: Siempre devuelve `suggested_reply` para validación  
✅ **OpenAI solo devuelve TEXTO**: String puro, sin metadatos de decisión  
✅ **Timeout duro**: 5 segundos máximo  
✅ **Fallback garantizado**: Siempre retorna texto (o None si deshabilitado)  
✅ **Controlado por OPENAI_ENABLED**: Si `false`, nunca llama al modelo  

---

## Ejemplo de Uso

```python
# Preparar contexto estructurado
contexto = {
    "productos_recomendados": [
        {"nombre": "Singer 4423", "precio": 1800000, "caracteristicas": [...]}
    ],
    "datos_negocio": {
        "horarios": "Lunes a Sábado 8am-6pm",
        "direccion": "Montería, Córdoba",
        "formas_pago": ["Addi", "Sistecrédito"]
    },
    "contexto_conversacion": {
        "intent_detectado": "buscar_maquina_industrial",
        "tipo_maquina": "industrial"
    }
}

# Llamar adapter
suggested_reply, metadata = get_llm_suggestion_sync(
    task_type=LLMTaskType.COPY,
    user_message="Quiero una máquina para producir ropa",
    context=contexto
)

# Resultado:
# suggested_reply = "Para producción de ropa, la Singer 4423 es excelente. 
#                    Cuesta $1.800.000. ¿Te interesa esta opción?"
# metadata = {"success": True, "latency_ms": 1200, "tokens_used": 85, ...}
```

---

## Logging Seguro

El adapter loguea información útil sin exponer secretos:

```python
logger.info("LLM Adapter usado exitosamente", 
    task_type="copy",
    latency_ms=1200,
    tokens_used=85,
    fallback_used=False
)

logger.warning("LLM Adapter fallback usado",
    task_type="copy",
    error="timeout_5s"
)
```

**Nunca loguea:**
- API keys
- Mensajes completos del usuario (solo truncados)
- Respuestas completas (solo longitudes)

---

## Configuración Requerida

```bash
# Habilitación
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...

# Modelo y parámetros (ya configurados)
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=180
OPENAI_TEMPERATURE=0.4
```

**Nota**: El timeout está hardcodeado a 5 segundos por seguridad (no configurable).

---

## Pruebas Recomendadas

1. **Con OPENAI_ENABLED=false**:
   - Verificar que nunca se llama al modelo
   - Verificar que retorna `None` inmediatamente

2. **Con OPENAI_ENABLED=true y timeout**:
   - Simular timeout (>5s)
   - Verificar que retorna fallback automáticamente

3. **Con respuesta inválida**:
   - Simular respuesta que menciona "soy un bot"
   - Verificar que retorna fallback

4. **Con contexto insuficiente**:
   - Llamar sin datos del negocio
   - Verificar que retorna `None` con error apropiado

---

**Última actualización**: 2025-01-05  
**Estado**: ✅ Implementación completa

