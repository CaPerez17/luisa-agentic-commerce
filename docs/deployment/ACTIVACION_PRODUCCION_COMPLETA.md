# Activación Completa para Producción - LUISA

**Fecha**: 2026-01-07  
**Dominio**: https://luisa-agent.online  
**Infraestructura**: AWS Lightsail + Docker Compose + Caddy

---

## 🎯 Objetivo

Activar completamente LUISA en producción con:
- ✅ WhatsApp habilitado
- ✅ OpenAI habilitado (con límites)
- ✅ Todos los fixes aplicados (P0, P1, observabilidad)
- ✅ Logs y monitoreo configurados

---

## 📋 Checklist Pre-Activación

- [ ] API Key de OpenAI lista
- [ ] WhatsApp Access Token configurado en Meta
- [ ] WhatsApp Phone Number ID configurado
- [ ] WhatsApp Verify Token configurado
- [ ] Acceso SSH al servidor de producción
- [ ] Archivo `.env` preparado con todas las variables

---

## 🔧 Paso 1: Preparar Archivo `.env` para Producción

Crea o actualiza el archivo `.env` en tu máquina local con esta configuración:

```bash
# ============================================================================
# WHATSAPP CONFIGURATION
# ============================================================================
WHATSAPP_ENABLED=true
WHATSAPP_VERIFY_TOKEN=tu-verify-token-real-aqui
WHATSAPP_ACCESS_TOKEN=tu-access-token-real-aqui
WHATSAPP_PHONE_NUMBER_ID=tu-phone-number-id-real-aqui

# ============================================================================
# OPENAI CONFIGURATION - ACTIVADO PARA PRUEBAS REALES
# ============================================================================
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-tu-api-key-real-aqui
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=150
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_CALLS_PER_CONVERSATION=4
OPENAI_CONVERSATION_TTL_HOURS=24

# ============================================================================
# PRODUCTION MODE
# ============================================================================
PRODUCTION_MODE=true
LOG_FORMAT=json
LOG_LEVEL=INFO

# ============================================================================
# DATABASE
# ============================================================================
DB_PATH=/app/data/luisa.db

# ============================================================================
# BUSINESS CONFIGURATION (opcional, usar defaults si no especificas)
# ============================================================================
BUSINESS_NAME=Almacén y Taller El Sastre
BUSINESS_LOCATION=Calle 34 #1-30, Montería, Córdoba, Colombia
BUSINESS_HOURS=Lunes a viernes 9am-6pm, sábados 9am-2pm
BUSINESS_PHONE=+573142156486
```

**⚠️ IMPORTANTE**: Reemplaza TODOS los valores `tu-xxx-real-aqui` con tus valores reales.

---

## 🚀 Paso 2: Desplegar a Producción

### Opción A: Script Automatizado (Recomendado)

```bash
# 1. Conectarse al servidor
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

# 2. Ir al directorio de la app
cd /opt/luisa

# 3. Hacer pull del código más reciente
git pull origin main

# 4. Copiar .env al servidor (desde tu máquina local)
# En tu máquina local:
scp -i ~/.ssh/luisa-lightsail.pem .env ubuntu@44.215.107.112:/opt/luisa/.env

# 5. Desplegar
sudo ./deploy.sh
```

### Opción B: Manual (si prefieres control total)

```bash
# 1. Conectarse al servidor
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

# 2. Ir al directorio
cd /opt/luisa

# 3. Actualizar código
git pull origin main

# 4. Copiar .env (si no lo hiciste antes)
# Desde tu máquina local:
scp -i ~/.ssh/luisa-lightsail.pem .env ubuntu@44.215.107.112:/opt/luisa/.env

# 5. Verificar que .env existe y tiene las variables correctas
cat .env | grep -E "OPENAI_ENABLED|WHATSAPP_ENABLED|OPENAI_API_KEY" | head -5

# 6. Detener servicios actuales
sudo docker compose down

# 7. Construir imagen del backend
sudo docker compose build backend

# 8. Levantar servicios
sudo docker compose up -d

# 9. Esperar a que estén listos (hasta 90 segundos)
timeout 90 bash -c 'until curl -sf http://localhost:8000/health > /dev/null; do sleep 5; done'

# 10. Verificar estado
sudo docker compose ps
```

---

## ✅ Paso 3: Verificar Activación

### 3.1 Health Check Público

