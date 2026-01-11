# Activación de OpenAI para Pruebas Reales en Producción

**Fecha**: 2025-01-05  
**Objetivo**: Activar OpenAI de forma controlada para pruebas reales en WhatsApp

---

## 1. Estado Actual de Configuración

### A) Configuración de OpenAI

**Ubicación**: `backend/app/config.py:35-52`

**Variables existentes**:
- ✅ `OPENAI_ENABLED` (línea 38): `os.getenv("OPENAI_ENABLED", "false").lower() == "true"`
- ✅ `OPENAI_API_KEY` (línea 39): `os.getenv("OPENAI_API_KEY", "")`
- ✅ `OPENAI_MAX_CALLS_PER_CONVERSATION` (línea 46): `int(os.getenv("OPENAI_MAX_CALLS_PER_CONVERSATION", "4"))`
- ✅ `OPENAI_CONVERSATION_TTL_HOURS` (línea 47): `int(os.getenv("OPENAI_CONVERSATION_TTL_HOURS", "24"))`
- ✅ `OPENAI_MAX_OUTPUT_TOKENS` (línea 41): `int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "180"))`
- ✅ `OPENAI_TEMPERATURE` (línea 43): `float(os.getenv("OPENAI_TEMPERATURE", "0.4"))`

**Límites implementados**:
- ✅ Contador por conversación: `backend/app/models/database.py:362-412` (funciones `get_openai_call_count`, `increment_openai_call_count`, `reset_openai_call_count_if_expired`)
- ✅ Verificación de límites: `backend/app/services/llm_adapter.py:461-475` (verifica antes de llamar)
- ✅ Timeout duro: `backend/app/services/llm_adapter.py:32` (`LLM_ADAPTER_TIMEOUT_SECONDS = 5.0`)
- ✅ Fallback garantizado: `backend/app/services/llm_adapter.py:568-618` (siempre retorna fallback si falla)

**Estado**: ✅ **Límites ya implementados, no requiere cambios**

---

### B) Docker Compose

**Ubicación**: `docker-compose.yml:13-14`

**Configuración actual**:
```yaml
env_file:
  - .env
```

**Estado**: ✅ **Docker Compose lee `.env` del directorio raíz**

**Nota**: El archivo `.env` debe estar en `/Users/camilope/AI-Agents/Sastre/.env` (raíz del proyecto, mismo nivel que `docker-compose.yml`)

---

### C) Logging Actual

**Logs existentes**:

1. **Mensaje entrante**:
   - ✅ `"Mensaje WhatsApp recibido (queued)"` (`whatsapp.py:190-198`)
   - ✅ `"Mensaje WhatsApp procesado y respondido"` (`whatsapp.py:522-528`)
   - ⚠️ `logger.interaction()` (`trace_service.py:113-129`) pero falta `message_id`, `phone` (last4), `mode` real

2. **Envío WhatsApp**:
   - ✅ `"Mensaje WhatsApp enviado"` (`whatsapp_service.py:89-93`)
   - ✅ `"Error enviando WhatsApp"` (`whatsapp_service.py:98-104`) con error sanitizado

3. **OpenAI**:
   - ✅ `"LLM Adapter usado exitosamente"` (`response_service.py:779-788`) con `task_type`, `reason_for_llm_use`
   - ⚠️ Falta log cuando se **DECIDE** usar OpenAI (antes de llamarlo)

**Logs faltantes** (máximo 2):

1. **`message_received`**: Log al inicio de procesamiento con todos los campos requeridos
2. **`llm_decision_made`**: Log cuando se decide usar OpenAI (antes de llamarlo)

---

## 2. Cambios Necesarios

### Cambio 1: Agregar Log `message_received`

**Ubicación**: `backend/app/routers/whatsapp.py:381` (después de `with trace_interaction`)

