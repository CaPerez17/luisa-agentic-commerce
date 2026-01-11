# Checklist Demo-Proof para WhatsApp Real

**Fecha**: 2025-01-05  
**Objetivo**: Identificar TODOS los puntos donde LUISA podría NO responder en WhatsApp real

---

## Mapa: Condición → Respuesta Esperada → Log Esperado → Archivo:Línea

### P0: No Respuesta (SILENCIO TOTAL)

| # | Condición | Respuesta | Log Esperado (event_name) | Archivo:Línea |
|---|-----------|-----------|---------------------------|---------------|
| **1** | `WHATSAPP_ENABLED=false` en POST webhook | ❌ Return `{"status": "disabled"}` sin procesar | ❌ **NO HAY LOG** (solo return) | `whatsapp.py:87` |
| **2** | Webhook sin JSON válido | ❌ Return `{"status": "ok"}` sin procesar | ⚠️ `"Webhook recibido sin JSON válido"` (warning) | `whatsapp.py:92` |
| **3** | Webhook solo tiene statuses (no messages) | ❌ Return `{"status": "ok"}` sin procesar | ✅ `"Webhook ignorado (solo statuses)"` (info, decision_path="ignore_status_event") | `whatsapp.py:101-108` |
| **4** | Webhook sin messages | ❌ Return `{"status": "ok"}` sin procesar | ✅ `"Webhook ignorado (sin messages)"` (info, decision_path="no_messages_skip") | `whatsapp.py:112-118` |
| **5** | Parse de webhook falla | ❌ Return `{"status": "ok"}` sin procesar | ✅ `"Webhook ignorado (parse falló)"` (info, decision_path="parse_failed_skip") | `whatsapp.py:124-131` |
| **6** | Mensaje duplicado (idempotencia) | ❌ Return `{"status": "ok", "dedup": True}` sin procesar | ✅ `"Mensaje WhatsApp duplicado (dedup)"` (info, decision_path="dedup_skip") | `whatsapp.py:143-150` |
| **7** | Race condition: mensaje ya procesado | ❌ Return `{"status": "ok", "dedup": True}` sin procesar | ✅ `"Mensaje WhatsApp duplicado (race condition)"` (info, decision_path="dedup_skip") | `whatsapp.py:158-165` |
| **8** | Rate limit excedido (>20 req/min) | ❌ Return HTTP 429 sin procesar | ⚠️ `"Rate limit WhatsApp"` (warning) | `whatsapp.py:170-176` |
| **9** | Mensaje no es de texto (imagen/audio) | ❌ Return `None` en parse, luego `{"status": "ok"}` | ✅ `"Mensaje no es de texto, ignorando"` (info) | `whatsapp_service.py:156` |
| **10** | Excepción en `_process_whatsapp_message` | ❌ Procesamiento falla silenciosamente | ❌ `"Error procesando mensaje WhatsApp en background"` (error) | `whatsapp.py:533-539` |
| **11** | `send_whatsapp_message` falla (timeout) | ❌ Respuesta generada pero NO enviada | ⚠️ `"Timeout enviando WhatsApp"` (warning, attempt=X) | `whatsapp_service.py:110-111` |
| **12** | `send_whatsapp_message` falla (error API) | ❌ Respuesta generada pero NO enviada | ⚠️ `"Error enviando WhatsApp"` (warning, status_code, error) | `whatsapp_service.py:98-104` |
| **13** | `send_whatsapp_message` falla (max reintentos) | ❌ Respuesta generada pero NO enviada | ❌ **NO LOG EXPLÍCITO** (solo return False) | `whatsapp_service.py:119` |
| **14** | `WHATSAPP_ENABLED=false` en `send_whatsapp_message` | ❌ Respuesta generada pero NO enviada | ⚠️ `"WhatsApp deshabilitado, mensaje no enviado"` (warning) | `whatsapp_service.py:40-42` |
| **15** | `WHATSAPP_ACCESS_TOKEN` o `PHONE_NUMBER_ID` vacíos | ❌ Respuesta generada pero NO enviada | ❌ `"WhatsApp no configurado correctamente"` (error) | `whatsapp_service.py:44-46` |
| **16** | Outbox dedup bloquea mensaje saliente | ❌ Respuesta generada pero NO enviada | ✅ `"Mensaje WhatsApp bloqueado (outbox dedup)"` (info, decision_path="outgoing_dedup_skip") | `whatsapp_service.py:52-59` |

### P1: Respuesta con Copy Fijo (Siempre Igual)

