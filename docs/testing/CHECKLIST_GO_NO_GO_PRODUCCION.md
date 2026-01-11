# Checklist GO / NO-GO para Producción

**Fecha**: 2025-01-05  
**Versión**: 2.0 (Post-implementación de límites OpenAI y copy refinado)  
**Objetivo**: Verificar que LUISA está lista para demo comercial en producción

---

## Criterio General GO/NO-GO

✅ **GO**: Todos los checks críticos (⚠️) pasan + Máximo 2 warnings no críticos  
❌ **NO-GO**: Algún check crítico falla o más de 2 warnings

---

## 1. Infraestructura ⚠️

### 1.1 Docker Containers

- [ ] **⚠️ CRÍTICO**: Todos los containers están corriendo
  ```bash
  docker compose ps
  ```
  **Esperado**: `luisa-backend` y `luisa-caddy` en estado `Up`

- [ ] **⚠️ CRÍTICO**: Health check del backend OK (local)
  ```bash
  curl -f http://localhost:8000/health
  ```
  **Esperado**: `200 OK` con JSON `{"status": "healthy", ...}`

- [ ] **⚠️ CRÍTICO**: Health check del backend OK (público)
  ```bash
  curl -f https://luisa-agent.online/health
  ```
  **Esperado**: `200 OK` con JSON válido

- [ ] **⚠️ CRÍTICO**: HTTPS válido (no expirado)
  ```bash
  curl -I https://luisa-agent.online/health 2>&1 | grep -i "SSL\|expired"
  openssl s_client -connect luisa-agent.online:443 -servername luisa-agent.online < /dev/null 2>&1 | grep -i "Verify return code: 0"
  ```
  **Esperado**: Certificado válido, no expirado

- [ ] **⚠️ CRÍTICO**: Caddy reverse proxy funcionando
  ```bash
  docker compose logs caddy | tail -20 | grep -i "proxy\|error"
  ```
  **Esperado**: Sin errores de proxy, conexión OK

### 1.2 Base de Datos

- [ ] **⚠️ CRÍTICO**: Base de datos existe y es accesible
  ```bash
  docker compose exec backend python -c "from app.models.database import get_connection; conn = get_connection(); print('DB OK')"
  ```
  **Esperado**: Sin errores, mensaje "DB OK"

- [ ] **⚠️ CRÍTICO**: Todas las tablas críticas existen
  ```bash
  docker compose exec backend python -c "from app.models.database import init_db; init_db(); print('Tables OK')"
  ```
  **Esperado**: Sin errores, tablas creadas/validadas

- [ ] Tabla `conversations` tiene columnas nuevas (OpenAI tracking)
  ```bash
  docker compose exec backend python -c "from app.models.database import get_connection; conn = get_connection(); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(conversations)'); cols = [r[1] for r in cursor.fetchall()]; assert 'openai_calls_count' in cols; print('OpenAI columns OK')"
  ```
  **Esperado**: Columnas `openai_calls_count`, `first_openai_call_at`, `last_openai_call_at` presentes

### 1.3 Recursos

- [ ] **⚠️ CRÍTICO**: Memoria disponible suficiente
  ```bash
  docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}"
  ```
  **Esperado**: Backend < 300MB, Caddy < 50MB

- [ ] **⚠️ CRÍTICO**: Disco disponible suficiente
  ```bash
  df -h | grep -E "/$|/data"
  ```
  **Esperado**: Al menos 2GB libres (para logs y DB)

- [ ] CPU no saturada
  ```bash
  docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}"
  ```
  **Esperado**: CPU < 80% promedio

---

## 2. WhatsApp ⚠️

### 2.1 Configuración

- [ ] **⚠️ CRÍTICO**: `WHATSAPP_ENABLED=true` en `.env`
  ```bash
  grep -E "^WHATSAPP_ENABLED=" .env
  ```
  **Esperado**: `WHATSAPP_ENABLED=true`