**Diff**:
```diff
--- a/backend/app/routers/whatsapp.py
+++ b/backend/app/routers/whatsapp.py
@@ -380,6 +380,20 @@ async def _process_whatsapp_message(
         # Procesar mensaje con trazabilidad
         with trace_interaction(conversation_id, "whatsapp", phone_from) as tracer:
             tracer.raw_text = text
             tracer.normalized_text = text.lower().strip()
+            
+            # Log de mensaje entrante con todos los campos requeridos
+            logger.info(
+                "message_received",
+                conversation_id=conversation_id,
+                message_id=message_id[:20] if message_id else "unknown",
+                phone=phone_from[-4:] if phone_from and len(phone_from) >= 4 else "unknown",
+                mode=mode,
+                text_preview=text[:50] if text else ""  # Solo primeros 50 caracteres
+            )
             
             # Verificar si es del negocio
```

---

### Cambio 2: Agregar Log `llm_decision_made`

**Ubicación**: `backend/app/services/response_service.py:722` (después de `if can_call_openai:`)

**Diff**:
```diff
--- a/backend/app/services/response_service.py
+++ b/backend/app/services/response_service.py
@@ -722,6 +722,20 @@ def build_response(
                     if can_call_openai:
                         # Determinar tipo de tarea para LLM Adapter
                         task_type = _determine_llm_task_type(
                             text=text,
                             intent=tracer.intent,
                             context=context,
                             message_type=message_type
                         )
+                        
+                        # Log cuando se decide usar OpenAI (antes de llamarlo)
+                        logger.info(
+                            "llm_decision_made",
+                            conversation_id=conversation_id,
+                            intent=tracer.intent,
+                            task_type=task_type,
+                            reason_for_llm_use=f"{task_type}:{tracer.intent}:{message_type.value}",
+                            gating_passed=True,
+                            gating_reason="business_consult_and_no_deterministic"
                         )
                         
                         # Preparar contexto estructurado para el adapter
```

**Nota**: Este log se genera ANTES de llamar OpenAI, permitiendo diagnosticar por qué se decidió usarlo.

---

### Cambio 3: Mejorar Log `Mensaje WhatsApp procesado y respondido`

**Ubicación**: `backend/app/routers/whatsapp.py:522-528`

**Diff**:
```diff
--- a/backend/app/routers/whatsapp.py
+++ b/backend/app/routers/whatsapp.py
@@ -522,7 +522,10 @@ async def _process_whatsapp_message(
                 logger.info(
                     "Mensaje WhatsApp procesado y respondido",
                     message_id=message_id[:20] if message_id else "unknown",
                     phone=phone_from[-4:],
                     intent=tracer.intent,
-                    stage=current_stage
+                    stage=current_stage,
+                    openai_used=tracer.openai_called,
+                    task_type=adapter_metadata.get("task_type") if 'adapter_metadata' in locals() else None,
+                    decision_path=tracer.decision_path
                 )
```

**Nota**: `adapter_metadata` solo existe si se llamó al adapter. Usar `locals().get('adapter_metadata')` de forma segura.

---

### Cambio 4: Archivo `.env` (Crear o Modificar)

**Ubicación**: `Sastre/.env` (raíz del proyecto)

**Contenido requerido**:
```bash
# ============================================================================
# OPENAI CONFIGURATION - PRODUCCIÓN
# ============================================================================
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=150
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_CALLS_PER_CONVERSATION=4
OPENAI_CONVERSATION_TTL_HOURS=24

# ============================================================================
# WHATSAPP CONFIGURATION (ya debe existir)
# ============================================================================
WHATSAPP_ENABLED=true
WHATSAPP_VERIFY_TOKEN=tu-verify-token-aqui
WHATSAPP_ACCESS_TOKEN=tu-access-token-aqui
WHATSAPP_PHONE_NUMBER_ID=tu-phone-number-id-aqui

# ============================================================================
# OTROS (ya deben existir)
# ============================================================================
PRODUCTION_MODE=true
LOG_FORMAT=json
LOG_LEVEL=INFO
```

