# Minimum Observability Pack para Demo en Vivo

**Fecha**: 2025-01-05  
**Objetivo**: Verificar y completar instrumentación mínima para diagnosticar rápidamente problemas en demo

---

## Estado Actual de Instrumentación

### ✅ 1. Mensaje Entrante (Trace Completo)

**Ubicación**: `backend/app/routers/whatsapp.py:381` → `trace_interaction()`

**Log generado**: `logger.interaction()` en `trace_service.py:113-129`

**Campos actuales**:
- ✅ `conversation_id` - presente
- ✅ `intent` - presente (asignado en línea 405)
- ✅ `openai_called` - presente
- ✅ `decision_path` - presente (asignado en línea 500)
- ⚠️ `message_id` - **FALTA** (no se pasa al tracer)
- ⚠️ `phone` (last4) - **FALTA** (tracer usa `customer_phone_hash` pero no se loguea explícitamente en formato last4)
- ⚠️ `mode` - **FALTA** (hardcodeado como "AI_ACTIVE" en `trace_service.py:123`)

**Problema identificado**:
- El `tracer.log()` en `trace_service.py:158` se llama automáticamente, pero:
  - `mode` está hardcodeado como `"AI_ACTIVE"` (línea 123)
  - `message_id` no se guarda en el tracer
  - `phone` (last4) no se loguea explícitamente

---

### ✅ 2. Envío a WhatsApp (Success/Fail)

**Ubicación**: `backend/app/services/whatsapp_service.py:24-119`

**Logs actuales**:
- ✅ Éxito: `logger.info("Mensaje WhatsApp enviado", to=masked_phone, message_id=message_id)` (línea 89-93)
- ✅ Error: `logger.warning("Error enviando WhatsApp", to=masked_phone, status_code=..., error=error_msg, attempt=...)` (línea 98-104)
- ✅ Timeout: `logger.warning("Timeout enviando WhatsApp", to=masked_phone, attempt=...)` (línea 111)
- ✅ Excepción: `logger.error("Error inesperado enviando WhatsApp", error=str(e), attempt=...)` (línea 113)

**Problema identificado**:
- ✅ Error está sanitizado (solo `error_msg` de la API, no tokens)
- ⚠️ Falta `conversation_id` en logs de envío (no se pasa a `send_whatsapp_message`)
- ⚠️ Falta `message_id` del mensaje entrante en logs de envío (no se puede correlacionar)

---

## Logs Faltantes (Máximo 2)

### 🔴 Log 1: "Por qué se activó HUMAN_ACTIVE"

**Estado actual**:
- Existe: `logger.info("Handoff procesado", conversation_id=..., team=..., priority=..., reason=...)` en `handoff_service.py:327-333`
- Problema: El log no incluye suficiente contexto para diagnóstico rápido

**Lo que falta**:
- Texto del usuario que triggeó el handoff
- Keywords detectados que activaron la regla
- `message_id` del mensaje que activó el handoff
- `phone` (last4) para correlación

**Ubicación para agregar**: `backend/app/services/handoff_service.py:327` (después de `set_conversation_mode`)

---

### 🔴 Log 2: "Por qué se decidió usar OpenAI"

**Estado actual**:
- Existe: `logger.info("LLM Adapter usado exitosamente", reason_for_llm_use=...)` en `response_service.py:779-788`
- Problema: Este log se genera DESPUÉS de llamar OpenAI, no cuando se DECIDE usarlo

**Lo que falta**:
- Log cuando se DECIDE usar OpenAI (antes de llamarlo)
- Incluir: `reason_for_llm_use`, `task_type`, `gating_reason` (por qué pasó el gating)
- `message_id` para correlación

**Ubicación para agregar**: `backend/app/services/response_service.py:709-716` (dentro de `should_call_openai` check, antes de llamar al adapter)

---

## Checklist: Logs "Debe Existir"

### Mensaje Entrante (Procesado)

| Campo | Estado | Ubicación Actual | Acción Requerida |
|-------|--------|------------------|------------------|
| `conversation_id` | ✅ Existe | `trace_service.py:117` | Ninguna |
| `message_id` | ⚠️ Falta | - | Agregar al tracer |
| `phone` (last4) | ⚠️ Falta | - | Agregar al tracer |
| `intent` | ✅ Existe | `trace_service.py:120` | Ninguna |
| `mode` | ⚠️ Incorrecto | `trace_service.py:123` (hardcoded) | Obtener del contexto |
| `openai_called` | ✅ Existe | `trace_service.py:124` | Ninguna |
| `decision_path` | ✅ Existe | `trace_service.py:128` | Ninguna |

---

### Envío a WhatsApp

| Campo | Estado | Ubicación Actual | Acción Requerida |
|-------|--------|------------------|------------------|
| Success log | ✅ Existe | `whatsapp_service.py:89` | Agregar `conversation_id`, `message_id` (entrante) |
| Fail log | ✅ Existe | `whatsapp_service.py:98` | Agregar `conversation_id`, `message_id` (entrante) |
| Error sanitizado | ✅ Existe | `whatsapp_service.py:97` | Ninguna |

---