- [ ] **⚠️ CRÍTICO**: `WHATSAPP_ACCESS_TOKEN` configurado (no vacío)
  ```bash
  grep -E "^WHATSAPP_ACCESS_TOKEN=" .env | sed 's/=.*/=***HIDDEN***/'
  ```
  **Esperado**: Token presente, no vacío

- [ ] **⚠️ CRÍTICO**: `WHATSAPP_PHONE_NUMBER_ID` configurado (no vacío)
  ```bash
  grep -E "^WHATSAPP_PHONE_NUMBER_ID=" .env
  ```
  **Esperado**: Phone number ID presente, no vacío

- [ ] **⚠️ CRÍTICO**: `WHATSAPP_VERIFY_TOKEN` configurado (no vacío)
  ```bash
  grep -E "^WHATSAPP_VERIFY_TOKEN=" .env | sed 's/=.*/=***HIDDEN***/'
  ```
  **Esperado**: Token presente, debe coincidir con Meta Dashboard

- [ ] `WHATSAPP_VERIFY_TOKEN` coincide con Meta Dashboard
  - **Manual**: Verificar en Meta Business Dashboard → Webhooks → Verify Token
  - **Esperado**: Coincide exactamente (case-sensitive)

### 2.2 Webhook

- [ ] **⚠️ CRÍTICO**: Webhook URL correcta en Meta
  - **Manual**: Meta Dashboard → Webhooks → Callback URL
  - **Esperado**: `https://luisa-agent.online/whatsapp/webhook`

- [ ] **⚠️ CRÍTICO**: GET verification funciona
  ```bash
  curl "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=TU_TOKEN&hub.challenge=test123"
  ```
  **Esperado**: Retorna `test123` (text/plain)

- [ ] **⚠️ CRÍTICO**: Webhook recibe mensajes (verificar logs)
  ```bash
  docker compose logs backend --tail 100 | grep -i "webhook.*POST\|whatsapp.*message\|_process_whatsapp_message"
  ```
  **Esperado**: Logs de recepción de mensajes en últimas 24h

- [ ] POST de mensajes genera logs correctos
  ```bash
  docker compose logs backend --tail 50 | grep -i "message_id\|queued_processing\|decision_path"
  ```
  **Esperado**: Logs estructurados con `message_id`, `decision_path`

- [ ] POST de statuses se ignoran (no procesan)
  ```bash
  docker compose logs backend --tail 100 | grep -i "status.*ignored\|ignore.*status"
  ```
  **Esperado**: Sin logs de procesamiento de statuses

### 2.3 Respuestas

- [ ] **⚠️ CRÍTICO**: No hay errores 4xx/5xx al responder
  ```bash
  docker compose logs backend --tail 200 | grep -i "error.*4\|error.*5\|http.*40\|http.*50"
  ```
  **Esperado**: Máximo 1-2 errores no críticos en últimas 100 respuestas

- [ ] Rate limiting funciona (máx 20 req/min)
  ```bash
  docker compose logs backend --tail 200 | grep -i "rate.*limit\|too.*many"
  ```
  **Esperado**: Si hay rate limiting, está funcionando correctamente

- [ ] Idempotencia funciona (no procesa mensajes duplicados)
  ```bash
  docker compose exec backend python -c "from app.models.database import get_connection; conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM wa_outbox_dedup WHERE created_at > datetime(\"now\", \"-1 day\")'); print(f'Dedup entries: {cursor.fetchone()[0]}')"
  ```
  **Esperado**: Entradas de deduplicación presentes

---

## 3. OpenAI ⚠️

### 3.1 Configuración

- [ ] **⚠️ CRÍTICO** (si OPENAI_ENABLED=true): `OPENAI_API_KEY` configurado
  ```bash
  grep -E "^OPENAI_ENABLED=" .env
  grep -E "^OPENAI_API_KEY=" .env | sed 's/=.*/=***HIDDEN***/'
  ```
  **Esperado**: Si `OPENAI_ENABLED=true`, token presente

- [ ] `OPENAI_ENABLED` es `true` o `false` (no ambiguo)
  ```bash
  grep -E "^OPENAI_ENABLED=" .env
  ```
  **Esperado**: `OPENAI_ENABLED=true` o `OPENAI_ENABLED=false`