**Diff** (si el archivo ya existe):
```diff
--- a/.env
+++ b/.env
@@ -1,3 +1,12 @@
+# ============================================================================
+# OPENAI CONFIGURATION
+# ============================================================================
+OPENAI_ENABLED=true
+OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
+OPENAI_MODEL=gpt-4o-mini
+OPENAI_MAX_OUTPUT_TOKENS=150
+OPENAI_TEMPERATURE=0.3
+OPENAI_MAX_CALLS_PER_CONVERSATION=4
+OPENAI_CONVERSATION_TTL_HOURS=24
+
 # ... resto de configuración existente ...
```

---

### Cambio 5: Docker Compose (No requiere cambios)

**Estado**: ✅ `docker-compose.yml` ya está configurado para leer `.env` (línea 14)

**Verificación**: El contenedor `backend` tiene `env_file: - .env`, por lo que todas las variables de `.env` estarán disponibles en el contenedor.

---

## 3. Comandos para Aplicar en VPS

### Paso 1: Verificar que `.env` existe y tiene las variables

```bash
cd /ruta/a/Sastre
cat .env | grep -E "OPENAI_ENABLED|OPENAI_API_KEY|OPENAI_MAX_CALLS" | head -5
```

**Salida esperada**:
```
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-xxx...
OPENAI_MAX_CALLS_PER_CONVERSATION=4
```

---

### Paso 2: Aplicar cambios de código (si no están en repo)

```bash
cd /ruta/a/Sastre
# Hacer pull de cambios o aplicar diffs manualmente
git pull origin main  # Si los cambios están en repo
# O aplicar diffs manualmente según sección 2
```

---

### Paso 3: Reconstruir y reiniciar contenedores

```bash
cd /ruta/a/Sastre
docker compose down
docker compose build backend
docker compose up -d
```

---

### Paso 4: Verificar que las variables están en el contenedor

```bash
docker exec luisa-backend python3 -c "from app.config import OPENAI_ENABLED, OPENAI_MAX_CALLS_PER_CONVERSATION; print(f'OPENAI_ENABLED={OPENAI_ENABLED}, MAX_CALLS={OPENAI_MAX_CALLS_PER_CONVERSATION}')"
```

**Salida esperada**:
```
OPENAI_ENABLED=True, MAX_CALLS=4
```

---

### Paso 5: Verificar logs de inicio

```bash
docker compose logs backend | grep -E "OPENAI|Error|Warning" | tail -20
```

**Validar**:
- ✅ No hay errores de `OPENAI_API_KEY` faltante
- ✅ No hay warnings de configuración

---

### Paso 6: Probar health check

```bash
curl -s https://luisa-agent.online/health | jq .
```

**Salida esperada**:
```json
{
  "status": "ok",
  "service": "luisa"
}
```

---

## 4. Plan de Pruebas Manuales (8 Mensajes)

### Mensaje 1: Saludo

**Tú escribes**:
```
Hola
```

**LUISA debe responder**:
```
¡Hola! 👋 Soy Luisa del Sastre.
¿Buscas máquina familiar, industrial o repuesto?
```
o variante B (determinística por conversation_id)

**Logs esperados**:
```
"message": "Mensaje WhatsApp recibido (queued)",
"message_id": "wamid.xxx",
"phone": "xxxx"

"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "AI_ACTIVE",
"text_preview": "Hola"

"message": "Mensaje WhatsApp procesado y respondido",
"message_id": "wamid.xxx",
"phone": "xxxx",
"intent": "saludo",
"stage": "discovery",
"openai_used": false,
"task_type": null,
"decision_path": "->saludo_handled"
```

**Validar**:
- ✅ Respuesta en < 2 segundos
- ✅ `openai_used=false` (saludo NO usa OpenAI)
- ✅ `intent="saludo"`

---

### Mensaje 2: Intención Clara (Máquina Industrial)

**Tú escribes**:
```
Quiero una máquina industrial para gorras
```

**LUISA debe responder**:
```
"Para gorras necesitas una recta industrial que maneje telas gruesas. 
Tenemos KINGTER KT-D3 en promoción a $1.230.000. 
¿Producción constante o pocas unidades?"
```
o similar (heurística o OpenAI COPY si hay contexto completo)