## Propuestas de Implementación

### Log 1: "human_active_triggered"

**Ubicación**: `backend/app/services/handoff_service.py:327` (después de línea 324)

**Formato exacto**:
```python
logger.info(
    "human_active_triggered",
    conversation_id=conversation_id,
    message_id=message_id,  # Agregar como parámetro a process_handoff
    phone=customer_phone[-4:] if customer_phone else "unknown",
    reason=decision.reason,
    priority=decision.priority.value,
    team=team.value if team else None,
    user_text=text[:100],  # Primeros 100 caracteres
    trigger_keywords=[kw for kw in IMPACTO_NEGOCIO | INSTALACION | VISITA | URGENTE | PROBLEMAS if kw in text_lower][:3]  # Primeros 3 keywords detectados
)
```

**Modificaciones requeridas**:
1. Agregar `message_id: Optional[str] = None` como parámetro a `process_handoff()` en línea 265
2. Pasar `message_id` desde `whatsapp.py:434` al llamar `process_handoff()`
3. Agregar el log después de `set_conversation_mode()` en línea 324

**Ejemplo de salida**:
```json
{
  "level": "INFO",
  "message": "human_active_triggered",
  "conversation_id": "wa_573001234567",
  "message_id": "wamid.xxx",
  "phone": "4567",
  "reason": "Cliente requiere asesoría para proyecto de negocio",
  "priority": "high",
  "team": "comercial",
  "user_text": "quiero montar un taller de confección, qué necesito?",
  "trigger_keywords": ["montar negocio", "emprendimiento"]
}
```

---

### Log 2: "openai_decision_made"

**Ubicación**: `backend/app/services/response_service.py:718` (después de línea 716, antes de línea 718)

**Formato exacto**:
```python
logger.info(
    "openai_decision_made",
    conversation_id=conversation_id,
    message_id=message_id,  # Agregar como parámetro o del contexto
    phone=customer_number[-4:] if customer_number else "unknown",
    intent=tracer.intent,
    task_type=task_type,
    reason_for_llm_use=reason_for_llm_use,
    gating_passed=True,  # Si llegó aquí, pasó el gating
    gating_reason="cache_miss_and_consult"  # Ejemplo: explicar por qué pasó el gating
)
```

**Modificaciones requeridas**:
1. El log debe ir ANTES de llamar `get_llm_suggestion_sync()` en línea 751
2. Necesita acceso a `message_id` (puede venir del tracer o como parámetro adicional)
3. Agregar `gating_reason` explicando por qué se decidió usar OpenAI

**Ejemplo de salida**:
```json
{
  "level": "INFO",
  "message": "openai_decision_made",
  "conversation_id": "wa_573001234567",
  "message_id": "wamid.xxx",
  "phone": "4567",
  "intent": "buscar_maquina_industrial",
  "task_type": "copy",
  "reason_for_llm_use": "copy:buscar_maquina_industrial:business_consult",
  "gating_passed": true,
  "gating_reason": "intent_requires_custom_copy_and_cache_miss"
}
```

---

### Fix 1: Completar Trace de Mensaje Entrante

**Ubicación**: `backend/app/routers/whatsapp.py:381` y `backend/app/services/trace_service.py:113-129`

**Modificaciones**:
1. Pasar `message_id` al tracer en `whatsapp.py:381`:
   ```python
   with trace_interaction(conversation_id, "whatsapp", phone_from) as tracer:
       tracer.raw_text = text
       tracer.normalized_text = text.lower().strip()
       tracer.message_id = message_id  # NUEVO: Agregar campo message_id
   ```

2. Agregar campo `message_id` a `InteractionTracer` en `trace_service.py:14-37`:
   ```python
   message_id: Optional[str] = None
   ```

3. Obtener `mode` real en `trace_service.py:123`:
   ```python
   mode = mode if 'mode' in locals() else "AI_ACTIVE"  # Obtener del contexto si está disponible
   ```

4. Incluir `message_id` y `phone` (last4) en `tracer.log()` en `trace_service.py:113-129`:
   ```python
   def log(self) -> None:
       """Registra la interacción en los logs estructurados."""
       phone_last4 = self.customer_phone[-4:] if self.customer_phone and len(self.customer_phone) >= 4 else "unknown"
       
       logger.interaction(
           request_id=self.request_id,
           conversation_id=self.conversation_id,
           message_id=self.message_id,  # NUEVO
           phone=phone_last4,  # NUEVO
           channel=self.channel,
           business_related=self.business_related,
           intent=self.intent,
           routed_team=self.routed_team,
           asset_id=self.selected_asset_id,
           mode=self.mode if hasattr(self, 'mode') else "AI_ACTIVE",  # NUEVO: obtener mode real
           openai_called=self.openai_called,
           cache_hit=self.cache_hit,
           latency_ms=self._latency_ms,
           latency_us=self._latency_us,
           error_message=self.error_message
       )
   ```

5. Pasar `mode` al tracer en `whatsapp.py:381`:
   ```python
   with trace_interaction(conversation_id, "whatsapp", phone_from) as tracer:
       tracer.raw_text = text
       tracer.normalized_text = text.lower().strip()
       tracer.message_id = message_id  # NUEVO
       tracer.mode = mode  # NUEVO: mode obtenido en línea 293 o después de TTL check
   ```