| # | Condición | Respuesta | Log Esperado (event_name) | Archivo:Línea |
|---|-----------|-----------|---------------------------|---------------|
| **17** | Modo `HUMAN_ACTIVE` (no expirado) | ✅ Mensaje cortés FIJO | ✅ `"reply_sent_in_human_active"` (info) O `"reply_failed_in_human_active"` (error) | `whatsapp.py:363-378` |
| **18** | Mensaje off-topic (no del negocio) | ✅ Mensaje redirect FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `whatsapp.py:390-399` |
| **19** | Intent `saludo` detectado | ✅ Saludo FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `response_service.py:706-707`, `whatsapp.py:556-557` |
| **20** | Mensaje ambiguo (triage primer turno) | ✅ Triage greeting FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `triage_service.py:152-157` |
| **21** | Mensaje ambiguo (triage 2+ turnos) | ✅ Pregunta cerrada FIJA | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `triage_service.py:159-160` |
| **22** | Handoff activado (proyecto negocio) | ✅ Mensaje handoff FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `handoff_service.py:375-385` |
| **23** | Handoff activado (logística) | ✅ Mensaje handoff FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `handoff_service.py:388-392` |
| **24** | Handoff activado (cierre compra) | ✅ Mensaje handoff FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `handoff_service.py:395-405` |
| **25** | Handoff urgente | ✅ Mensaje handoff FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `handoff_service.py:408-412` |
| **26** | Tipo mensaje: `EMPTY_OR_GIBBERISH` | ✅ Saludo FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `business_guardrails.py:199-200` |
| **27** | Tipo mensaje: `NON_BUSINESS` | ✅ Redirect FIJO | ✅ `"Mensaje WhatsApp procesado y respondido"` (info) | `business_guardrails.py:202-203` |

---

## Checklist P0/P1: Puntos de Falla

### P0: Silencio Total (CRÍTICO - LUISA NO RESPONDE)

- [ ] **P0-1**: Verificar que `WHATSAPP_ENABLED=true` en producción
  - **Log esperado**: Si `false`, NO hay log de procesamiento
  - **Ubicación**: `whatsapp.py:87`
  - **Riesgo**: Usuario envía mensaje → LUISA no responde → Usuario piensa que no funciona

- [ ] **P0-2**: Verificar que webhook recibe JSON válido
  - **Log esperado**: `"Webhook recibido sin JSON válido"` (warning)
  - **Ubicación**: `whatsapp.py:92`
  - **Riesgo**: Webhook malformado → LUISA no procesa → Sin respuesta

- [ ] **P0-3**: Verificar que no se procesan solo statuses
  - **Log esperado**: `"Webhook ignorado (solo statuses)"` (info, decision_path="ignore_status_event")
  - **Ubicación**: `whatsapp.py:101-108`
  - **Riesgo**: OK (correcto ignorar statuses)

- [ ] **P0-4**: Verificar deduplicación de mensajes
  - **Log esperado**: `"Mensaje WhatsApp duplicado (dedup)"` (info, decision_path="dedup_skip")
  - **Ubicación**: `whatsapp.py:143-150`
  - **Riesgo**: Mensaje duplicado → LUISA no responde → Usuario confundido

- [ ] **P0-5**: Verificar rate limiting
  - **Log esperado**: `"Rate limit WhatsApp"` (warning)
  - **Ubicación**: `whatsapp.py:170-176`
  - **Riesgo**: Usuario envía muchos mensajes → HTTP 429 → Sin respuesta

- [ ] **P0-6**: Verificar que mensajes no-texto se ignoran
  - **Log esperado**: `"Mensaje no es de texto, ignorando"` (info, type=X)
  - **Ubicación**: `whatsapp_service.py:156`
  - **Riesgo**: Usuario envía imagen/audio → LUISA no responde → Usuario confundido

- [ ] **P0-7**: Verificar excepciones en `_process_whatsapp_message`
  - **Log esperado**: `"Error procesando mensaje WhatsApp en background"` (error, error=str(e))
  - **Ubicación**: `whatsapp.py:533-539`
  - **Riesgo**: Error no manejado → Procesamiento falla → Sin respuesta

- [ ] **P0-8**: Verificar que `send_whatsapp_message` siempre loguea éxito/fallo
  - **Log esperado**: 
    - Éxito: `"Mensaje WhatsApp enviado"` (info, to, message_id)
    - Fallo: `"Error enviando WhatsApp"` (warning) o `"Timeout enviando WhatsApp"` (warning)
  - **Ubicación**: `whatsapp_service.py:89-93, 98-104, 110-111`
  - **Riesgo**: Fallo silencioso → Respuesta generada pero NO enviada → Usuario no recibe respuesta

- [ ] **P0-9**: Verificar configuración de WhatsApp
  - **Log esperado**: `"WhatsApp no configurado correctamente"` (error) si falta token o phone_id
  - **Ubicación**: `whatsapp_service.py:44-46`
  - **Riesgo**: Configuración incompleta → Todos los mensajes fallan → Sin respuestas