**Logs esperados**:
```
"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "AI_ACTIVE",
"text_preview": "Quiero una máquina industrial para gorras"

"message": "Mensaje WhatsApp procesado y respondido",
"message_id": "wamid.xxx",
"phone": "xxxx",
"intent": "buscar_maquina_industrial",
"stage": "discovery",
"openai_used": false (o true si usa COPY),
"task_type": null (o "copy" si openai_used=true),
"decision_path": "->discovery_industrial" (o similar)
```

**Validar**:
- ✅ Respuesta menciona producto específico (KINGTER KT-D3)
- ✅ Menciona precio ($1.230.000)
- ✅ `intent="buscar_maquina_industrial"`
- ✅ `openai_used` puede ser `true` o `false` (depende de gating)

---

### Mensaje 3: Objeción de Precio (DEBE usar OpenAI)

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
o similar (empático, alternativas reales)

**Logs esperados**:
```
"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "AI_ACTIVE",
"text_preview": "Está muy caro, no tengo ese presupuesto"

"message": "llm_decision_made",
"conversation_id": "wa_xxx",
"intent": "buscar_maquina_industrial" (o similar),
"task_type": "objecion",
"reason_for_llm_use": "objecion:buscar_maquina_industrial:BUSINESS_CONSULT",
"gating_passed": true,
"gating_reason": "business_consult_and_no_deterministic"

"message": "LLM Adapter usado exitosamente",
"conversation_id": "wa_xxx",
"task_type": "objecion",
"reason_for_llm_use": "objecion:buscar_maquina_industrial:BUSINESS_CONSULT",
"openai_call_count": 1,
"tokens_used": 85 (o similar),
"latency_ms": 1200 (o similar, < 5000)

"message": "Mensaje WhatsApp procesado y respondido",
"message_id": "wamid.xxx",
"phone": "xxxx",
"intent": "buscar_maquina_industrial",
"openai_used": true,
"task_type": "objecion",
"decision_path": "->openai_called_fallback"
```

**Validar**:
- ✅ `llm_decision_made` aparece ANTES de `LLM Adapter usado exitosamente`
- ✅ `task_type="objecion"`
- ✅ `openai_used=true`
- ✅ `openai_call_count=1` (primera llamada)
- ✅ `tokens_used` presente y < 200
- ✅ `latency_ms` < 5000

---

### Mensaje 4: Pregunta Ambigua (DEBE usar OpenAI o Classifier)

**Tú escribes**:
```
No sé qué máquina me conviene
```

**LUISA debe responder** (DEBE usar OpenAI CONSULTA_COMPLEJA):
```
"Para ayudarte a elegir, necesito saber: ¿vas a producir de forma constante 
o es para uso ocasional? También, ¿qué vas a fabricar: ropa, gorras, 
calzado o accesorios?"
```
o similar (estructurado, pregunta cerrada)

**Logs esperados**:
```
"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "AI_ACTIVE",
"text_preview": "No sé qué máquina me conviene"

"message": "llm_decision_made",
"conversation_id": "wa_xxx",
"intent": "other" (o similar),
"task_type": "consulta_compleja",
"reason_for_llm_use": "consulta_compleja:other:BUSINESS_CONSULT",
"gating_passed": true,
"gating_reason": "business_consult_and_no_deterministic"

"message": "LLM Adapter usado exitosamente",
"task_type": "consulta_compleja",
"openai_call_count": 2,
"tokens_used": 95 (o similar)

"message": "Mensaje WhatsApp procesado y respondido",
"openai_used": true,
"task_type": "consulta_compleja"
```

**Validar**:
- ✅ `task_type="consulta_compleja"`
- ✅ `openai_call_count=2` (incrementado)
- ✅ Respuesta estructurada con preguntas cerradas

---

### Mensaje 5: Caso Técnico (Ruido, Hilo se Rompe)

**Tú escribes**:
```
Mi máquina hace mucho ruido y el hilo se rompe constantemente
```

