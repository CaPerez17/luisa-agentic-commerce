# Plan de Prueba Manual para WhatsApp Real

**Fecha**: 2025-01-05  
**Objetivo**: Validar todos los flujos críticos escribiendo desde WhatsApp real

---

## Pre-requisitos

- ✅ WhatsApp habilitado y configurado
- ✅ OpenAI habilitado (si se quiere validar objeciones)
- ✅ Acceso a logs del backend (`docker compose logs -f backend`)
- ✅ Número de WhatsApp configurado como contacto

---

## Flujo Completo de Prueba (6 Escenarios)

---

### **Escenario 1: Saludo + Triage**

#### Paso 1.1: Saludo Inicial

**Tú escribes**:
```
Hola
```

**LUISA debe responder** (una de estas 2 variantes):
```
Variante A:
¡Hola! 👋 Soy Luisa del Sastre.
¿Buscas máquina familiar, industrial o repuesto?

Variante B:
¡Hola! 😊 Soy Luisa. ¿Te ayudo con máquinas familiares, industriales o repuestos?
```

**Log esperado**:
```
"message": "Mensaje WhatsApp recibido (queued)",
"message_id": "wamid.xxx",
"phone": "xxxx",
"decision_path": "queued_processing"

"message": "Mensaje WhatsApp procesado y respondido",
"message_id": "wamid.xxx",
"phone": "xxxx",
"intent": "saludo",
"stage": "discovery"
```

**Validar**:
- ✅ LUISA responde en < 2 segundos
- ✅ Mensaje contiene saludo + pregunta cerrada
- ✅ Variante de saludo es determinística (mismo conversation_id = misma variante)

---

#### Paso 1.2: Respuesta Ambigua (Triage)

**Tú escribes**:
```
Info
```
o
```
Buenas
```

**LUISA debe responder** (una de estas 2 variantes):
```
Variante A:
¡Hola! 👋 Soy Luisa del Sastre.
¿Buscas máquina familiar, industrial o repuesto?

Variante B:
¡Hola! 😊 Soy Luisa. ¿Qué necesitas: máquinas, repuestos o servicio técnico?
```

**Log esperado**:
```
"message": "Mensaje WhatsApp procesado y respondido",
"message_id": "wamid.xxx",
"phone": "xxxx",
"intent": "other" (o "saludo"),
"decision_path": "->triage_greeting" (o equivalente)
```

**Validar**:
- ✅ LUISA responde con triage (pregunta cerrada)
- ✅ Variante de triage es determinística

---

### **Escenario 2: Recomendación de Producto (con Contexto)**

#### Paso 2.1: Especificar Tipo de Máquina

**Tú escribes**:
```
Quiero una máquina industrial
```

**LUISA debe responder** (heurística, NO OpenAI):
```
"Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
```
o similar (respuesta determinística según playbook)

**Log esperado**:
```
"message": "Mensaje WhatsApp procesado y respondido",
"message_id": "wamid.xxx",
"phone": "xxxx",
"intent": "buscar_maquina_industrial",
"stage": "discovery",
"openai_called": false (o no aparece el campo)
```

**Validar**:
- ✅ LUISA pregunta por uso específico (ropa/gorras/calzado)
- ✅ NO usa OpenAI (heurística pura)
- ✅ Respuesta determinística

---

#### Paso 2.2: Especificar Uso

**Tú escribes**:
```
Para gorras
```

**LUISA debe responder** (heurística o OpenAI COPY):
```
"Para gorras necesitas una recta industrial que maneje telas gruesas. 
Tenemos KINGTER KT-D3 en promoción a $1.230.000. 
¿Producción constante o pocas unidades?"
```
o similar (puede usar OpenAI COPY si hay contexto completo)

**Log esperado** (si usa OpenAI):
```
"message": "openai_decision_made",
"intent": "buscar_maquina_industrial",
"task_type": "copy",
"reason_for_llm_use": "copy:buscar_maquina_industrial:BUSINESS_CONSULT",
"gating_passed": true

"message": "LLM Adapter usado exitosamente",
"task_type": "copy",
"reason_for_llm_use": "copy:buscar_maquina_industrial:BUSINESS_CONSULT"
```

**Log esperado** (si NO usa OpenAI):
```
"message": "Mensaje WhatsApp procesado y respondido",
"intent": "buscar_maquina_industrial",
"openai_called": false (o no aparece)
```