- [ ] Límites de uso configurados correctamente
  ```bash
  grep -E "^OPENAI_MAX_CALLS_PER_CONVERSATION=|^OPENAI_CONVERSATION_TTL_HOURS=|^OPENAI_MAX_TOKENS_PER_CALL=" .env
  ```
  **Esperado**: Valores razonables (default: 4, 24, 180)

### 3.2 Funcionalidad

- [ ] **⚠️ CRÍTICO** (si OPENAI_ENABLED=true): OpenAI responde sin errores
  ```bash
  docker compose logs backend --tail 200 | grep -i "openai\|llm.*adapter" | grep -i "error\|timeout\|failed"
  ```
  **Esperado**: Máximo 5% de errores en llamadas (si está habilitado)

- [ ] Límites de llamadas por conversación funcionan
  ```bash
  docker compose logs backend --tail 200 | grep -i "max_calls_per_conversation_exceeded\|limit_exceeded"
  ```
  **Esperado**: Si hay límites excedidos, están siendo bloqueados correctamente

- [ ] Reset por TTL funciona
  ```bash
  docker compose logs backend --tail 200 | grep -i "contador.*reseteado\|reset.*ttl\|conversation.*ttl"
  ```
  **Esperado**: Logs de reset cuando TTL expira

- [ ] Tracking de llamadas funciona
  ```bash
  docker compose exec backend python -c "from app.models.database import get_openai_call_count; print('Tracking OK')"
  ```
  **Esperado**: Sin errores, función importable

### 3.3 Fallbacks

- [ ] **⚠️ CRÍTICO**: Fallback funciona si OpenAI falla
  ```bash
  docker compose logs backend --tail 200 | grep -i "fallback.*used\|openai.*error.*fallback"
  ```
  **Esperado**: Si hay errores de OpenAI, se usa fallback (no silencio)

- [ ] Respuestas siempre generadas (nunca `None` sin fallback)
  ```bash
  docker compose logs backend --tail 200 | grep -i "response.*none\|text.*empty" | grep -v "fallback"
  ```
  **Esperado**: Sin respuestas vacías sin fallback

---

## 4. Costos ⚠️

### 4.1 Control de Costos

- [ ] **⚠️ CRÍTICO**: Límites de uso configurados
  ```bash
  grep -E "^OPENAI_MAX_CALLS_PER_CONVERSATION=|^OPENAI_MAX_TOKENS_PER_CALL=" .env
  ```
  **Esperado**: Valores presentes y razonables

- [ ] **⚠️ CRÍTICO**: TTL de conversación configurado
  ```bash
  grep -E "^OPENAI_CONVERSATION_TTL_HOURS=" .env
  ```
  **Esperado**: Valor presente (default: 24)

- [ ] Modelo económico configurado (si OPENAI habilitado)
  ```bash
  grep -E "^OPENAI_MODEL=" .env
  ```
  **Esperado**: `gpt-4o-mini` (económico) o similar

### 4.2 Monitoreo

- [ ] Tracking de llamadas por conversación funciona
  ```bash
  docker compose exec backend python -c "from app.models.database import get_connection; conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM conversations WHERE openai_calls_count > 0'); print(f'Conversaciones con OpenAI: {cursor.fetchone()[0]}')"
  ```
  **Esperado**: Número de conversaciones con llamadas OpenAI

- [ ] Logging de costos presente
  ```bash
  docker compose logs backend --tail 200 | grep -i "tokens_used\|openai_call_count\|reason_for_llm_use"
  ```
  **Esperado**: Logs con `tokens_used`, `openai_call_count`, `reason_for_llm_use`

- [ ] Estimación de costos diarios razonable
  ```bash
  # Calcular: llamadas/día * tokens/llamada * costo/token
  # Ejemplo: 100 llamadas * 150 tokens * $0.00015 = ~$0.02/día
  ```
  **Esperado**: < $5/día para demo comercial

---

## 5. Logs ⚠️

### 5.1 Configuración

