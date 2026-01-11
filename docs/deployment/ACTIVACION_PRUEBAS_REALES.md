# Activación para Pruebas Reales - LUISA

**Fecha**: 2026-01-07  
**Estado**: ⚠️ **Requiere configuración final**

---

## ✅ Cambios Aplicados

### 1. Configuración `.env` Actualizada

**Variables activadas**:
- ✅ `WHATSAPP_ENABLED=true`
- ✅ `OPENAI_ENABLED=true`
- ⚠️ `OPENAI_API_KEY=sk-PLACEHOLDER-REEMPLAZA-CON-TU-KEY-REAL` ← **REEMPLAZA ESTO**

**Límites configurados**:
- ✅ `OPENAI_MAX_CALLS_PER_CONVERSATION=4`
- ✅ `OPENAI_CONVERSATION_TTL_HOURS=24`
- ✅ `OPENAI_MAX_OUTPUT_TOKENS=150`
- ✅ `OPENAI_TEMPERATURE=0.3`

---

## ⚠️ Acción Requerida: Agregar API Key de OpenAI

**Paso 1**: Editar `.env` y reemplazar el placeholder:

```bash
cd /Users/camilope/AI-Agents/Sastre
nano .env
```

**Paso 2**: Cambiar esta línea:
```
OPENAI_API_KEY=sk-PLACEHOLDER-REEMPLAZA-CON-TU-KEY-REAL
```

Por tu API key real:
```
OPENAI_API_KEY=sk-tu-key-real-aqui
```

**Paso 3**: Guardar el archivo (Ctrl+X, Y, Enter)

---

## 🔄 Reiniciar Servicios

Después de actualizar `.env`, reiniciar el backend:

### Opción A: Si usas Docker Compose
```bash
cd /Users/camilope/AI-Agents/Sastre
docker compose restart backend
```

### Opción B: Si el backend corre directamente
```bash
# Detener proceso actual (si existe)
pkill -f "python.*main.py" || pkill -f uvicorn

# Reiniciar (ajusta según tu setup)
cd /Users/camilope/AI-Agents/Sastre/backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ✅ Verificación Post-Activación

### 1. Verificar Variables en Backend

```bash
# Si usas Docker
docker exec luisa-backend python3 -c "from app.config import OPENAI_ENABLED, OPENAI_MAX_CALLS_PER_CONVERSATION; print(f'OPENAI_ENABLED={OPENAI_ENABLED}, MAX_CALLS={OPENAI_MAX_CALLS_PER_CONVERSATION}')"

# Si corre directamente
curl -s http://localhost:8000/health | python3 -m json.tool
```

**Salida esperada**:
```json
{
  "status": "healthy",
  "service": "luisa",
  "whatsapp_enabled": true,
  ...
}
```

---

### 2. Verificar que OpenAI está Habilitado

```bash
# Revisar logs de inicio
docker compose logs backend | grep -i "openai\|whatsapp" | tail -10

# O si corre directamente, revisar la salida del proceso
```

**Qué buscar**:
- ✅ No debe aparecer: `"OPENAI_ENABLED=true pero OPENAI_API_KEY está vacío"`
- ✅ Debe aparecer: `"WhatsApp webhook habilitado"` (si WHATSAPP_ENABLED=true)

---

### 3. Probar Webhook Localmente

```bash
# Enviar mensaje de prueba
curl -X POST http://localhost:8000/whatsapp/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "573142156486",
            "id": "wamid.test_real",
            "type": "text",
            "text": {"body": "Hola"}
          }]
        }
      }]
    }]
  }'

# Debe responder: {"status": "ok", "queued": true}
```

---

### 4. Verificar Logs de Procesamiento

```bash
# Ver logs en tiempo real
docker compose logs -f backend | grep -E "message_received|llm_decision_made|LLM Adapter"
```

**Qué buscar**:
- ✅ `message_received` → Confirma que el mensaje se recibió
- ✅ `llm_decision_made` → Confirma que se decidió usar OpenAI (si aplica)
- ✅ `LLM Adapter usado exitosamente` → Confirma que OpenAI respondió correctamente

---

## 📋 Checklist de Activación

- [ ] `.env` actualizado con `OPENAI_API_KEY` real
- [ ] Backend reiniciado
- [ ] Health check responde OK
- [ ] Variables verificadas en contenedor/proceso
- [ ] Webhook responde correctamente (no 404)
- [ ] Logs muestran que WhatsApp está habilitado
- [ ] Mensaje de prueba se procesa correctamente

---

## 🧪 Ejecutar Pruebas Completas

Una vez activado todo, ejecutar el script de pruebas:

```bash
cd /Users/camilope/AI-Agents/Sastre
python3 backend/scripts/test_activacion_openai.py http://localhost:8000/whatsapp/webhook
```

Este script ejecutará los 8 mensajes del plan de pruebas y generará un reporte completo.

---

## 🔍 Diagnóstico de Problemas

### Problema: "OPENAI_API_KEY está vacío"
**Causa**: El `.env` no tiene una API key válida  
**Solución**: Editar `.env` y agregar tu API key real

### Problema: Webhook responde 404
**Causa**: `WHATSAPP_ENABLED=false` o router no montado  
**Solución**: Verificar que `.env` tiene `WHATSAPP_ENABLED=true` y reiniciar backend

### Problema: "LLM Adapter falló completamente"
**Causa**: API key inválida o OpenAI no disponible  
**Solución**: Verificar API key, verificar conectividad a OpenAI, revisar logs

### Problema: "Límite de llamadas excedido"
**Causa**: Normal después de 4 llamadas por conversación  
**Solución**: Esperar 24 horas o cambiar `OPENAI_CONVERSATION_TTL_HOURS` en `.env`

---

## 📊 Configuración Recomendada para Pruebas Reales

```bash
# .env
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-tu-key-real
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=150
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_CALLS_PER_CONVERSATION=4
OPENAI_CONVERSATION_TTL_HOURS=24

WHATSAPP_ENABLED=true
WHATSAPP_VERIFY_TOKEN=tu-verify-token-real
WHATSAPP_ACCESS_TOKEN=tu-access-token-real
WHATSAPP_PHONE_NUMBER_ID=tu-phone-number-id-real

PRODUCTION_MODE=true
LOG_FORMAT=json
LOG_LEVEL=INFO
```

---

**Última actualización**: 2026-01-07  
**Estado**: ⚠️ Requiere agregar `OPENAI_API_KEY` real antes de pruebas