- [ ] **P0-10**: Verificar outbox dedup (anti-spam)
  - **Log esperado**: `"Mensaje WhatsApp bloqueado (outbox dedup)"` (info, decision_path="outgoing_dedup_skip")
  - **Ubicación**: `whatsapp_service.py:52-59`
  - **Riesgo**: Mensaje duplicado reciente → No se envía → Usuario no recibe respuesta

### P1: Copy Repetido (Riesgo de Parecer Chatbot)

- [ ] **P1-1**: Verificar que saludo inicial tiene variación
  - **Copy actual**: `"¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"` (FIJO)
  - **Ubicaciones**: 
    - `response_service.py:707`
    - `response_service.py:509`
    - `response_service.py:913`
    - `triage_service.py:155-156`
    - `business_guardrails.py:200`
    - `whatsapp.py:557` (diferente: `"¡Hola! 😊 ¿En qué te puedo ayudar: máquinas, repuestos o servicio técnico?"`)
  - **Riesgo**: Mismo saludo siempre → Parece chatbot

- [ ] **P1-2**: Verificar que mensaje HUMAN_ACTIVE tiene variación
  - **Copy actual**: `"¡Hola! 😊 Un asesor te va a contactar pronto.\n¿Quieres que pase tu nombre y barrio para que todo esté listo?"` (FIJO)
  - **Ubicación**: `whatsapp.py:356-359`
  - **Riesgo**: Mismo mensaje en HUMAN_ACTIVE → Parece chatbot

- [ ] **P1-3**: Verificar que mensajes handoff tienen variación
  - **Copy actual**: 5 variantes fijas según tipo
  - **Ubicaciones**: `handoff_service.py:375-422`
  - **Riesgo**: Mismos mensajes handoff → Parece chatbot

- [ ] **P1-4**: Verificar que triage greeting tiene variación
  - **Copy actual**: 
    - Primer turno: `"¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"` (FIJO)
    - 2+ turnos: `"¿Es por máquinas, repuestos o servicio técnico?"` (FIJO)
  - **Ubicación**: `triage_service.py:152-160`
  - **Riesgo**: Mismo triage siempre → Parece chatbot

- [ ] **P1-5**: Verificar que mensaje off-topic tiene variación
  - **Copy actual**: `"¡Hola! 😊 Te ayudo con máquinas, repuestos y servicio técnico.\n¿Qué necesitas?"` (FIJO)
  - **Ubicación**: `business_guardrails.py:203`
  - **Riesgo**: Mismo redirect siempre → Parece chatbot

---

## Señales de Riesgo: Repetición de Copy

### Riesgo 1: Saludo Inicial Repetido

**Archivos donde se define:**
1. `backend/app/services/response_service.py:707` - Función `build_response()` → Intent saludo
2. `backend/app/services/response_service.py:509` - Función `get_default_response()` → Respuesta genérica
3. `backend/app/services/response_service.py:913` - Función `_generate_fallback_response()` → Fallback
4. `backend/app/services/triage_service.py:155-156` - Función `generate_triage_greeting()` → Primer turno ambiguo
5. `backend/app/rules/business_guardrails.py:200` - Función `get_response_for_message_type()` → EMPTY_OR_GIBBERISH
6. `backend/app/routers/whatsapp.py:557` - Función `_generate_whatsapp_response()` → Saludo (DIFERENTE)

**Copy repetido** (5 de 6 usan el mismo):
```
"¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"
```

**Riesgo**: Usuario que envía varios mensajes ambiguos siempre recibe el mismo saludo.

---

### Riesgo 2: Mensaje HUMAN_ACTIVE Fijo

**Archivo donde se define:**
1. `backend/app/routers/whatsapp.py:356-359` - Función `_process_whatsapp_message()` → Modo HUMAN_ACTIVE

**Copy fijo**:
```
"¡Hola! 😊 Un asesor te va a contactar pronto.\n¿Quieres que pase tu nombre y barrio para que todo esté listo?"
```

**Riesgo**: Usuario que escribe múltiples veces después de handoff siempre recibe el mismo mensaje.

---

### Riesgo 3: Triage Greeting Fijo

**Archivo donde se define:**
1. `backend/app/services/triage_service.py:152-160` - Función `generate_triage_greeting()` → Ambiguo primer turno y 2+ turnos

**Copy fijo**:
- Primer turno: `"¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?"`
- 2+ turnos: `"¿Es por máquinas, repuestos o servicio técnico?"`

**Riesgo**: Usuario que envía múltiples mensajes ambiguos siempre recibe los mismos triage greetings.

---

## Micro-Mejoras para Variar Copy (Máximo 3)

### Mejora 1: Rotación de Saludos Iniciales

**Objetivo**: Variar saludo inicial sin perder control

**Implementación**:
- Crear lista de 3-4 variantes de saludo
- Seleccionar por `hash(conversation_id) % len(variantes)` (determinístico por conversación)
- Aplicar en: `response_service.py:707`, `triage_service.py:155-156`, `business_guardrails.py:200`

