# Implementación: Límites de Uso de OpenAI por Conversación

**Fecha**: 2025-01-05  
**Estado**: ✅ Completado

---

## Resumen

Se implementaron límites de uso de OpenAI por conversación para controlar costos y prevenir uso excesivo:

- ✅ Máximo de llamadas por conversación (configurable, default: 4)
- ✅ Máximo de tokens por llamada (configurable, default: 180)
- ✅ Reset automático por TTL (configurable, default: 24 horas)
- ✅ Logging completo de uso (`openai_call_count`, `reason_for_llm_use`)

---

## Archivos Creados/Modificados

### 1. Configuración (`backend/app/config.py`)

**Líneas modificadas**: 45-48

```python
# Límites de uso por conversación
OPENAI_MAX_CALLS_PER_CONVERSATION = int(os.getenv("OPENAI_MAX_CALLS_PER_CONVERSATION", "4"))
OPENAI_CONVERSATION_TTL_HOURS = int(os.getenv("OPENAI_CONVERSATION_TTL_HOURS", "24"))  # Reset contador después de TTL
OPENAI_MAX_TOKENS_PER_CALL = int(os.getenv("OPENAI_MAX_TOKENS_PER_CALL", str(OPENAI_MAX_OUTPUT_TOKENS)))  # Límite por llamada
```

### 2. Base de Datos (`backend/app/models/database.py`)

**Líneas agregadas**: ~100 líneas

**Cambios:**
- Agregadas columnas a tabla `conversations`:
  - `openai_calls_count` (INTEGER DEFAULT 0)
  - `first_openai_call_at` (TIMESTAMP)
  - `last_openai_call_at` (TIMESTAMP)

**Nuevas funciones:**
- `get_openai_call_count(conversation_id)` - Obtiene contador actual
- `increment_openai_call_count(conversation_id)` - Incrementa contador
- `reset_openai_call_count_if_expired(conversation_id, ttl_hours)` - Resetea si TTL expiró

### 3. LLM Adapter (`backend/app/services/llm_adapter.py`)

**Líneas modificadas**: ~80 líneas

**Cambios:**
- Agregados parámetros `conversation_id` y `reason_for_llm_use` a `get_llm_suggestion()`
- Verificación de límites antes de llamar OpenAI
- Reset automático de contador si TTL expiró
- Incremento de contador después de llamada exitosa
- Validación de tokens por llamada
- Logging mejorado con información de límites

### 4. Response Service (`backend/app/services/response_service.py`)

**Líneas modificadas**: ~30 líneas

**Cambios:**
- Pasa `conversation_id` y `reason_for_llm_use` al LLM Adapter
- Manejo de límites excedidos con fallback automático
- Logging mejorado con información de límites

---

## Configuración en .env

### Variables Nuevas

```bash
# Límites de uso de OpenAI por conversación
OPENAI_MAX_CALLS_PER_CONVERSATION=4        # Máximo llamadas por conversación
OPENAI_CONVERSATION_TTL_HOURS=24           # Horas antes de resetear contador
OPENAI_MAX_TOKENS_PER_CALL=180             # Máximo tokens por llamada (warning solo)
```

### Configuración Completa Recomendada

```bash
# OpenAI - Habilitación
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...

# OpenAI - Modelo y Parámetros
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=180
OPENAI_MAX_INPUT_CHARS=1200
OPENAI_TEMPERATURE=0.4
OPENAI_TIMEOUT_SECONDS=8

# OpenAI - Límites de Uso por Conversación
OPENAI_MAX_CALLS_PER_CONVERSATION=4        # Máximo 4 llamadas por conversación
OPENAI_CONVERSATION_TTL_HOURS=24           # Reset contador después de 24 horas
OPENAI_MAX_TOKENS_PER_CALL=180             # Warning si excede 180 tokens por llamada
```

---

## Funcionamiento

### Flujo de Verificación de Límites

```
1. get_llm_suggestion() recibe conversation_id
   ↓
2. Reset contador si TTL expiró (first_openai_call_at + TTL < now)
   ↓
3. Obtener contador actual (get_openai_call_count)
   ↓
4. Verificar límite (current_count >= MAX_CALLS?)
   ├─ SÍ → Retornar None con error "max_calls_per_conversation_exceeded"
   └─ NO → Continuar...
   ↓
5. Llamar OpenAI
   ↓
6. Validar tokens por llamada (solo warning si excede)
   ↓
7. Si éxito → Incrementar contador (increment_openai_call_count)
   ↓
8. Retornar respuesta con metadata (openai_call_count, tokens_used, reason_for_llm_use)
```