**Validar**:
- ✅ LUISA menciona producto específico (KINGTER KT-D3)
- ✅ Menciona precio ($1.230.000)
- ✅ Termina con pregunta cerrada
- ✅ Si usa OpenAI, aparece `openai_decision_made` y `LLM Adapter usado exitosamente`

---

### **Escenario 3: Objeción de Precio**

#### Paso 3.1: Objeción Explícita

**Tú escribes**:
```
Está muy caro, no tengo ese presupuesto
```

**LUISA debe responder** (DEBE usar OpenAI OBJECION):
```
"Entiendo tu preocupación por el precio. Tenemos opciones desde $400.000 
para uso familiar. También ofrecemos financiamiento con Addi y Sistecrédito. 
¿Te interesa ver opciones de financiamiento o prefieres una máquina usada?"
```
o similar (respuesta empática + alternativas reales)

**Log esperado**:
```
"message": "openai_decision_made",
"intent": "buscar_maquina_industrial" (o similar),
"task_type": "objecion",
"reason_for_llm_use": "objecion:buscar_maquina_industrial:BUSINESS_CONSULT",
"gating_passed": true

"message": "LLM Adapter usado exitosamente",
"task_type": "objecion",
"reason_for_llm_use": "objecion:buscar_maquina_industrial:BUSINESS_CONSULT",
"openai_call_count": 1 (o 2, 3, etc.)
```

**Validar**:
- ✅ LUISA reconoce la objeción con empatía
- ✅ Menciona alternativas reales (financiamiento, opciones más económicas)
- ✅ NO inventa precios o productos
- ✅ Logs muestran `task_type=objecion` y `openai_called=true`

---

#### Paso 3.2: Segunda Objeción (Validar Variación)

**Tú escribes**:
```
Solo estoy averiguando, todavía no sé
```

**LUISA debe responder** (DEBE usar OpenAI OBJECION nuevamente):
```
"Claro, es normal averiguar antes de decidir. ¿Quieres que te ayude a 
comparar opciones según tu necesidad? O si prefieres, un asesor puede 
acompañarte sin compromiso."
```
o similar (empático, sin presionar)

**Log esperado**:
```
"message": "openai_decision_made",
"task_type": "objecion",
"openai_call_count": 2 (incrementado)
```

**Validar**:
- ✅ LUISA no presiona
- ✅ Ofrece ayuda sin compromiso
- ✅ `openai_call_count` incrementado correctamente

---

### **Escenario 4: Caso Técnico (Ruido, Hilo se Rompe)**

#### Paso 4.1: Problema Técnico

**Tú escribes**:
```
Mi máquina hace mucho ruido y el hilo se rompe
```

**LUISA debe responder** (heurística o handoff según prioridad):
```
"Cómo 1: Si detecta URGENTE → Handoff a técnico:
'Esto requiere atención inmediata. Te conecto con nuestro equipo.
¿Te llamamos ahora mismo?'

Cómo 2: Si NO es urgente → Respuesta heurística:
'Para ruido y hilo que se rompe, puede ser tensión de hilo, aguja desalineada 
o motor. ¿Hace cuánto tiempo empezó el problema?'
```

**Log esperado** (si es handoff):
```
"message": "human_active_triggered",
"reason": "Cliente requiere atención inmediata" (o similar),
"priority": "urgent",
"team": "tecnica"

"message": "Handoff procesado",
"conversation_id": "wa_xxx",
"team": "tecnica",
"priority": "urgent"

"message": "Mensaje WhatsApp procesado y respondido",
"intent": "soporte_tecnico"
```

**Log esperado** (si NO es handoff):
```
"message": "Mensaje WhatsApp procesado y respondido",
"intent": "soporte_tecnico",
"stage": "support"
```

**Validar**:
- ✅ Si es urgente → Handoff activado + log `human_active_triggered`
- ✅ Si NO es urgente → Respuesta heurística con diagnóstico básico
- ✅ Respuesta siempre termina con pregunta cerrada

---

#### Paso 4.2: Seguimiento del Caso Técnico

**Tú escribes** (si NO hubo handoff):
```
Hace una semana
```

**LUISA debe responder**:
```
"Una semana es tiempo suficiente para revisar. Te recomiendo:
1. Revisar tensión del hilo
2. Verificar que la aguja esté bien instalada
3. Limpiar la máquina

Si persiste, podemos agendar una revisión con nuestro técnico. 
¿Prefieres que te llamemos para agendar cita o pasas por el almacén?"
```
o similar (diagnóstico + ofrecimiento de servicio)