**Variantes propuestas**:
```python
SALUDO_VARIANTES = [
    "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?",
    "¡Hola! 😊 Soy Luisa. ¿Te ayudo con máquinas familiares, industriales o repuestos?",
    "¡Hola! 👋 Soy Luisa del Sastre.\n¿Qué necesitas: máquinas, repuestos o servicio técnico?",
    "¡Hola! 😊 Hola, soy Luisa. ¿Buscas máquina familiar, industrial o repuesto?"
]
```

**Archivo**: `backend/app/rules/keywords.py` (agregar constante)
**Función helper**: `get_greeting_for_conversation(conversation_id: str) -> str` en `keywords.py`
**Impacto**: Mismo saludo por conversación, diferente entre conversaciones

---

### Mejora 2: Rotación de Mensaje HUMAN_ACTIVE

**Objetivo**: Variar mensaje en modo HUMAN_ACTIVE sin perder control

**Implementación**:
- Crear lista de 2-3 variantes de mensaje HUMAN_ACTIVE
- Seleccionar por `hash(conversation_id + timestamp) % len(variantes)` (determinístico por mensaje)
- Aplicar en: `whatsapp.py:356-359`

**Variantes propuestas**:
```python
HUMAN_ACTIVE_VARIANTES = [
    "¡Hola! 😊 Un asesor te va a contactar pronto.\n¿Quieres que pase tu nombre y barrio para que todo esté listo?",
    "¡Hola! 👋 Un asesor te contactará pronto.\n¿Te ayudo con tu nombre y ubicación mientras tanto?",
    "¡Hola! 😊 Un asesor te va a contactar.\n¿Prefieres que deje tu nombre y barrio para acelerar?"
]
```

**Archivo**: `backend/app/rules/keywords.py` (agregar constante)
**Función helper**: `get_human_active_message(conversation_id: str, timestamp: str) -> str` en `keywords.py`
**Impacto**: Diferente mensaje por interacción en HUMAN_ACTIVE, más humano

---

### Mejora 3: Rotación de Triage Greeting

**Objetivo**: Variar triage greeting sin perder control

**Implementación**:
- Crear lista de 2-3 variantes por nivel (primer turno, 2+ turnos)
- Seleccionar por `hash(conversation_id) % len(variantes)` (determinístico por conversación)
- Aplicar en: `triage_service.py:152-160`

**Variantes propuestas**:
```python
TRIAGE_FIRST_VARIANTES = [
    "¡Hola! 👋 Soy Luisa del Sastre.\n¿Buscas máquina familiar, industrial o repuesto?",
    "¡Hola! 😊 Soy Luisa. ¿Te ayudo con máquinas familiares, industriales o repuestos?",
    "¡Hola! 👋 Soy Luisa del Sastre.\n¿Qué necesitas: máquinas, repuestos o servicio técnico?"
]

TRIAGE_RETRY_VARIANTES = [
    "¿Es por máquinas, repuestos o servicio técnico?",
    "¿Necesitas máquinas, repuestos o soporte?",
    "¿Es por máquinas, repuestos o ayuda técnica?"
]
```

**Archivo**: `backend/app/services/triage_service.py` (agregar constantes)
**Modificar**: `generate_triage_greeting()` para usar rotación
**Impacto**: Mismo triage por conversación, diferente entre conversaciones

---

## Resumen Ejecutivo

### Puntos Críticos P0 (Silencio Total)

**Total**: 10 puntos críticos donde LUISA podría NO responder

**Más probables en demo**:
1. P0-5: Rate limit (si usuario envía >20 mensajes/min)
2. P0-7: Excepciones no manejadas (si hay bug en código)
3. P0-8: `send_whatsapp_message` falla silenciosamente (timeout, error API)
4. P0-10: Outbox dedup bloquea mensaje (si mismo mensaje en 2min)

### Puntos P1 (Copy Repetido)

**Total**: 5 puntos donde copy puede ser repetitivo

**Más visibles en demo**:
1. P1-1: Saludo inicial (5 de 6 usos tienen mismo copy)
2. P1-2: Mensaje HUMAN_ACTIVE (siempre igual)
3. P1-4: Triage greeting (siempre igual)

### Micro-Mejoras Recomendadas

1. ✅ **Rotación de saludos** (Mejora 1) - Impacto alto, esfuerzo bajo
2. ✅ **Rotación HUMAN_ACTIVE** (Mejora 2) - Impacto medio, esfuerzo bajo
3. ✅ **Rotación triage** (Mejora 3) - Impacto medio, esfuerzo bajo

**Implementación total**: ~50 líneas de código, 0 breaking changes, 100% backward compatible

---

**Última actualización**: 2025-01-05  
**Responsable**: Tech Lead + SRE