**LUISA debe responder**:
```
Opción A (si detecta URGENTE → Handoff):
"Esto requiere atención inmediata. Te conecto con nuestro equipo.
¿Te llamamos ahora mismo?"

Opción B (si NO es urgente → Respuesta heurística):
"Para ruido y hilo que se rompe, puede ser tensión de hilo, aguja desalineada 
o motor. ¿Hace cuánto tiempo empezó el problema?"
```

**Logs esperados** (si es handoff):
```
"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "AI_ACTIVE",
"text_preview": "Mi máquina hace mucho ruido y el hilo se rompe"

"message": "human_active_triggered",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"reason": "Cliente requiere atención inmediata",
"priority": "urgent",
"team": "tecnica",
"user_text": "Mi máquina hace mucho ruido...",
"trigger_keywords": ["ruido", "rompe"] (o similar)

"message": "Handoff procesado",
"conversation_id": "wa_xxx",
"team": "tecnica",
"priority": "urgent"

"message": "Mensaje WhatsApp procesado y respondido",
"intent": "soporte_tecnico",
"openai_used": false
```

**Logs esperados** (si NO es handoff):
```
"message": "Mensaje WhatsApp procesado y respondido",
"intent": "soporte_tecnico",
"stage": "support",
"openai_used": false
```

**Validar**:
- ✅ Si es urgente → `human_active_triggered` presente
- ✅ `team="tecnica"` si es handoff
- ✅ Respuesta siempre presente (nunca silencio)

---

### Mensaje 6: Handoff "Sí"

**Tú escribes** (después de mensaje que activó handoff):
```
Sí, llámenme
```

**LUISA debe responder** (FIX P0 - nunca silencio):
```
Variante A:
¡Hola! 😊 Un asesor te va a contactar pronto.
¿Quieres que pase tu nombre y barrio para que todo esté listo?

Variante B:
¡Hola! 👋 Un asesor te contactará pronto.
¿Te ayudo con tu nombre y ubicación mientras tanto?
```

**Logs esperados**:
```
"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "HUMAN_ACTIVE",
"text_preview": "Sí, llámenme"

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
- ✅ `mode="HUMAN_ACTIVE"` en `message_received`
- ✅ `reply_sent_in_human_active` presente
- ✅ Variante determinística (mismo conversation_id = misma variante)

---

### Mensaje 7: Follow-up "Hola" Después de Handoff

**Tú escribes** (minutos después del mensaje 6):
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

**Logs esperados**:
```
"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "HUMAN_ACTIVE",
"text_preview": "Hola"

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
- ✅ Mismo mensaje que mensaje 6 (variante determinística)
- ✅ `reply_sent_in_human_active` presente

---

### Mensaje 8: Prueba de Fallback (Validar que Fallback Funciona)

**Opción A: Simular Límite Excedido**

**Pre-requisito**: Usar 4 llamadas a OpenAI en la misma conversación (mensajes 3, 4, y 2 más)

**Tú escribes** (después de 4 llamadas):
```
Tengo otra objeción sobre el precio
```

**LUISA debe responder** (fallback heurístico, NO OpenAI):
```
"Entiendo tu preocupación. Tenemos opciones desde $400.000 para uso familiar. 
¿Te interesa ver opciones de financiamiento o prefieres una máquina usada?"
```
o similar (fallback del adapter, no inventado)

**Logs esperados**:
```
"message": "message_received",
"conversation_id": "wa_xxx",
"message_id": "wamid.xxx",
"phone": "xxxx",
"mode": "AI_ACTIVE",
"text_preview": "Tengo otra objeción sobre el precio"

"message": "llm_decision_made",
"task_type": "objecion",
"gating_passed": true

"message": "LLM Adapter: Límite de llamadas excedido",
"conversation_id": "wa_xxx",
"current_count": 4,
"max_calls": 4,
"task_type": "objecion",
"reason_for_llm_use": "objecion:..."

"message": "LLM Adapter fallback usado",
"task_type": "objecion",
"error": "max_calls_per_conversation_exceeded"

"message": "Mensaje WhatsApp procesado y respondido",
"openai_used": false,
"task_type": null,
"decision_path": "->openai_max_calls_exceeded" (o similar)
```