```bash
# Desde tu máquina local
curl -s https://luisa-agent.online/health | python3 -m json.tool
```

**Salida esperada**:
```json
{
  "status": "healthy",
  "service": "luisa",
  "version": "2.0.0",
  "modules": {
    "whatsapp": true,  ← Debe ser true
    "openai": true,    ← Debe ser true
    ...
  }
}
```

### 3.2 Verificar Variables en Contenedor

```bash
# En el servidor
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

cd /opt/luisa
sudo docker exec luisa-backend python3 -c "
from app.config import (
    OPENAI_ENABLED, 
    OPENAI_MAX_CALLS_PER_CONVERSATION,
    WHATSAPP_ENABLED
)
print(f'OPENAI_ENABLED={OPENAI_ENABLED}')
print(f'MAX_CALLS={OPENAI_MAX_CALLS_PER_CONVERSATION}')
print(f'WHATSAPP_ENABLED={WHATSAPP_ENABLED}')
"
```

**Salida esperada**:
```
OPENAI_ENABLED=True
MAX_CALLS=4
WHATSAPP_ENABLED=True
```

### 3.3 Verificar Logs de Inicio

```bash
# En el servidor
sudo docker compose logs backend | grep -iE "openai|whatsapp|error|warning" | tail -20
```

**Qué buscar**:
- ✅ No debe aparecer: `"OPENAI_ENABLED=true pero OPENAI_API_KEY está vacío"`
- ✅ Debe aparecer: `"WhatsApp webhook habilitado"`
- ✅ No debe haber errores críticos

### 3.4 Probar Webhook de WhatsApp

```bash
# Desde tu máquina local
curl -X POST https://luisa-agent.online/whatsapp/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "573142156486",
            "id": "wamid.test_produccion",
            "type": "text",
            "text": {"body": "Hola"}
          }]
        }
      }]
    }]
  }'
```

**Salida esperada**: `{"status": "ok", "queued": true}`

---

## 📊 Paso 4: Ejecutar Pruebas en Producción

### 4.1 Script de Pruebas Automatizado

```bash
# Desde tu máquina local
cd /Users/camilope/AI-Agents/Sastre

# Actualizar script para usar producción
python3 backend/scripts/test_activacion_openai.py https://luisa-agent.online/whatsapp/webhook
```

Este script ejecutará los 8 mensajes del plan de pruebas y generará un reporte.

### 4.2 Monitorear Logs en Tiempo Real

```bash
# En el servidor (en una terminal)
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

cd /opt/luisa
sudo docker compose logs -f backend | grep -E "message_received|llm_decision_made|LLM Adapter|reply_sent_in_human_active"
```

Mientras las pruebas se ejecutan, deberías ver:
- `message_received` → Mensaje recibido
- `llm_decision_made` → Decisión de usar OpenAI
- `LLM Adapter usado exitosamente` → OpenAI respondió
- `reply_sent_in_human_active` → Respuesta en modo HUMAN_ACTIVE

---

## 🔍 Paso 5: Verificar Configuración de Meta

### 5.1 Webhook URL en Meta

La URL del webhook debe ser exactamente:
```
https://luisa-agent.online/whatsapp/webhook
```

**Verificar en Meta Business Suite**:
1. Ir a https://business.facebook.com
2. Configuración → WhatsApp → Configuración
3. Verificar que "Webhook URL" = `https://luisa-agent.online/whatsapp/webhook`
4. Verificar que "Verify Token" coincide con `WHATSAPP_VERIFY_TOKEN` en `.env`

### 5.2 Probar Verificación de Webhook

```bash
# Reemplaza YOUR_VERIFY_TOKEN con el valor real de tu .env
curl -v "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=test123"
```

**Salida esperada**: Debe responder `test123` (el challenge) si el token coincide.

---

## 🎯 Paso 6: Pruebas Manuales desde WhatsApp Real

Una vez activado todo, prueba desde WhatsApp real:

### Mensaje 1: Saludo
**Envías**: `Hola`  
**Esperas**: Saludo + pregunta de triage  
**Verifica en logs**: `message_received`, `intent=saludo`, `openai_used=false`

### Mensaje 2: Intención Clara
**Envías**: `Quiero una máquina industrial para gorras`  
**Esperas**: Recomendación con producto y precio  
**Verifica en logs**: `intent=buscar_maquina_industrial`

