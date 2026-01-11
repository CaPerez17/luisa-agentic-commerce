# Reporte de Pruebas - Activación OpenAI en Producción

**Fecha**: 2026-01-07 19:45:23  
**Webhook URL**: http://localhost:8000/whatsapp/webhook  
**Estado**: ⚠️ **Pruebas ejecutadas, requiere diagnóstico**

---

## Resumen Ejecutivo

- **Total de pruebas**: 8
- **Pruebas exitosas**: 0
- **Pruebas con problemas**: 8
- **Tasa de éxito**: 0%

### Problema Principal

El webhook está respondiendo **HTTP 404 (Not Found)**, lo que significa que **la ruta `/whatsapp/webhook` no existe o no está habilitada**.

**Causa raíz identificada**: `WHATSAPP_ENABLED=false` en `.env` hace que el router de WhatsApp no se monte en la aplicación FastAPI (línea 48-49 en `main.py`).

Todos los mensajes de prueba fallaron con:
- ❌ Webhook responde HTTP 404 (Not Found)
- ✅ Tiempo de respuesta < 2s
- ❌ Los logs esperados no aparecen (webhook no existe)

---

## Detalles por Prueba

### Prueba 1: Saludo
**Mensaje**: "Hola"

**Resultado**:
- ✅ Webhook responde (17.1ms)
- ❌ Logs faltantes: `message_received`, `Mensaje WhatsApp procesado y respondido`
- ✅ OpenAI NO usado (correcto para saludo)
- ⚠️ Intent no detectado

**Diagnóstico**: El mensaje se encoló pero no se procesó en background.

---

### Prueba 2: Intención Clara (Máquina Industrial)
**Mensaje**: "Quiero una máquina industrial para gorras"

**Resultado**:
- ✅ Webhook responde (20.0ms)
- ❌ Logs faltantes: `message_received`, `Mensaje WhatsApp procesado y respondido`
- ⚠️ Intent no detectado

**Diagnóstico**: Mismo problema que Prueba 1.

---

### Prueba 3: Objeción de Precio (DEBE usar OpenAI)
**Mensaje**: "Está muy caro, no tengo ese presupuesto"

**Resultado**:
- ✅ Webhook responde (21.5ms)
- ❌ Logs faltantes: `message_received`, `llm_decision_made`, `LLM Adapter usado exitosamente`
- ❌ OpenAI NO usado (debería usarse para objeciones)
- ⚠️ Task type no encontrado

**Diagnóstico**: El mensaje no se procesó, por lo que OpenAI nunca se llamó.

**Nota**: OpenAI está deshabilitado en `.env` (`OPENAI_ENABLED=false`), lo que podría ser la causa si el mensaje se procesara.

---

### Prueba 4: Pregunta Ambigua (DEBE usar OpenAI)
**Mensaje**: "No sé qué máquina me conviene"

**Resultado**:
- ✅ Webhook responde (20.0ms)
- ❌ Logs faltantes: `message_received`, `llm_decision_made`, `LLM Adapter usado exitosamente`
- ❌ OpenAI NO usado (debería usarse para consultas complejas)
- ⚠️ Task type no encontrado

**Diagnóstico**: Mismo problema que Prueba 3.

---

### Prueba 5: Caso Técnico (Ruido, Hilo se Rompe)
**Mensaje**: "Mi máquina hace mucho ruido y el hilo se rompe constantemente"

**Resultado**:
- ✅ Webhook responde (29.1ms)
- ❌ Logs faltantes: `message_received`, `Mensaje WhatsApp procesado y respondido`
- ✅ OpenAI NO usado (correcto para casos técnicos)
- ⚠️ Intent no detectado

**Diagnóstico**: Mismo problema que Prueba 1.

---

### Prueba 6: Handoff "Sí" (FIX P0 - nunca silencio)
**Mensaje**: "Sí, llámenme"

**Resultado**:
- ✅ Webhook responde (20.2ms)
- ❌ Logs faltantes: `message_received`, `Mensaje registrado en modo HUMAN_ACTIVE`, `reply_sent_in_human_active`
- ✅ OpenAI NO usado (correcto para HUMAN_ACTIVE)

**Diagnóstico**: Este mensaje requiere que haya un handoff previo (modo HUMAN_ACTIVE). Sin handoff previo, no puede validarse correctamente.

**Nota**: Esta prueba requiere contexto previo (handoff activado en mensaje anterior).

---

### Prueba 7: Follow-up "Hola" Después de Handoff
**Mensaje**: "Hola"

**Resultado**:
- ✅ Webhook responde (20.9ms)
- ❌ Logs faltantes: `message_received`, `Mensaje registrado en modo HUMAN_ACTIVE`, `reply_sent_in_human_active`
- ✅ OpenAI NO usado (correcto para HUMAN_ACTIVE)