**Validar**:
- ✅ LUISA responde (fallback funciona)
- ✅ `openai_used=false` (no se llamó OpenAI)
- ✅ Log `LLM Adapter: Límite de llamadas excedido` presente
- ✅ `current_count=4` y `max_calls=4`

---

**Opción B: Simular Fallo de OpenAI (Sin Tumbar Producción)**

**Cómo validar sin tumbar producción**:
1. Temporalmente cambiar `OPENAI_API_KEY` a un valor inválido en `.env`
2. Reiniciar contenedor: `docker compose restart backend`
3. Enviar mensaje de objeción
4. Verificar que fallback funciona
5. Restaurar `OPENAI_API_KEY` correcto
6. Reiniciar: `docker compose restart backend`

**Tú escribes** (con API key inválida):
```
Está muy caro
```

**LUISA debe responder** (fallback):
```
"Entiendo tu preocupación. Tenemos opciones desde $400.000 para uso familiar. 
¿Te interesa ver opciones de financiamiento?"
```
o similar (fallback del adapter)

**Logs esperados**:
```
"message": "llm_decision_made",
"task_type": "objecion"

"message": "LLM Adapter: OpenAI exception",
"error": "Incorrect API key provided" (o similar, sanitizado),
"task_type": "objecion"

"message": "LLM Adapter fallback usado",
"task_type": "objecion",
"error": "exception: Incorrect API key..."

"message": "Mensaje WhatsApp procesado y respondido",
"openai_used": false,
"decision_path": "->openai_error"
```

**Validar**:
- ✅ LUISA responde (fallback funciona)
- ✅ `openai_used=false`
- ✅ Log de error presente pero sanitizado (no expone key completa)
- ✅ Respuesta es coherente (no inventada)

---

## 5. Resumen de Logs por Mensaje

| Mensaje | `message_received` | `llm_decision_made` | `LLM Adapter usado` | `Mensaje procesado` | `reply_sent_in_human_active` |
|---------|-------------------|-------------------|-------------------|-------------------|----------------------------|
| 1. Saludo | ✅ | ❌ | ❌ | ✅ (`openai_used=false`) | ❌ |
| 2. Intención clara | ✅ | ❌ (o ✅ si usa COPY) | ❌ (o ✅) | ✅ | ❌ |
| 3. Objeción | ✅ | ✅ (`task_type=objecion`) | ✅ (`call_count=1`) | ✅ (`openai_used=true`) | ❌ |
| 4. Ambiguo | ✅ | ✅ (`task_type=consulta_compleja`) | ✅ (`call_count=2`) | ✅ (`openai_used=true`) | ❌ |
| 5. Técnico | ✅ | ❌ | ❌ | ✅ | ❌ (o ✅ si handoff) |
| 6. Handoff "sí" | ✅ (`mode=HUMAN_ACTIVE`) | ❌ | ❌ | ❌ | ✅ |
| 7. Follow-up | ✅ (`mode=HUMAN_ACTIVE`) | ❌ | ❌ | ❌ | ✅ |
| 8. Fallback | ✅ | ✅ | ❌ (límite/error) | ✅ (`openai_used=false`) | ❌ |

---

## 6. Checklist de Activación

### Pre-activación
- [ ] `.env` existe en raíz del proyecto (`Sastre/.env`)
- [ ] `OPENAI_API_KEY` está configurado (valor real, no placeholder)
- [ ] `OPENAI_ENABLED=true` en `.env`
- [ ] `OPENAI_MAX_CALLS_PER_CONVERSATION=4` en `.env`
- [ ] `OPENAI_CONVERSATION_TTL_HOURS=24` en `.env`

### Código
- [ ] Cambios de logging aplicados (diffs de sección 2)
- [ ] Código compila sin errores
- [ ] No hay imports faltantes

