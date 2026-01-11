# Guía de Desarrollo y Testing - LUISA

**Documentación consolidada para desarrollo, implementación, diseño y pruebas**

---

## Tabla de Contenidos

1. [Arquitectura y Diseño](#arquitectura-y-diseño)
2. [Implementación de Features](#implementación-de-features)
3. [Copy y UX](#copy-y-ux)
4. [Testing y Observabilidad](#testing-y-observabilidad)

---

## Arquitectura y Diseño

### Enfoque Híbrido: Heurísticas + OpenAI

LUISA combina **heurísticas determinísticas** (70% de casos) con **OpenAI** (30% de casos complejos).

**Filosofía**: "OpenAI solo cuando aporta valor real"

#### Distribución de Casos

- **Categoría A (70%)**: Heurísticas puras - FAQs, datos duros, confirmaciones simples
- **Categoría B (15%)**: Heurísticas + LLM Copy - Redacción comercial natural
- **Categoría C (15%)**: LLM Razonamiento - Casos complejos, objeciones, ambigüedad

#### LLM Adapter: Diseño y Principios

**Reglas de Oro:**
1. OpenAI NO decide estados (solo genera texto)
2. OpenAI NO hace handoff
3. OpenAI NO responde solo (siempre devuelve `suggested_reply`)
4. OpenAI solo devuelve TEXTO (string puro)

**Separación de Responsabilidades:**
- **Heurísticas**: Deciden QUÉ decir, CUÁNDO usar OpenAI, estados
- **LLM Adapter**: Solo genera texto sugerido
- **Heurísticas (post)**: Validan respuesta, aseguran pregunta cerrada

**Timeout duro**: 5 segundos (fallback garantizado si falla)

Ver [DISEÑO_LLM_ADAPTER.md](DISEÑO_LLM_ADAPTER.md) y [ANALISIS_OPENAI_VS_HEURISTICAS.md](ANALISIS_OPENAI_VS_HEURISTICAS.md) para detalles completos.

---

## Implementación de Features

### Límites de OpenAI por Conversación

**Funcionalidad:**
- Máximo de llamadas por conversación (default: 4)
- Reset automático por TTL (default: 24 horas)
- Tracking en base de datos
- Fallback automático si límite excedido

**Implementación:**
- Columnas en `conversations`: `openai_calls_count`, `first_openai_call_at`, `last_openai_call_at`
- Funciones en `database.py`: `get_openai_call_count()`, `increment_openai_call_count()`, `reset_openai_call_count_if_expired()`
- Verificación en `llm_adapter.py` antes de llamar OpenAI

Ver [IMPLEMENTACION_LIMITES_OPENAI.md](IMPLEMENTACION_LIMITES_OPENAI.md) para detalles técnicos.

### Variantes de Copy

**Funcionalidad:**
- Variaciones determinísticas de mensajes críticos (saludo, triage, HUMAN_ACTIVE, handoff)
- Selección por `hash(conversation_id) % len(variantes)`
- Misma conversación = misma variante (determinístico)

**Mensajes con variantes:**
1. Saludo inicial (2 variantes)
2. Triage primer turno (2 variantes)
3. Triage 2+ turnos (2 variantes)
4. HUMAN_ACTIVE follow-up (2 variantes)
5. Handoff "te llamamos o pasas" (2 variantes para Montería)
6. Handoff "te llamamos o vayamos" (2 variantes para fuera)

**Implementación:**
- Constantes en `keywords.py`: `SALUDO_VARIANTES`, `TRIAGE_FIRST_VARIANTES`, etc.
- Función helper: `select_variant(conversation_id, variants)`
- Integración en servicios relevantes

Ver [IMPLEMENTACION_VARIANTES_COPY.md](IMPLEMENTACION_VARIANTES_COPY.md) para detalles técnicos.

### LLM Adapter

**Funcionalidad:**
- Módulo independiente para interacción con OpenAI
- Task types: COPY, EXPLICACION, OBJECION, CONSULTA_COMPLEJA
- Fallback garantizado en todos los casos
- Validación de respuestas (no vacía, no menciona ser IA)

**Implementación:**
- Archivo: `backend/app/services/llm_adapter.py`
- Función principal: `get_llm_suggestion_sync()`
- Integración en `response_service.py`

Ver [IMPLEMENTACION_LLM_ADAPTER.md](IMPLEMENTACION_LLM_ADAPTER.md) y [DISEÑO_LLM_ADAPTER.md](DISEÑO_LLM_ADAPTER.md) para detalles.

---

## Copy y UX

### Principios del Copy

- ✅ **Sonar humano**: Lenguaje natural, cálido, colombiano
- ✅ **Claridad**: Directo, sin rodeos
- ✅ **Guía a venta/visita**: Preguntas cerradas que avancen el funnel
- ✅ **No invasivo**: Respetuoso, sin presión
- ✅ **Corto**: Máximo 2-3 líneas (WhatsApp)
- ✅ **Preguntas cerradas**: Opciones claras (máx 2-3)

### Mensajes Refinados

Todos los mensajes fueron refinados para ser más cortos, naturales y efectivos:

- **Saludo inicial**: 2 líneas, pregunta cerrada directa
- **HUMAN_ACTIVE follow-up**: 2 líneas, pregunta cerrada
- **Handoff mensajes**: 2 líneas, opciones claras
- **Triage**: 1-2 líneas según turno

Ver [COPY_LUISA_WHATSAPP.md](COPY_LUISA_WHATSAPP.md) para lista completa de mensajes.

---

## Testing y Observabilidad

### Plan de Pruebas Manuales

**8 Escenarios de Prueba:**

1. **Saludo + Triage**: Validar saludo inicial y respuesta a mensajes ambiguos
2. **Recomendación de Producto**: Validar recomendación con contexto
3. **Objeción de Precio**: Validar uso de OpenAI para objeciones
4. **Pregunta Ambigua**: Validar uso de OpenAI para consultas complejas
5. **Caso Técnico**: Validar handoff y respuestas técnicas
6. **Handoff + No Silencio**: Validar que LUISA nunca se queda muda
7. **Follow-up en HUMAN_ACTIVE**: Validar respuesta en modo HUMAN_ACTIVE
8. **Prueba de Fallback**: Validar límites y fallback

Cada escenario incluye:
- Mensaje a enviar
- Respuesta esperada
- Logs esperados (event_name)
- Validaciones a realizar

Ver [PLAN_PRUEBA_MANUAL_WHATSAPP.md](PLAN_PRUEBA_MANUAL_WHATSAPP.md) para detalles completos.

### Observabilidad Mínima

**Logs Críticos:**

1. **`message_received`**: Mensaje entrante con `conversation_id`, `message_id`, `phone` (last4), `mode`, `intent`
2. **`llm_decision_made`**: Decisión de usar OpenAI con `task_type`, `reason_for_llm_use`
3. **`human_active_triggered`**: Activación de HUMAN_ACTIVE con `reason`, `priority`, `team`
4. **`Mensaje WhatsApp enviado`**: Éxito/fallo de envío con error sanitizado

**Campos en Logs:**
- `conversation_id` (siempre)
- `message_id` (truncado a 20 chars)
- `phone` (últimos 4 dígitos)
- `intent`, `mode`, `task_type`, `decision_path`
- `openai_used` (bool)

Ver [MINIMUM_OBSERVABILITY_PACK.md](MINIMUM_OBSERVABILITY_PACK.md) para detalles completos.

### Checklist Demo-Proof

**Puntos Críticos (P0 - Silencio Total):**
- Verificar que `WHATSAPP_ENABLED=true`
- Verificar deduplicación de mensajes
- Verificar rate limiting
- Verificar que `send_whatsapp_message` siempre loguea éxito/fallo
- Verificar configuración de WhatsApp

**Puntos P1 (Copy Repetido):**
- Saludo inicial con variación
- HUMAN_ACTIVE con variación
- Handoff con variación
- Triage con variación

Ver [CHECKLIST_DEMO_PROOF_WHATSAPP.md](CHECKLIST_DEMO_PROOF_WHATSAPP.md) para checklist completo.

---

## Decision Matrix: OpenAI vs Heurísticas

### ¿Cuándo Usar Cada Enfoque?

| Categoría | Tipo | % | OpenAI | Función de OpenAI |
|-----------|------|---|--------|-------------------|
| **A) Heurística Pura** | FAQs, Datos duros, Confirmaciones | 70% | ❌ NO | - |
| **B) Heurística + Copy** | Recomendaciones, Comparaciones | 15% | ✅ SÍ | Solo redacción |
| **C) LLM Razonamiento** | Ambiguos, Objeciones, Complejos | 15% | ✅ SÍ | Clasificación + Planeación + Redacción |

### Criterios de Decisión

**Usar Heurísticas si:**
- Intent claro y determinístico
- Respuesta requiere solo datos duros
- Existe regla predefinida

**Usar OpenAI Copy si:**
- Heurísticas determinan QUÉ decir
- Se necesita redacción natural
- Contenido estructurado pero personalizado

**Usar OpenAI Reasoning si:**
- Mensaje ambiguo o complejo
- Requiere razonamiento sobre alternativas
- Involucra objeciones o estados emocionales

Ver [DECISION_MATRIX_OPENAI_HEURISTICAS.md](DECISION_MATRIX_OPENAI_HEURISTICAS.md) para matriz completa.

---

## Flujos Críticos

### Flujo 1: Nuevo Usuario → Saludo

```
Mensaje "Hola"
  ↓
Intent: saludo
  ↓
Respuesta: Saludo con variación determinística
  ↓
Pregunta cerrada: ¿Buscas máquina familiar, industrial o repuesto?
```

### Flujo 2: Objeción → OpenAI

```
Mensaje "Está muy caro"
  ↓
Detecta objeción (keywords)
  ↓
Decide usar OpenAI (task_type=objecion)
  ↓
LLM Adapter genera respuesta empática
  ↓
Respuesta con alternativas reales
```

### Flujo 3: Handoff → HUMAN_ACTIVE

```
Mensaje requiere handoff
  ↓
Activa HUMAN_ACTIVE mode
  ↓
Mensaje de handoff con variación
  ↓
Usuario responde → LUISA siempre responde (nunca silencio)
  ↓
TTL expira (12h) → Revert a AI_ACTIVE
```

---

**Última actualización**: 2026-01-09  
**Estado**: Documentación consolidada y actualizada