- [ ] **⚠️ CRÍTICO**: `PRODUCTION_MODE=true` en `.env`
  ```bash
  grep -E "^PRODUCTION_MODE=" .env
  ```
  **Esperado**: `PRODUCTION_MODE=true`

- [ ] **⚠️ CRÍTICO**: `LOG_FORMAT=json` en `.env`
  ```bash
  grep -E "^LOG_FORMAT=" .env
  ```
  **Esperado**: `LOG_FORMAT=json`

- [ ] `LOG_LEVEL=INFO` (no DEBUG en producción)
  ```bash
  grep -E "^LOG_LEVEL=" .env
  ```
  **Esperado**: `LOG_LEVEL=INFO` o `WARNING`

### 5.2 Logs Críticos

- [ ] **⚠️ CRÍTICO**: Logs de mensajes recibidos presentes
  ```bash
  docker compose logs backend --tail 100 | grep -i "whatsapp.*message\|_process_whatsapp_message" | head -5
  ```
  **Esperado**: Al menos 1 log de mensaje recibido

- [ ] **⚠️ CRÍTICO**: Logs de respuestas enviadas presentes
  ```bash
  docker compose logs backend --tail 100 | grep -i "reply.*sent\|message.*sent\|send.*whatsapp"
  ```
  **Esperado**: Al menos 1 log de respuesta enviada

- [ ] **⚠️ CRÍTICO**: Logs de HUMAN_ACTIVE presentes (si aplica)
  ```bash
  docker compose logs backend --tail 200 | grep -i "reply_sent_in_human_active\|reply_failed_in_human_active"
  ```
  **Esperado**: Si hay handoffs, logs de HUMAN_ACTIVE presentes

- [ ] **⚠️ CRÍTICO**: Logs de TTL revert presentes (si aplica)
  ```bash
  docker compose logs backend --tail 200 | grep -i "mode_auto_reverted_to_ai\|ttl.*expired"
  ```
  **Esperado**: Si hay TTL expirados, logs presentes

- [ ] Logs de límites OpenAI presentes (si aplica)
  ```bash
  docker compose logs backend --tail 200 | grep -i "max_calls_per_conversation_exceeded\|limit_exceeded\|openai_call_count"
  ```
  **Esperado**: Si hay límites excedidos, logs presentes

- [ ] Logs estructurados (JSON válido)
  ```bash
  docker compose logs backend --tail 10 | grep -v "^#" | python -m json.tool > /dev/null 2>&1 && echo "JSON OK" || echo "JSON invalid"
  ```
  **Esperado**: "JSON OK"

### 5.3 Errores

- [ ] **⚠️ CRÍTICO**: Sin errores críticos en logs
  ```bash
  docker compose logs backend --tail 500 | grep -iE "error|exception|traceback" | grep -vE "debug|warn" | head -20
  ```
  **Esperado**: Máximo 5 errores no críticos en últimas 500 líneas

- [ ] Sin errores de conexión a OpenAI (si habilitado)
  ```bash
  docker compose logs backend --tail 200 | grep -i "openai.*connection\|timeout.*openai\|api.*error" | head -10
  ```
  **Esperado**: Máximo 2-3 errores de conexión/timeout (tolerable)

- [ ] Sin errores de WhatsApp API
  ```bash
  docker compose logs backend --tail 200 | grep -i "whatsapp.*error\|meta.*error\|webhook.*error" | head -10
  ```
  **Esperado**: Sin errores de WhatsApp API (si hay, investigar)

---

## 6. Flujos Críticos ⚠️

### 6.1 Flujo 1: Nuevo Usuario → Saludo

- [ ] **⚠️ CRÍTICO**: Usuario nuevo recibe saludo
  ```bash
  # Enviar mensaje "hola" desde WhatsApp y verificar respuesta
  # O usar script de prueba:
  docker compose exec backend python -c "from app.services.response_service import build_response; from app.models.database import create_or_update_conversation; import uuid; cid = str(uuid.uuid4()); create_or_update_conversation(cid, '+573001234567', 'whatsapp'); r = build_response('hola', cid, 'whatsapp', '+573001234567'); print(f'Response: {r[\"text\"]}')"
  ```
  **Esperado**: Respuesta contiene "Hola", "Luisa", pregunta cerrada