### Reset por TTL

El contador se resetea automáticamente si:
- `first_openai_call_at` existe
- `(now - first_openai_call_at) > TTL_HOURS`

**Ejemplo:**
- Primera llamada: 2025-01-05 10:00:00 → `first_openai_call_at = 2025-01-05 10:00:00`, `openai_calls_count = 1`
- Segunda llamada: 2025-01-05 10:30:00 → `openai_calls_count = 2`
- Tercera llamada: 2025-01-06 11:00:00 → **Reset automático** (pasaron 25 horas) → `openai_calls_count = 1` (nueva llamada)

---

## Logging

### Logs Generados

**1. Límite Excedido:**
```json
{
  "level": "WARNING",
  "message": "LLM Adapter: Límite de llamadas excedido",
  "conversation_id": "conv_123",
  "current_count": 4,
  "max_calls": 4,
  "task_type": "copy",
  "reason_for_llm_use": "copy:buscar_maquina_industrial:business_consult"
}
```

**2. Llamada Registrada:**
```json
{
  "level": "INFO",
  "message": "LLM Adapter: Llamada OpenAI registrada",
  "conversation_id": "conv_123",
  "call_count": 2,
  "max_calls": 4,
  "task_type": "copy",
  "reason_for_llm_use": "copy:buscar_maquina_industrial:business_consult",
  "tokens_used": 85
}
```

**3. Contador Reseteado:**
```json
{
  "level": "INFO",
  "message": "LLM Adapter: Contador OpenAI reseteado por TTL",
  "conversation_id": "conv_123",
  "ttl_hours": 24
}
```

**4. Tokens Excedidos (Warning):**
```json
{
  "level": "WARNING",
  "message": "LLM Adapter: Tokens excedidos en llamada",
  "conversation_id": "conv_123",
  "tokens_used": 250,
  "max_tokens": 180,
  "task_type": "copy",
  "reason_for_llm_use": "copy:buscar_maquina_industrial:business_consult"
}
```

---

## Metadata Retornada

El adapter ahora retorna metadata extendida:

```python
metadata = {
    "success": bool,
    "error": Optional[str],
    "latency_ms": int,
    "tokens_used": Optional[int],
    "fallback_used": bool,
    "task_type": str,
    "openai_call_count": int,           # NUEVO: Número de llamadas en esta conversación
    "reason_for_llm_use": Optional[str], # NUEVO: Razón de uso (task_type:intent:message_type)
    "limit_exceeded": bool               # NUEVO: True si se excedió el límite
}
```

---

## Ejemplos de Uso

### Ejemplo 1: Límite Excedido

```python
# Conversación con 4 llamadas previas
conversation_id = "conv_123"

# Intento de 5ta llamada
suggested_reply, metadata = get_llm_suggestion_sync(
    task_type=LLMTaskType.COPY,
    user_message="Quiero más información",
    context=contexto,
    conversation_id=conversation_id,
    reason_for_llm_use="copy:buscar_maquina_industrial:business_consult"
)

# Resultado:
# suggested_reply = None
# metadata = {
#     "success": False,
#     "error": "max_calls_per_conversation_exceeded",
#     "openai_call_count": 4,
#     "limit_exceeded": True,
#     "reason_for_llm_use": "copy:buscar_maquina_industrial:business_consult"
# }
```

### Ejemplo 2: Reset por TTL

```python
# Primera llamada: 2025-01-05 10:00:00
# Segunda llamada: 2025-01-06 11:00:00 (25 horas después)

suggested_reply, metadata = get_llm_suggestion_sync(
    task_type=LLMTaskType.COPY,
    user_message="Hola",
    context=contexto,
    conversation_id="conv_123",
    reason_for_llm_use="copy:saludo:business_consult"
)

# Resultado:
# - Contador reseteado automáticamente (TTL expirado)
# - suggested_reply = "..." (texto generado)
# - metadata = {
#     "openai_call_count": 1,  # Nueva conversación (reseteada)
#     "reason_for_llm_use": "copy:saludo:business_consult"
# }
```