---

### Fix 2: Mejorar Logs de Envío WhatsApp

**Ubicación**: `backend/app/services/whatsapp_service.py:89, 98, 111, 113`

**Modificaciones**:
1. Agregar `conversation_id` y `message_id` (entrante) como parámetros opcionales a `send_whatsapp_message()` en línea 24:
   ```python
   async def send_whatsapp_message(
       to: str,
       text: str,
       retry_count: int = 2,
       conversation_id: Optional[str] = None,  # NUEVO
       incoming_message_id: Optional[str] = None  # NUEVO
   ) -> Tuple[bool, Optional[str]]:
   ```

2. Incluir en logs de éxito (línea 89):
   ```python
   logger.info(
       "Mensaje WhatsApp enviado",
       to=masked_phone,
       message_id=message_id,  # message_id del mensaje enviado
       conversation_id=conversation_id,  # NUEVO
       incoming_message_id=incoming_message_id  # NUEVO
   )
   ```

3. Incluir en logs de error (línea 98):
   ```python
   logger.warning(
       "Error enviando WhatsApp",
       to=masked_phone,
       status_code=response.status_code,
       error=error_msg,
       attempt=attempt + 1,
       conversation_id=conversation_id,  # NUEVO
       incoming_message_id=incoming_message_id  # NUEVO
   )
   ```

4. Pasar estos parámetros desde `whatsapp.py:359, 394, 513`:
   ```python
   success, error_info = await send_whatsapp_message(
       phone_from, 
       response_text,
       conversation_id=conversation_id,  # NUEVO
       incoming_message_id=message_id  # NUEVO
   )
   ```

---

## Resumen Ejecutivo

### Logs Actuales (✅ Completo)

1. ✅ **Mensaje entrante (trace)**: Existe pero falta `message_id`, `phone` (last4), `mode` correcto
2. ✅ **Envío WhatsApp (success/fail)**: Existe pero falta `conversation_id`, `message_id` (entrante) para correlación

### Logs Faltantes (🔴 Críticos)

1. 🔴 **`human_active_triggered`**: No existe log explícito con contexto completo de por qué se activó
2. 🔴 **`openai_decision_made`**: No existe log cuando se DECIDE usar OpenAI (solo después de llamarlo)

### Acciones Requeridas (5 cambios)

1. **`trace_service.py`**: Agregar `message_id`, `phone` (last4), `mode` real al log de interacción
2. **`whatsapp.py:381`**: Pasar `message_id` y `mode` al tracer
3. **`handoff_service.py:327`**: Agregar log `human_active_triggered` con contexto completo
4. **`response_service.py:718`**: Agregar log `openai_decision_made` antes de llamar OpenAI
5. **`whatsapp_service.py:24`**: Agregar `conversation_id` y `incoming_message_id` a logs de envío

---

## Formato Final de Logs

### Log: "human_active_triggered"

**Event name**: `human_active_triggered`  
**Level**: `INFO`  
**Ubicación**: `handoff_service.py:327`

**Campos**:
- `conversation_id` (string)
- `message_id` (string, primeros 20 chars)
- `phone` (string, últimos 4 dígitos)
- `reason` (string, razón del handoff)
- `priority` (string, "urgent" | "high" | "medium")
- `team` (string, "comercial" | "tecnica")
- `user_text` (string, primeros 100 caracteres)
- `trigger_keywords` (array, primeros 3 keywords detectados)

---

### Log: "openai_decision_made"

**Event name**: `openai_decision_made`  
**Level**: `INFO`  
**Ubicación**: `response_service.py:718`

**Campos**:
- `conversation_id` (string)
- `message_id` (string, primeros 20 chars)
- `phone` (string, últimos 4 dígitos)
- `intent` (string)
- `task_type` (string, "copy" | "explicacion" | "objecion" | "consulta_compleja")
- `reason_for_llm_use` (string, formato: "task:intent:message_type")
- `gating_passed` (boolean, siempre true si llegó aquí)
- `gating_reason` (string, explicación breve: "cache_miss_and_consult", "intent_requires_custom_copy", etc.)

---

## Ejemplos de Queries para Demo

### Ver todos los mensajes de una conversación
```bash
docker compose logs backend | grep "conversation_id=wa_573001234567"
```

### Ver por qué se activó HUMAN_ACTIVE
```bash
docker compose logs backend | grep "human_active_triggered" | tail -5
```

### Ver decisiones de uso de OpenAI
```bash
docker compose logs backend | grep "openai_decision_made" | tail -10
```

### Ver errores de envío WhatsApp
```bash
docker compose logs backend | grep "Error enviando WhatsApp" | tail -10
```

### Ver trace completo de un mensaje (correlacionar entrada y salida)
```bash
docker compose logs backend | grep -E "message_id=wamid\.xxx|conversation_id=wa_573001234567"
```

---

**Última actualización**: 2025-01-05  
**Estado**: ✅ Revisado, faltan 2 logs críticos + fixes de trace

