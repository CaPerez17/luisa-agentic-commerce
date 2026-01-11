# Guía de Despliegue y Configuración - LUISA

**Documentación consolidada para despliegue, configuración y activación en producción**

---

## Tabla de Contenidos

1. [Despliegue en Producción](#despliegue-en-producción)
2. [Configuración de OpenAI](#configuración-de-openai)
3. [Checklist GO/NO-GO](#checklist-gono-go)
4. [Activación Completa](#activación-completa)

---

## Despliegue en Producción

### Quick Start con Docker

```bash
# 1. Clonar repositorio
git clone <repository-url>
cd Sastre

# 2. Configurar .env
cp .env.example .env
# Editar .env con tus valores reales

# 3. Desplegar
docker compose up -d
```

### Variables de Entorno Requeridas

#### WhatsApp (Requerido)
```bash
WHATSAPP_ENABLED=true
WHATSAPP_VERIFY_TOKEN=tu-verify-token-real
WHATSAPP_ACCESS_TOKEN=tu-access-token-real
WHATSAPP_PHONE_NUMBER_ID=tu-phone-number-id-real
```

#### OpenAI (Opcional para producción)
```bash
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-tu-api-key-real
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=150
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_CALLS_PER_CONVERSATION=4
OPENAI_CONVERSATION_TTL_HOURS=24
```

#### Producción
```bash
PRODUCTION_MODE=true
LOG_FORMAT=json
LOG_LEVEL=INFO
```

Ver [DEPLOYMENT.md](DEPLOYMENT.md) para detalles completos.

---

## Configuración de OpenAI

### Configuración Recomendada para Producción

```bash
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-tu-key-real
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=150
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_CALLS_PER_CONVERSATION=4
OPENAI_CONVERSATION_TTL_HOURS=24
```

### ¿Qué Casos Disparan OpenAI?

**✅ Casos que SÍ usan OpenAI:**
- Objeciones de precio ("Está muy caro")
- Consultas complejas ("No sé qué máquina me conviene")
- Explicaciones técnicas (comparaciones, diferencias)
- Redacción comercial (cuando hay contexto completo)

**❌ Casos que NO usan OpenAI:**
- FAQs simples (horarios, dirección)
- Saludos/despedidas
- Mensajes off-topic
- Cache hits
- Respuestas determinísticas robustas disponibles

### Control de Costos

- **Límite por conversación**: 4 llamadas máximo
- **TTL de reset**: 24 horas (contador se resetea automáticamente)
- **Timeout duro**: 5 segundos (fallback garantizado)
- **Costo estimado**: ~$0.16-0.32 por conversación (máximo)

---

## Checklist GO/NO-GO

### Infraestructura ⚠️

- [ ] Contenedores corriendo (`docker compose ps`)
- [ ] Health check OK (`curl https://luisa-agent.online/health`)
- [ ] HTTPS válido (certificado no expirado)
- [ ] Base de datos accesible
- [ ] Recursos suficientes (memoria, disco)

### WhatsApp ⚠️

- [ ] `WHATSAPP_ENABLED=true` en `.env`
- [ ] Tokens configurados (ACCESS_TOKEN, VERIFY_TOKEN, PHONE_NUMBER_ID)
- [ ] Webhook URL correcta en Meta Dashboard
- [ ] GET verification funciona
- [ ] POST de mensajes funciona
- [ ] No hay errores 4xx/5xx

### OpenAI ⚠️ (si habilitado)

- [ ] `OPENAI_API_KEY` configurado y válido
- [ ] Límites configurados correctamente
- [ ] OpenAI responde sin errores
- [ ] Fallback funciona si OpenAI falla
- [ ] Tracking de llamadas funciona

### Logs ⚠️

- [ ] `PRODUCTION_MODE=true`
- [ ] `LOG_FORMAT=json`
- [ ] Logs estructurados presentes
- [ ] Sin errores críticos en logs
- [ ] Secrets no expuestos

**Decisión**: ✅ GO si todos los checks críticos pasan + máx 2 warnings

Ver [CHECKLIST_GO_NO_GO_PRODUCCION.md](CHECKLIST_GO_NO_GO_PRODUCCION.md) para checklist completo.

---

## Activación Completa

### Paso 1: Preparar `.env`

Configurar todas las variables requeridas (ver sección "Variables de Entorno Requeridas").

### Paso 2: Desplegar

```bash
# Opción A: Script automatizado
./deploy.sh

# Opción B: Manual
docker compose down
docker compose build backend
docker compose up -d
```

### Paso 3: Verificar

```bash
# Health check
curl -s https://luisa-agent.online/health | jq

# Verificar variables en contenedor
docker exec luisa-backend python3 -c "
from app.config import OPENAI_ENABLED, WHATSAPP_ENABLED
print(f'OPENAI_ENABLED={OPENAI_ENABLED}')
print(f'WHATSAPP_ENABLED={WHATSAPP_ENABLED}')
"

# Verificar logs
docker compose logs backend | tail -50
```

### Paso 4: Probar Webhook

```bash
curl -X POST https://luisa-agent.online/whatsapp/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "573142156486",
            "id": "wamid.test",
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

## Diagnóstico de Problemas Comunes

### Problema: Webhook responde 404

**Causa**: `WHATSAPP_ENABLED=false` o router no montado  
**Solución**: Verificar `.env` tiene `WHATSAPP_ENABLED=true` y reiniciar backend

### Problema: Health check muestra `openai: false`

**Causa**: `OPENAI_ENABLED=false` o `OPENAI_API_KEY` vacío  
**Solución**: Verificar `.env` y reiniciar backend

### Problema: "LLM Adapter falló completamente"

**Causa**: API key inválida o OpenAI no disponible  
**Solución**: Verificar API key, revisar logs, verificar conectividad

### Problema: "Límite de llamadas excedido"

**Causa**: Normal después de 4 llamadas por conversación  
**Solución**: Esperar 24 horas o cambiar `OPENAI_CONVERSATION_TTL_HOURS`

---

**Última actualización**: 2026-01-09  
**Estado**: Documentación consolidada y actualizada