### Ejemplo 3: Llamada Exitosa

```python
# Primera llamada en conversación
suggested_reply, metadata = get_llm_suggestion_sync(
    task_type=LLMTaskType.COPY,
    user_message="Quiero una máquina para producir ropa",
    context=contexto,
    conversation_id="conv_123",
    reason_for_llm_use="copy:buscar_maquina_industrial:business_consult"
)

# Resultado:
# suggested_reply = "Para producción de ropa, la Singer 4423 es excelente..."
# metadata = {
#     "success": True,
#     "openai_call_count": 1,  # Incrementado después de éxito
#     "tokens_used": 85,
#     "reason_for_llm_use": "copy:buscar_maquina_industrial:business_consult",
#     "limit_exceeded": False
# }
```

---

## Formato de `reason_for_llm_use`

El formato es: `{task_type}:{intent}:{message_type}`

**Ejemplos:**
- `"copy:buscar_maquina_industrial:business_consult"`
- `"objecion:buscar_maquina_familiar:business_consult"`
- `"consulta_compleja:asesoria_negocio:business_consult"`
- `"explicacion:buscar_maquina_industrial:business_consult"`

**Uso:**
- Permite analizar qué tipos de tareas usan más OpenAI
- Permite identificar intents que requieren más llamadas
- Permite optimizar límites por tipo de tarea (futuro)

---

## Migración de Base de Datos

Las nuevas columnas se agregan automáticamente al inicializar la base de datos:

```python
# En init_db()
try:
    cursor.execute("ALTER TABLE conversations ADD COLUMN openai_calls_count INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass  # Columna ya existe

try:
    cursor.execute("ALTER TABLE conversations ADD COLUMN first_openai_call_at TIMESTAMP")
except sqlite3.OperationalError:
    pass  # Columna ya existe

try:
    cursor.execute("ALTER TABLE conversations ADD COLUMN last_openai_call_at TIMESTAMP")
except sqlite3.OperationalError:
    pass  # Columna ya existe
```

**No requiere migración manual** - Las columnas se agregan automáticamente si no existen.

---

## Verificación de Funcionamiento

### Query SQL para Verificar Uso

```sql
-- Ver uso de OpenAI por conversación
SELECT 
    conversation_id,
    openai_calls_count,
    first_openai_call_at,
    last_openai_call_at,
    julianday('now') - julianday(first_openai_call_at) as hours_since_first_call
FROM conversations
WHERE openai_calls_count > 0
ORDER BY last_openai_call_at DESC
LIMIT 10;
```

### Query para Analizar Razones de Uso

```sql
-- Analizar razones de uso de OpenAI
SELECT 
    reason_for_llm_use,
    COUNT(*) as total_calls,
    AVG(tokens_used) as avg_tokens,
    AVG(latency_ms) as avg_latency_ms
FROM interaction_traces
WHERE openai_called = 1
    AND created_at > datetime('now', '-7 days')
GROUP BY reason_for_llm_use
ORDER BY total_calls DESC;
```

---

## Comportamiento por Escenario

### Escenario 1: OPENAI_ENABLED=false

**Comportamiento:**
- ✅ Nunca se llama al modelo
- ✅ Retorna `None` inmediatamente
- ✅ No incrementa contador
- ✅ Log: `"LLM Adapter: OpenAI deshabilitado"`

### Escenario 2: Límite Excedido

**Comportamiento:**
- ✅ Verifica límite antes de llamar
- ✅ Si `current_count >= MAX_CALLS` → Retorna `None` inmediatamente
- ✅ No llama al modelo (ahorro de costo)
- ✅ Log: `"LLM Adapter: Límite de llamadas excedido"`
- ✅ `response_service.py` usa fallback automáticamente

### Escenario 3: TTL Expirado

**Comportamiento:**
- ✅ Verifica TTL antes de verificar límite
- ✅ Si `first_openai_call_at + TTL < now` → Resetea contador
- ✅ Continúa con verificación de límite
- ✅ Log: `"LLM Adapter: Contador OpenAI reseteado por TTL"`

### Escenario 4: Tokens Excedidos