**Log esperado**:
```
"message": "Mensaje WhatsApp procesado y respondido",
"intent": "soporte_tecnico",
"stage": "support"
```

**Validar**:
- ✅ LUISA da diagnóstico básico
- ✅ Ofrece servicio técnico
- ✅ Pregunta cerrada al final

---

### **Escenario 5: Handoff (Cita/Asesor) y que NO se Quede Muda**

#### Paso 5.1: Trigger de Handoff

**Tú escribes**:
```
Quiero montar un taller de confección, qué necesito?
```

**LUISA debe responder** (handoff activado):
```
"Para tu proyecto, lo mejor es que un asesor te acompañe personalmente.
¿Te llamamos para agendar cita o prefieres que vayamos a tu taller?"
```
o similar (variante según si está en Montería o fuera)

**Log esperado**:
```
"message": "human_active_triggered",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"reason": "Cliente requiere asesoría para proyecto de negocio",
"priority": "high",
"team": "comercial",
"user_text": "Quiero montar un taller...",
"trigger_keywords": ["montar", "emprendimiento"] (o similar)

"message": "Handoff procesado",
"conversation_id": "wa_xxx",
"team": "comercial",
"priority": "high"

"message": "Mensaje WhatsApp procesado y respondido",
"intent": "buscar_maquina_industrial" (o similar)
```

**Validar**:
- ✅ LUISA propone asesor (handoff activado)
- ✅ Log `human_active_triggered` con contexto completo
- ✅ Log `Handoff procesado` con team y priority
- ✅ Respuesta contiene pregunta cerrada (te llamamos o vayamos)

---

#### Paso 5.2: Usuario Responde "Sí" o Similar

**Tú escribes**:
```
Sí, llámenme
```

**LUISA debe responder** (FIX P0 - nunca quedarse muda):
```
Variante A:
¡Hola! 😊 Un asesor te va a contactar pronto.
¿Quieres que pase tu nombre y barrio para que todo esté listo?

Variante B:
¡Hola! 👋 Un asesor te contactará pronto.
¿Te ayudo con tu nombre y ubicación mientras tanto?
```

**Log esperado**:
```
"message": "Mensaje registrado en modo HUMAN_ACTIVE",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx"

"message": "reply_sent_in_human_active",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx"
```

**Validar**:
- ✅ LUISA **NUNCA** se queda muda (respuesta siempre presente)
- ✅ Mensaje es cortés y pide datos útiles (nombre, barrio)
- ✅ Log `reply_sent_in_human_active` confirma respuesta enviada
- ✅ Variante es determinística (mismo conversation_id = misma variante)

---

#### Paso 5.3: Usuario Escribe Otra Vez en HUMAN_ACTIVE

**Tú escribes** (minutos después):
```
Hola
```

**LUISA debe responder** (FIX P0 - siempre responde):
```
Variante A:
¡Hola! 😊 Un asesor te va a contactar pronto.
¿Quieres que pase tu nombre y barrio para que todo esté listo?

Variante B:
¡Hola! 👋 Un asesor te contactará pronto.
¿Te ayudo con tu nombre y ubicación mientras tanto?
```

**Log esperado**:
```
"message": "Mensaje registrado en modo HUMAN_ACTIVE",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx"

"message": "reply_sent_in_human_active",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx"
```

**Validar**:
- ✅ LUISA responde (nunca silencio)
- ✅ Mismo mensaje (variante determinística)
- ✅ Log `reply_sent_in_human_active` presente

---

#### Paso 5.4: Usuario Insiste con Pregunta Específica

**Tú escribes**:
```
Cuánto cuesta la KINGTER?
```

**LUISA debe responder** (FIX P0 - siempre responde):
```
Variante A:
¡Hola! 😊 Un asesor te va a contactar pronto.
¿Quieres que pase tu nombre y barrio para que todo esté listo?

Variante B:
¡Hola! 👋 Un asesor te contactará pronto.
¿Te ayudo con tu nombre y ubicación mientras tanto?
```

**Log esperado**:
```
"message": "Mensaje registrado en modo HUMAN_ACTIVE",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx"

"message": "reply_sent_in_human_active",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx"
```

**Validar**:
- ✅ LUISA responde (nunca ignora la pregunta)
- ✅ Respuesta cortés pero no técnica (modo HUMAN_ACTIVE)
- ✅ Log `reply_sent_in_human_active` presente