- [ ] Copy refinado presente en saludo
  ```bash
  # Verificar que el mensaje usa el nuevo copy
  # Debe contener: "¡Hola! 👋 Soy Luisa del Sastre."
  ```
  **Esperado**: Mensaje contiene el nuevo copy refinado

### 6.2 Flujo 2: Handoff → Usuario Responde

- [ ] **⚠️ CRÍTICO**: Handoff se activa correctamente
  ```bash
  docker compose logs backend --tail 200 | grep -i "handoff.*triggered\|handoff.*processed" | head -5
  ```
  **Esperado**: Logs de handoff presentes cuando corresponde

- [ ] **⚠️ CRÍTICO**: Usuario recibe mensaje de handoff (copy refinado)
  ```bash
  # Verificar que el mensaje de handoff usa el nuevo copy
  # Debe ser corto (2 líneas), con pregunta cerrada
  ```
  **Esperado**: Mensaje contiene copy refinado (2 líneas, pregunta cerrada)

- [ ] **⚠️ CRÍTICO**: Modo HUMAN_ACTIVE se activa
  ```bash
  docker compose exec backend python -c "from app.models.database import get_conversation_mode; print('Mode:', get_conversation_mode('CONVERSATION_ID_TEST'))"
  ```
  **Esperado**: Si hay handoff, modo es `HUMAN_ACTIVE`

### 6.3 Flujo 3: FIX P0 - Nunca Silencio

- [ ] **⚠️ CRÍTICO**: Usuario escribe después de handoff → LUISA responde
  ```bash
  # Enviar mensaje después de handoff y verificar respuesta
  docker compose logs backend --tail 100 | grep -i "reply_sent_in_human_active"
  ```
  **Esperado**: Log `reply_sent_in_human_active` presente

- [ ] **⚠️ CRÍTICO**: Respuesta en HUMAN_ACTIVE usa copy refinado
  ```bash
  # Verificar que el mensaje es:
  # "¡Hola! 😊 Un asesor te va a contactar pronto.\n¿Quieres que pase tu nombre y barrio para que todo esté listo?"
  ```
  **Esperado**: Copy refinado presente (2 líneas, pregunta cerrada)

- [ ] Sin silencio total (nunca `None` sin respuesta)
  ```bash
  docker compose logs backend --tail 200 | grep -i "response.*none\|text.*empty" | grep -v "fallback"
  ```
  **Esperado**: Sin respuestas vacías

### 6.4 Flujo 4: FIX P1 - TTL Automático

- [ ] **⚠️ CRÍTICO**: TTL expira → Modo revertido a AI_ACTIVE
  ```bash
  # Simular TTL expirado o verificar logs:
  docker compose logs backend --tail 200 | grep -i "mode_auto_reverted_to_ai"
  ```
  **Esperado**: Log `mode_auto_reverted_to_ai` presente si TTL expira

- [ ] Después de TTL, conversación vuelve a AI normal
  ```bash
  # Verificar que después del TTL, la conversación procesa mensajes normalmente
  ```
  **Esperado**: Sin bloqueo permanente en HUMAN_ACTIVE

### 6.5 Flujo 5: OpenAI con Límites

- [ ] **⚠️ CRÍTICO** (si OPENAI_ENABLED=true): Llamadas OpenAI funcionan
  ```bash
  docker compose logs backend --tail 200 | grep -i "llm.*adapter.*used\|openai.*called" | head -5
  ```
  **Esperado**: Logs de llamadas OpenAI presentes (si habilitado)

- [ ] Límite de llamadas se respeta
  ```bash
  # Verificar que después de 4 llamadas, la 5ta retorna None con error
  docker compose logs backend --tail 200 | grep -i "max_calls_per_conversation_exceeded"
  ```
  **Esperado**: Si hay límites excedidos, están bloqueados