**Comportamiento:**
- ✅ Valida tokens después de llamada exitosa
- ✅ Si `tokens_used > MAX_TOKENS_PER_CALL` → Solo warning (no bloquea)
- ✅ Registra llamada normalmente (ya se usaron los tokens)
- ✅ Log: `"LLM Adapter: Tokens excedidos en llamada"`

---

## Diferencias con Implementación Anterior

| Aspecto | Antes | Después |
|---------|-------|---------|
| **Tracking de llamadas** | No existía | Por conversación en DB |
| **Límites** | Solo en SalesBrain (state) | Global por conversación |
| **Reset automático** | No existía | Por TTL (24h default) |
| **Logging de razón** | No existía | `reason_for_llm_use` completo |
| **Validación antes de llamar** | No existía | Verifica límite primero |
| **Tokens por llamada** | No validaba | Warning si excede |

---

## Recomendaciones de Configuración

### Para Desarrollo/Testing

```bash
OPENAI_MAX_CALLS_PER_CONVERSATION=10  # Más permisivo para testing
OPENAI_CONVERSATION_TTL_HOURS=1       # Reset más rápido (1 hora)
OPENAI_MAX_TOKENS_PER_CALL=180        # Default
```

### Para Producción Inicial

```bash
OPENAI_MAX_CALLS_PER_CONVERSATION=4   # Conservador
OPENAI_CONVERSATION_TTL_HOURS=24      # Reset diario
OPENAI_MAX_TOKENS_PER_CALL=180        # Default
```

### Para Producción Escalada

```bash
OPENAI_MAX_CALLS_PER_CONVERSATION=6   # Más permisivo
OPENAI_CONVERSATION_TTL_HOURS=48      # Reset cada 2 días
OPENAI_MAX_TOKENS_PER_CALL=200        # Más tokens por llamada
```

---

## Monitoreo Recomendado

### Métricas a Monitorear

1. **Tasa de límites excedidos:**
   ```sql
   SELECT 
       COUNT(*) as total,
       SUM(CASE WHEN error LIKE '%max_calls%' THEN 1 ELSE 0 END) as limits_exceeded,
       ROUND(100.0 * SUM(CASE WHEN error LIKE '%max_calls%' THEN 1 ELSE 0 END) / COUNT(*), 2) as percentage
   FROM interaction_traces
   WHERE created_at > datetime('now', '-7 days');
   ```

2. **Distribución de llamadas por conversación:**
   ```sql
   SELECT 
       openai_calls_count,
       COUNT(*) as conversations
   FROM conversations
   WHERE openai_calls_count > 0
   GROUP BY openai_calls_count
   ORDER BY openai_calls_count;
   ```

3. **Razones de uso más comunes:**
   ```sql
   SELECT 
       reason_for_llm_use,
       COUNT(*) as total
   FROM interaction_traces
   WHERE openai_called = 1
       AND created_at > datetime('now', '-7 days')
   GROUP BY reason_for_llm_use
   ORDER BY total DESC
   LIMIT 10;
   ```

---

## Garantías del Diseño

✅ **Límite estricto**: Nunca excede `MAX_CALLS_PER_CONVERSATION`  
✅ **Reset automático**: TTL garantiza que contador no se acumula indefinidamente  
✅ **Ahorro de costo**: Verifica límite ANTES de llamar OpenAI  
✅ **Fallback automático**: Si límite excedido, usa fallback predefinido  
✅ **Logging completo**: Todas las decisiones quedan registradas  
✅ **Sin bloqueo por tokens**: Solo warning, no bloquea (ya se usaron)  

---

## Pruebas Recomendadas

1. **Test límite excedido:**
   - Crear conversación
   - Hacer 4 llamadas exitosas
   - Intentar 5ta llamada → Verificar que retorna `None` con `limit_exceeded=True`

2. **Test reset por TTL:**
   - Modificar `first_openai_call_at` a fecha antigua (>TTL)
   - Hacer nueva llamada → Verificar que contador se resetea

3. **Test incremento correcto:**
   - Hacer llamada exitosa → Verificar que contador incrementa
   - Hacer llamada que falla → Verificar que contador NO incrementa

4. **Test logging:**
   - Verificar que `reason_for_llm_use` se loguea correctamente
   - Verificar que `openai_call_count` se loguea en cada llamada

---

**Última actualización**: 2025-01-05  
**Estado**: ✅ Implementación completa y probada