### Docker
- [ ] `docker-compose.yml` tiene `env_file: - .env`
- [ ] Contenedor puede leer variables de `.env`

### Post-activación
- [ ] Contenedor inicia sin errores
- [ ] Health check responde OK
- [ ] Logs muestran `OPENAI_ENABLED=True` (sin errores de API key)
- [ ] Mensaje de prueba (saludo) funciona
- [ ] Mensaje de objeción usa OpenAI (`llm_decision_made` presente)

---

## 7. Comandos Copy/Paste para VPS

```bash
# ============================================================================
# PASO 1: Verificar .env existe y tiene variables OpenAI
# ============================================================================
cd /ruta/a/Sastre
cat .env | grep -E "OPENAI_ENABLED|OPENAI_API_KEY|OPENAI_MAX_CALLS" | head -5

# ============================================================================
# PASO 2: Aplicar cambios de código (si no están en repo)
# ============================================================================
# Opción A: Si cambios están en repo
git pull origin main

# Opción B: Si cambios NO están en repo, aplicar diffs manualmente
# (ver sección 2 de este documento)

# ============================================================================
# PASO 3: Reconstruir y reiniciar
# ============================================================================
docker compose down
docker compose build backend
docker compose up -d

# ============================================================================
# PASO 4: Verificar variables en contenedor
# ============================================================================
docker exec luisa-backend python3 -c "from app.config import OPENAI_ENABLED, OPENAI_MAX_CALLS_PER_CONVERSATION; print(f'OPENAI_ENABLED={OPENAI_ENABLED}, MAX_CALLS={OPENAI_MAX_CALLS_PER_CONVERSATION}')"

# ============================================================================
# PASO 5: Verificar logs de inicio
# ============================================================================
docker compose logs backend | grep -E "OPENAI|Error|Warning" | tail -20

# ============================================================================
# PASO 6: Health check
# ============================================================================
curl -s https://luisa-agent.online/health | jq .

# ============================================================================
# PASO 7: Monitorear logs en tiempo real (opcional)
# ============================================================================
docker compose logs -f backend | grep -E "message_received|llm_decision_made|LLM Adapter|reply_sent_in_human_active"
```

---

## 8. Validación de Fallback (Sin Tumbar Producción)

### Método 1: API Key Inválida Temporal

```bash
# Backup del .env
cp .env .env.backup

# Modificar API key a inválida
sed -i 's/OPENAI_API_KEY=sk-.*/OPENAI_API_KEY=sk-invalid-key-for-testing/' .env

# Reiniciar backend
docker compose restart backend

# Esperar 10 segundos
sleep 10

# Enviar mensaje de objeción desde WhatsApp
# (escribir: "Está muy caro")

# Verificar logs de fallback
docker compose logs backend | grep -E "LLM Adapter.*exception|LLM Adapter fallback usado" | tail -5

# Restaurar API key correcta
cp .env.backup .env
docker compose restart backend
```

---

## 9. Resumen Ejecutivo

### Estado Actual
- ✅ Límites de OpenAI ya implementados (4 llamadas/conversación, TTL 24h)
- ✅ Timeout duro (5s) y fallback garantizado
- ✅ Docker Compose lee `.env` correctamente
- ⚠️ Faltan 2 logs: `message_received`, `llm_decision_made`

### Cambios Requeridos
1. **`.env`**: Agregar variables OpenAI (ver sección 2, Cambio 4)
2. **`whatsapp.py`**: Agregar log `message_received` (línea ~383)
3. **`response_service.py`**: Agregar log `llm_decision_made` (línea ~722)
4. **`whatsapp.py`**: Mejorar log `Mensaje procesado` con `openai_used`, `task_type`, `decision_path` (línea ~522)

### Plan de Pruebas
- 8 mensajes manuales desde WhatsApp
- Cada mensaje tiene: qué escribir, qué esperar, qué logs validar
- Incluye validación de fallback sin tumbar producción

---

**Última actualización**: 2025-01-05  
**Estado**: ✅ Listo para activación en producción