### Mensaje 3: Objeción (DEBE usar OpenAI)
**Envías**: `Está muy caro, no tengo ese presupuesto`  
**Esperas**: Respuesta empática con alternativas  
**Verifica en logs**: `llm_decision_made`, `task_type=objecion`, `LLM Adapter usado exitosamente`, `openai_call_count=1`

### Mensaje 4: Consulta Compleja (DEBE usar OpenAI)
**Envías**: `No sé qué máquina me conviene`  
**Esperas**: Respuesta estructurada con preguntas  
**Verifica en logs**: `llm_decision_made`, `task_type=consulta_compleja`, `openai_call_count=2`

---

## 🐛 Diagnóstico de Problemas

### Problema: Health check muestra `whatsapp: false` o `openai: false`

**Causa**: Variables no cargadas correctamente  
**Solución**:
```bash
# Verificar que .env existe y tiene las variables
cat .env | grep -E "OPENAI_ENABLED|WHATSAPP_ENABLED"

# Reiniciar backend
sudo docker compose restart backend

# Verificar logs
sudo docker compose logs backend | grep -i "whatsapp\|openai" | tail -10
```

### Problema: Webhook responde 404

**Causa**: Router de WhatsApp no montado  
**Solución**:
```bash
# Verificar que WHATSAPP_ENABLED=true en .env
# Reiniciar backend
sudo docker compose restart backend

# Verificar logs de inicio
sudo docker compose logs backend | grep "WhatsApp webhook"
```

### Problema: "OPENAI_API_KEY está vacío"

**Causa**: API key no está en .env o es inválida  
**Solución**:
```bash
# Verificar .env
cat .env | grep OPENAI_API_KEY

# Si está vacío o es placeholder, editar:
nano .env
# Cambiar: OPENAI_API_KEY=sk-tu-key-real

# Reiniciar backend
sudo docker compose restart backend
```

### Problema: "LLM Adapter falló completamente"

**Causa**: API key inválida o OpenAI no disponible  
**Solución**:
```bash
# Verificar logs de error
sudo docker compose logs backend | grep -i "openai\|error" | tail -20

# Verificar API key en .env
cat .env | grep OPENAI_API_KEY

# Probar conectividad a OpenAI (desde el contenedor)
sudo docker exec luisa-backend curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $(cat .env | grep OPENAI_API_KEY | cut -d'=' -f2)" | head -5
```

---

## 📈 Monitoreo Continuo

### Ver logs en tiempo real

```bash
# Todos los logs
sudo docker compose logs -f backend

# Solo logs importantes
sudo docker compose logs -f backend | grep -E "message_received|llm_decision_made|LLM Adapter|ERROR|Error"
```

### Verificar uso de OpenAI

```bash
# Ver llamadas a OpenAI en los últimos minutos
sudo docker compose logs backend | grep "LLM Adapter usado exitosamente" | tail -10

# Ver límites excedidos
sudo docker compose logs backend | grep "Límite de llamadas excedido"
```

### Verificar estado de servicios

```bash
# Estado de contenedores
sudo docker compose ps

# Uso de recursos
sudo docker stats --no-stream
```

---

## ✅ Checklist Final de Activación

- [ ] `.env` configurado con todas las variables reales
- [ ] `.env` copiado al servidor (`/opt/luisa/.env`)
- [ ] Código actualizado en servidor (`git pull`)
- [ ] Backend desplegado (`sudo ./deploy.sh`)
- [ ] Health check público responde OK
- [ ] Variables verificadas en contenedor (OPENAI_ENABLED=True, WHATSAPP_ENABLED=True)
- [ ] Logs de inicio sin errores críticos
- [ ] Webhook responde correctamente (no 404)
- [ ] Prueba de mensaje funciona desde WhatsApp real
- [ ] Logs muestran `message_received` y procesamiento correcto
- [ ] OpenAI funciona (en objeciones/consultas complejas)

---

## 🎉 Activación Completa

Una vez completado todo el checklist, LUISA está completamente activada en producción y lista para:

✅ Recibir mensajes de WhatsApp reales  
✅ Usar OpenAI para objeciones y consultas complejas  
✅ Manejar handoffs correctamente  
✅ Nunca quedarse muda (FIX P0)  
✅ Revertir HUMAN_ACTIVE automáticamente (FIX P1)  
✅ Generar logs completos para diagnóstico  

---

**Última actualización**: 2026-01-07  
**Estado**: 🚀 Listo para activación en producción