---

### **Escenario 6: TTL de HUMAN_ACTIVE (Simular Expiración)**

#### Opción A: Ajuste Temporal en Base de Datos (RECOMENDADO para Demo)

**Pre-requisito**: Conversación en modo `HUMAN_ACTIVE` (del Escenario 5)

**Paso 6.1: Modificar `mode_updated_at` en DB**

**Tú ejecutas** (en terminal, NO es escribir en WhatsApp):
```bash
# Conectar a la base de datos
docker exec -it luisa-backend sqlite3 /app/data/luisa.db

# Ver conversación actual
SELECT conversation_id, conversation_mode, mode_updated_at FROM conversations WHERE conversation_mode = 'HUMAN_ACTIVE';

# Modificar mode_updated_at a hace 13 horas (más que HUMAN_TTL_HOURS=12)
UPDATE conversations 
SET mode_updated_at = datetime('now', '-13 hours') 
WHERE conversation_id = 'wa_xxxxxxxxxxxxx';

# Verificar cambio
SELECT conversation_id, conversation_mode, mode_updated_at FROM conversations WHERE conversation_mode = 'HUMAN_ACTIVE';
```

**Nota**: Reemplaza `wa_xxxxxxxxxxxxx` con tu `conversation_id` real (obtener del log del Escenario 5).

---

#### Paso 6.2: Escribir Mensaje Después del TTL

**Tú escribes** (después de modificar DB):
```
Hola, sigo interesado
```

**LUISA debe responder** (modo AI_ACTIVE, NO HUMAN_ACTIVE):
```
"¡Hola! 😊 ¿En qué te puedo ayudar: máquinas, repuestos o servicio técnico?"
```
o similar (respuesta normal de AI, NO mensaje de HUMAN_ACTIVE)

**Log esperado**:
```
"message": "mode_auto_reverted_to_ai",
"conversation_id": "wa_xxx",
"seconds_in_human_active": 46800 (o similar, > 12 horas en segundos),
"ttl_hours": 12

"message": "Mensaje WhatsApp procesado y respondido",
"intent": "saludo" (o similar),
"stage": "discovery"
```

**Validar**:
- ✅ LUISA responde con flujo normal de AI (NO mensaje de HUMAN_ACTIVE)
- ✅ Log `mode_auto_reverted_to_ai` presente
- ✅ `seconds_in_human_active` > `ttl_hours * 3600` (43,200 segundos)
- ✅ No aparece `reply_sent_in_human_active` (ya no está en HUMAN_ACTIVE)

---

#### Opción B: Validar TTL Sin Esperar (Solo Observación)

**Alternativa** (si no puedes modificar DB directamente):

**Paso 6.1: Verificar `mode_updated_at` Actual**

**Tú ejecutas** (en terminal):
```bash
# Ver timestamp actual de HUMAN_ACTIVE
docker exec luisa-backend sqlite3 /app/data/luisa.db \
  "SELECT conversation_id, conversation_mode, mode_updated_at, 
   datetime('now') as now_utc,
   CAST((julianday('now') - julianday(mode_updated_at)) * 24 AS INTEGER) as hours_elapsed
   FROM conversations 
   WHERE conversation_mode = 'HUMAN_ACTIVE';"
```

**Resultado esperado**:
```
conversation_id|mode|mode_updated_at|now_utc|hours_elapsed
wa_xxx|HUMAN_ACTIVE|2025-01-05 10:00:00|2025-01-05 15:30:00|5
```

**Validar**:
- ✅ `mode_updated_at` existe y tiene timestamp
- ✅ `hours_elapsed` < 12 (aún NO expirado)

---

#### Paso 6.2: Calcular Cuándo Expirará

**Tú calculas**:
```
Si mode_updated_at = 2025-01-05 10:00:00
y HUMAN_TTL_HOURS = 12
Entonces expirará = 2025-01-05 22:00:00 (10:00 + 12 horas)
```

**Validar**:
- ✅ Puedes verificar que el TTL está configurado correctamente
- ✅ Sabes cuándo expirará sin esperar

---

#### Paso 6.3: Escribir Mensaje ANTES del TTL

**Tú escribes** (antes de las 22:00 si expiró a las 22:00):
```
Sigo esperando el llamado
```