**Diagnóstico**: Este mensaje requiere estar en modo HUMAN_ACTIVE (del mensaje 6). Sin contexto previo, no puede validarse.

---

### Prueba 8: Prueba de Fallback (Límite Excedido)
**Mensaje**: "Tengo otra objeción sobre el precio"

**Resultado**:
- ✅ Webhook responde (21.0ms)
- ❌ Logs faltantes: `message_received`, `llm_decision_made`, `LLM Adapter: Límite de llamadas excedido`
- ✅ OpenAI NO usado (correcto si fallback funciona)

**Diagnóstico**: Esta prueba requiere 4 llamadas previas a OpenAI. Sin llamadas previas, no puede validarse.

---

## Problemas Identificados

### Problema 1: Mensajes no se procesan en background
**Síntoma**: Webhook responde HTTP 200, pero los logs esperados no aparecen.

**Causa raíz**: `WHATSAPP_ENABLED=false` en `.env` hace que el router de WhatsApp no se monte (código en `main.py:48-49`).

**Solución**: Cambiar `WHATSAPP_ENABLED=true` en `.env` y reiniciar el backend.

---

### Problema 2: OpenAI deshabilitado
**Síntoma**: `OPENAI_ENABLED=false` en `.env`.

**Impacto**: Las pruebas 3 y 4 (objeciones y consultas complejas) nunca usarán OpenAI, incluso si los mensajes se procesaran.

**Recomendación**: Habilitar OpenAI para pruebas reales (`OPENAI_ENABLED=true` y `OPENAI_API_KEY` válido).

---

### Problema 3: Pruebas que requieren contexto previo
**Pruebas afectadas**: 6, 7, 8

**Problema**: Estas pruebas requieren estado conversacional previo (HUMAN_ACTIVE, llamadas OpenAI previas) que no existe si las pruebas anteriores fallaron.

**Recomendación**: Ejecutar estas pruebas en una conversación real donde el contexto ya existe, o crear un script que establezca el contexto necesario antes de ejecutar la prueba.

---

## Recomendaciones

### 1. Diagnóstico Inmediato

```bash
# Ver logs completos del backend en tiempo real
cd /Users/camilope/AI-Agents/Sastre
docker compose logs -f backend

# En otra terminal, enviar un mensaje de prueba
curl -X POST http://localhost:8000/whatsapp/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "573142156486",
            "id": "wamid.test_debug",
            "type": "text",
            "text": {"body": "Hola"}
          }]
        }
      }]
    }]
  }'

# Observar los logs en la primera terminal
```

**Qué buscar en los logs**:
- `Mensaje WhatsApp recibido (queued)` → Confirma que el webhook recibió el mensaje
- `message_received` → Confirma que el procesamiento comenzó
- `Mensaje WhatsApp procesado y respondido` → Confirma que el procesamiento terminó
- `ERROR` o `Error` → Indica errores que impiden el procesamiento

---

### 2. Habilitar OpenAI para Pruebas

```bash
# Editar .env
cd /Users/camilope/AI-Agents/Sastre
nano .env

# Cambiar:
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-tu-key-real-aqui

# Reiniciar backend
docker compose restart backend
```

---

### 3. Ejecutar Pruebas con Contexto

Para las pruebas 6, 7, 8 que requieren contexto previo:

**Opción A**: Ejecutar en una conversación real de WhatsApp donde ya existe el contexto.

**Opción B**: Crear un script que establezca el contexto antes de ejecutar la prueba:

```python
# Establecer modo HUMAN_ACTIVE para prueba 6
set_conversation_mode("wa_573142156486", "HUMAN_ACTIVE")

# O hacer 4 llamadas a OpenAI antes de prueba 8
for i in range(4):
    send_test_message("Está muy caro")
    time.sleep(2)
```

---

## Próximos Pasos

1. ✅ **Diagnóstico completo**: Revisar logs completos del backend mientras se envía un mensaje
2. ⏳ **Habilitar OpenAI**: Configurar `OPENAI_ENABLED=true` y `OPENAI_API_KEY` válido
3. ⏳ **Ejecutar pruebas con contexto**: Crear contexto necesario para pruebas 6, 7, 8
4. ⏳ **Re-ejecutar suite completa**: Ejecutar todas las pruebas nuevamente después de corregir problemas

---

## Archivos Generados

- `reporte_pruebas_openai_1767833149.json`: Reporte JSON completo con todos los detalles
- `REPORTE_PRUEBAS_OPENAI.md`: Este reporte en Markdown

---

**Última actualización**: 2026-01-07 19:45:23  
**Estado**: ⚠️ Requiere diagnóstico adicional