- [ ] Fallback funciona cuando límite excedido
  ```bash
  docker compose logs backend --tail 200 | grep -i "limit_exceeded.*fallback"
  ```
  **Esperado**: Si límite excedido, se usa fallback (no silencio)

### 6.6 Flujo 6: Copy Refinado en Todos los Mensajes

- [ ] **⚠️ CRÍTICO**: Todos los mensajes usan copy refinado
  ```bash
  # Verificar que NO aparecen mensajes antiguos:
  docker compose logs backend --tail 200 | grep -i "Almacén El Sastre\|Cuéntame qué necesitas\|En este punto lo mejor"
  ```
  **Esperado**: Sin mensajes antiguos (deben usar copy refinado)

- [ ] Mensajes cortos (máx 3 líneas)
  ```bash
  docker compose exec backend python -c "from app.services.response_service import build_response; from app.models.database import create_or_update_conversation; import uuid; cid = str(uuid.uuid4()); create_or_update_conversation(cid, '+573001234567', 'whatsapp'); r = build_response('hola', cid, 'whatsapp', '+573001234567'); lines = r['text'].count('\n') + 1; print(f'Lines: {lines}'); assert lines <= 3, 'Message too long'"
  ```
  **Esperado**: Mensajes tienen máximo 3 líneas

- [ ] Preguntas cerradas presentes
  ```bash
  # Verificar que mensajes terminan con pregunta cerrada (¿...?)
  ```
  **Esperado**: Todos los mensajes terminan con pregunta cerrada

---

## 7. Performance

### 7.1 Tiempos de Respuesta

- [ ] **⚠️ CRÍTICO**: Tiempo de respuesta promedio < 2s
  ```bash
  docker compose logs backend --tail 200 | grep -i "latency_ms" | python3 -c "import sys, json; lines = [l for l in sys.stdin if 'latency_ms' in l]; latencies = [json.loads(l.split('|')[0] if '|' in l else l)['latency_ms'] for l in lines if 'latency_ms' in str(json.loads(l.split('|')[0] if '|' in l else l))]; print(f'Avg: {sum(latencies)/len(latencies):.0f}ms' if latencies else 'No data')"
  ```
  **Esperado**: Promedio < 2000ms

- [ ] 95% de respuestas < 3s
  ```bash
  # Calcular percentil 95 de latencias
  ```
  **Esperado**: 95% < 3000ms

### 7.2 Recursos

- [ ] CPU promedio < 50%
- [ ] Memoria estable (no memory leak)
  ```bash
  docker stats --no-stream --format "{{.MemUsage}}" luisa-backend
  # Monitorear durante 10 min, verificar que no crece constantemente
  ```
  **Esperado**: Memoria estable (no crecimiento constante)

---

## 8. Seguridad

- [ ] **⚠️ CRÍTICO**: Secrets no expuestos en logs
  ```bash
  docker compose logs backend --tail 500 | grep -iE "sk-|EAA|password|secret|token.*=" | grep -v "HIDDEN\|***"
  ```
  **Esperado**: Sin secrets expuestos (si hay, son filtrados)

- [ ] Rate limiting activo
  ```bash
  docker compose logs backend --tail 200 | grep -i "rate.*limit"
  ```
  **Esperado**: Rate limiting funcionando

- [ ] HTTPS solo (no HTTP)
  ```bash
  curl -I http://luisa-agent.online/health 2>&1 | grep -i "301\|302\|https"
  ```
  **Esperado**: HTTP redirige a HTTPS

---

## 9. Monitoreo y Alertas

- [ ] Logs estructurados (JSON) para parsing
- [ ] Health check endpoint accesible
- [ ] Métricas clave logueadas (latency, errors, costs)

---

## Resumen de Verificación

### Checks Críticos (⚠️)

**Total**: ~45 checks críticos  
**Pasados**: ___ / 45  
**Fallidos**: ___ / 45  

### Warnings No Críticos

**Total**: ~15 checks opcionales  
**Presentes**: ___ / 15  

---

## Decisión Final

- [ ] **✅ GO**: Todos los checks críticos pasan + Máx 2 warnings
- [ ] **❌ NO-GO**: Algún check crítico falla o > 2 warnings