**LUISA debe responder** (modo HUMAN_ACTIVE, NO expirado):
```
Variante A:
¡Hola! 😊 Un asesor te va a contactar pronto.
¿Quieres que pase tu nombre y barrio para que todo esté listo?
```

**Log esperado**:
```
"message": "Mensaje registrado en modo HUMAN_ACTIVE",
"conversation_id": "wa_xxx"

"message": "reply_sent_in_human_active",
"conversation_id": "wa_xxx"
```

**Validar**:
- ✅ LUISA responde con mensaje de HUMAN_ACTIVE (no expirado)
- ✅ NO aparece `mode_auto_reverted_to_ai`

---

## Resumen de Logs por Escenario

### Escenario 1: Saludo + Triage
- `"Mensaje WhatsApp recibido (queued)"`
- `"Mensaje WhatsApp procesado y respondido"` con `intent="saludo"`

### Escenario 2: Recomendación de Producto
- `"Mensaje WhatsApp procesado y respondido"` con `intent="buscar_maquina_industrial"`
- Opcional: `"openai_decision_made"` con `task_type="copy"` (si usa OpenAI)

### Escenario 3: Objeción de Precio
- `"openai_decision_made"` con `task_type="objecion"`
- `"LLM Adapter usado exitosamente"` con `task_type="objecion"`
- `"Mensaje WhatsApp procesado y respondido"`

### Escenario 4: Caso Técnico
- `"Mensaje WhatsApp procesado y respondido"` con `intent="soporte_tecnico"`
- Opcional: `"human_active_triggered"` con `priority="urgent"` (si es urgente)

### Escenario 5: Handoff + No Silencio
- `"human_active_triggered"` (Paso 5.1)
- `"Handoff procesado"` (Paso 5.1)
- `"reply_sent_in_human_active"` (Pasos 5.2, 5.3, 5.4)

### Escenario 6: TTL HUMAN_ACTIVE
- `"mode_auto_reverted_to_ai"` (Paso 6.2, Opción A)
- `"Mensaje WhatsApp procesado y respondido"` con respuesta normal (NO HUMAN_ACTIVE)

---

## Checklist Final de Validación

### Funcionalidad
- [ ] Escenario 1: Saludo + triage funciona correctamente
- [ ] Escenario 2: Recomendación de producto incluye contexto relevante
- [ ] Escenario 3: Objeción usa OpenAI y genera respuesta empática
- [ ] Escenario 4: Caso técnico activa handoff si es urgente
- [ ] Escenario 5: Handoff activado y LUISA nunca se queda muda (3 veces mínimo)
- [ ] Escenario 6: TTL funciona (modo revierte a AI_ACTIVE después de 12h)

### Observabilidad
- [ ] Todos los logs esperados aparecen en orden correcto
- [ ] `openai_decision_made` aparece solo en casos complejos (objeciones, consultas)
- [ ] `human_active_triggered` aparece cuando se activa handoff
- [ ] `reply_sent_in_human_active` aparece cada vez que LUISA responde en HUMAN_ACTIVE
- [ ] `mode_auto_reverted_to_ai` aparece cuando TTL expira

### Variaciones de Copy
- [ ] Saludo inicial tiene variación (diferentes conversaciones = diferentes variantes)
- [ ] Triage greeting tiene variación (mismo conversation_id = misma variante)
- [ ] HUMAN_ACTIVE follow-up tiene variación (mismo conversation_id = misma variante)
- [ ] Handoff "te llamamos o pasas" tiene variación (mismo conversation_id = misma variante)

### Performance
- [ ] Todas las respuestas llegan en < 2 segundos
- [ ] OpenAI (si se usa) responde en < 5 segundos (timeout)

---

## Comandos de Monitoreo (Opcionales)

### Ver todos los logs en tiempo real
```bash
docker compose logs -f backend | grep -E "Mensaje WhatsApp|openai_decision_made|human_active|mode_auto_reverted"
```

### Ver logs de una conversación específica
```bash
docker compose logs backend | grep "conversation_id=wa_xxxxxxxxxxxxx"
```

### Ver solo logs de OpenAI
```bash
docker compose logs backend | grep -E "openai_decision_made|LLM Adapter"
```

### Ver solo logs de handoff
```bash
docker compose logs backend | grep -E "human_active_triggered|Handoff procesado|reply_sent_in_human_active"
```

---

**Última actualización**: 2025-01-05  
**Estado**: ✅ Listo para ejecución manual en WhatsApp real