**Justificación**:
```
[Completar aquí la justificación de la decisión]
```

---

## Comandos Opcionales (Copy/Paste)

### Verificación Rápida

```bash
# 1. Estado de containers
docker compose ps

# 2. Health check
curl -f https://luisa-agent.online/health | jq

# 3. Verificar logs recientes
docker compose logs backend --tail 50

# 4. Verificar errores
docker compose logs backend --tail 500 | grep -iE "error|exception" | grep -v "debug\|warn" | head -20

# 5. Verificar mensajes recibidos
docker compose logs backend --tail 100 | grep -i "whatsapp.*message" | head -10

# 6. Verificar respuestas enviadas
docker compose logs backend --tail 100 | grep -i "reply.*sent\|message.*sent" | head -10

# 7. Verificar HUMAN_ACTIVE
docker compose logs backend --tail 200 | grep -i "reply_sent_in_human_active\|mode_auto_reverted_to_ai"

# 8. Verificar límites OpenAI
docker compose logs backend --tail 200 | grep -i "max_calls_per_conversation_exceeded\|openai_call_count"

# 9. Verificar configuración
docker compose exec backend python -c "from app.config import validate_config; warnings = validate_config(); print('Warnings:', warnings if warnings else 'None')"

# 10. Verificar base de datos
docker compose exec backend python -c "from app.models.database import get_connection; conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM conversations'); print(f'Conversations: {cursor.fetchone()[0]}')"
```

### Testing de Flujos

```bash
# Test Flujo 1: Saludo
curl -X POST https://luisa-agent.online/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hola", "conversation_id": "test_123", "channel": "whatsapp", "customer_number": "+573001234567"}' | jq

# Test Flujo 2: Handoff (simulado)
# [Enviar mensaje que active handoff desde WhatsApp real]

# Test Flujo 3: HUMAN_ACTIVE follow-up
# [Enviar mensaje después de handoff desde WhatsApp real]

# Test Flujo 4: TTL (requiere esperar o modificar DB)
docker compose exec backend python -c "
from app.models.database import get_db
from datetime import datetime, timedelta
import sqlite3
with get_db() as conn:
    cursor = conn.cursor()
    # Actualizar first_openai_call_at a hace 25 horas
    cursor.execute('UPDATE conversations SET first_openai_call_at = datetime(\"now\", \"-25 hours\") WHERE conversation_id = \"TEST_TTL\"')
    conn.commit()
print('TTL test setup OK')
"
```

### Monitoreo Continuo

```bash
# Watch logs en tiempo real
docker compose logs -f backend | grep -E "error|exception|reply_sent|mode_auto_reverted"

# Watch health check
watch -n 5 'curl -s https://luisa-agent.online/health | jq'

# Watch recursos
watch -n 2 'docker stats --no-stream'

# Watch mensajes WhatsApp
docker compose logs -f backend | grep -i "whatsapp.*message"
```

### Análisis de Logs

```bash
# Contar errores por tipo
docker compose logs backend --since 1h | grep -i "error" | cut -d' ' -f5- | sort | uniq -c | sort -rn | head -10

# Latencia promedio
docker compose logs backend --since 1h | grep -i "latency_ms" | python3 -c "
import sys, json, re
latencies = []
for line in sys.stdin:
    try:
        match = re.search(r'latency_ms[:\"]\s*(\d+)', line)
        if match:
            latencies.append(int(match.group(1)))
    except:
        pass
if latencies:
    print(f'Avg: {sum(latencies)/len(latencies):.0f}ms')
    print(f'P95: {sorted(latencies)[int(len(latencies)*0.95)]}ms')
else:
    print('No data')
"

# Contar llamadas OpenAI
docker compose logs backend --since 1h | grep -i "llm.*adapter.*used\|openai.*called.*true" | wc -l

# Contar límites excedidos
docker compose logs backend --since 1h | grep -i "max_calls_per_conversation_exceeded" | wc -l
```

---

**Última actualización**: 2025-01-05  
**Versión**: 2.0  
**Responsable**: SRE + Backend Lead

