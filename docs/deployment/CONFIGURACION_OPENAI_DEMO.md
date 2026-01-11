# Configuración OpenAI para Demo Comercial

**Fecha**: 2025-01-05  
**Objetivo**: OpenAI solo cuando realmente mejora, sin bloquear respuestas, costo controlado

---

## Configuración Recomendada (.env)

```bash
# ============================================================================
# OPENAI CONFIGURATION - DEMO COMERCIAL
# ============================================================================

# Habilitar OpenAI (necesario para que funcione)
OPENAI_ENABLED=true

# Límites por conversación (generoso para demo, pero controlado)
OPENAI_MAX_CALLS_PER_CONVERSATION=6

# TTL para resetear contador (12 horas = 2 conversaciones por día máximo)
OPENAI_CONVERSATION_TTL_HOURS=12

# Tokens de salida (suficiente para respuestas cortas y naturales)
OPENAI_MAX_OUTPUT_TOKENS=150

# Temperatura (más determinístico = más predecible y controlado)
OPENAI_TEMPERATURE=0.3

# Modelo (económico y rápido)
OPENAI_MODEL=gpt-4o-mini

# Timeout (ya está en código como 5s duro, no configurable)
# OPENAI_TIMEOUT_SECONDS=8  # No se usa en LLM Adapter (usa 5s duro)
```

---

## Explicación de Valores

### `OPENAI_ENABLED=true`
**Por qué**: Necesario para que OpenAI funcione. Si está en `false`, nunca se llamará al modelo.

**Impacto**: Sin esto, todas las respuestas serán heurísticas (fallbacks).

---

### `OPENAI_MAX_CALLS_PER_CONVERSATION=6`
**Por qué**: Balance entre generosidad y control de costo.

**Razonamiento**:
- **Demo típica**: 1-2 conversaciones por cliente
- **Conversación promedio**: 5-8 mensajes
- **Casos que necesitan OpenAI**: ~20-30% de mensajes (objeciones, consultas complejas)
- **Cálculo**: 8 mensajes × 30% = ~2-3 llamadas por conversación
- **Margen de seguridad**: 6 llamadas permite 2 conversaciones completas sin bloqueo

**Si fuera 4**: Podría bloquear en conversaciones largas (riesgo en demo)  
**Si fuera 10+**: Costo innecesario (la mayoría de mensajes no necesita OpenAI)

**Garantía**: Si se excede, hay fallback automático (nunca bloquea respuesta).

---

### `OPENAI_CONVERSATION_TTL_HOURS=12`
**Por qué**: Reset rápido para permitir múltiples conversaciones en el mismo día.

**Razonamiento**:
- **Demo típica**: Cliente puede volver a escribir en 4-6 horas
- **Con TTL=24h**: Si usa 6 llamadas a las 10am, no puede usar más hasta las 10am del día siguiente
- **Con TTL=12h**: Si usa 6 llamadas a las 10am, puede usar más a las 10pm (mismo día)

**Impacto en costo**: Mínimo (solo resetea contador, no genera llamadas adicionales automáticamente).

---

### `OPENAI_MAX_OUTPUT_TOKENS=150`
**Por qué**: Suficiente para respuestas cortas y naturales (2-3 frases + pregunta cerrada).

**Razonamiento**:
- **Respuesta típica de LUISA**: 50-100 palabras = ~70-140 tokens
- **150 tokens** = ~110 palabras = 2-3 frases + pregunta cerrada
- **Si fuera 180+**: Riesgo de respuestas muy largas (no ideal para WhatsApp)
- **Si fuera 100**: Podría truncar respuestas naturales

**Ejemplo de respuesta con 150 tokens**:
```
"Entiendo tu preocupación por el precio. Tenemos opciones desde $400.000 
para uso familiar. ¿Te interesa ver opciones de financiamiento con Addi 
o prefieres una máquina usada?"
```
(~50 palabras = ~70 tokens, dentro del límite)

---

### `OPENAI_TEMPERATURE=0.3`
**Por qué**: Más determinístico = más predecible y controlado para demo.

**Razonamiento**:
- **Temperature 0.0-0.3**: Muy determinístico, respuestas consistentes
- **Temperature 0.4-0.7**: Balance creatividad/consistencia
- **Temperature 0.8-1.0**: Muy creativo, respuestas variables

**Para demo comercial**:
- ✅ **0.3**: Respuestas consistentes, predecibles, profesionales
- ⚠️ **0.4**: Aceptable, pero puede variar más entre llamadas
- ❌ **0.5+**: Demasiado variable, puede generar respuestas inesperadas

**Impacto**: Con 0.3, la misma objeción genera respuestas similares (mejor para demo).

---

## ¿Qué Casos Dispararán OpenAI?

### ✅ Casos que SÍ usarán OpenAI (con esta configuración)

#### 1. **Objeciones de Precio**
**Ejemplo de mensaje**:
```
"Está muy caro, no tengo ese presupuesto"
"Es muy costoso, hay algo más barato?"
"Solo estoy averiguando, todavía no sé"
```

**Task Type**: `OBJECION`  
**Por qué**: Detecta keywords de objeción → `_determine_llm_task_type()` retorna `OBJECION`  
**Gating**: Pasa si `message_type == BUSINESS_CONSULT` y no es FAQ

**Respuesta esperada**: Empatía + alternativas reales (financiamiento, opciones más económicas)

---

#### 2. **Consultas Complejas / Ambiguas**
**Ejemplo de mensaje**:
```
"Quiero montar un taller, qué necesito?"
"No sé qué máquina me conviene"
"Ayúdame a elegir entre varias opciones"
"Qué máquinas necesito para empezar un emprendimiento?"
```

**Task Type**: `CONSULTA_COMPLEJA`  
**Por qué**: Detecta keywords de ambigüedad/emprendimiento → `_determine_llm_task_type()` retorna `CONSULTA_COMPLEJA`  
**Gating**: Pasa si `message_type == BUSINESS_CONSULT` y no es FAQ

**Respuesta esperada**: Análisis estructurado + recomendaciones basadas en contexto

---

#### 3. **Comparaciones / Explicaciones Técnicas**
**Ejemplo de mensaje**:
```
"Cuál es la diferencia entre Singer y Kingter?"
"Explícame cómo funciona una fileteadora"
"Qué significa que sea mecatrónica?"
```

**Task Type**: `EXPLICACION`  
**Por qué**: Detecta keywords de comparación/explicación → `_determine_llm_task_type()` retorna `EXPLICACION`  
**Gating**: Pasa si `message_type == BUSINESS_CONSULT` y no es FAQ

**Respuesta esperada**: Explicación simple + comparación clara

---

#### 4. **Redacción Comercial (cuando hay contexto completo)**
**Ejemplo de mensaje**:
```
"Me interesa la KINGTER KT-D3, cuéntame más"
"Quiero saber sobre la promoción navideña"
```

**Task Type**: `COPY`  
**Por qué**: Hay productos recomendados en contexto → `_determine_llm_task_type()` retorna `COPY`  
**Gating**: Pasa si `message_type == BUSINESS_CONSULT` y no es FAQ

**Respuesta esperada**: Texto comercial natural + pregunta cerrada

---

### ❌ Casos que NO usarán OpenAI (siempre heurísticas)

#### 1. **FAQs Simples**
**Ejemplo de mensaje**:
```
"Cuál es el horario?"
"Dónde están ubicados?"
"Cuánto cuesta el envío?"
"Aceptan Addi?"
```

**Por qué**: `intent` está en lista de FAQs → `should_call_openai()` retorna `False`  
**Respuesta**: Cache o reglas determinísticas (sin OpenAI)

---

#### 2. **Saludos / Despedidas**
**Ejemplo de mensaje**:
```
"Hola"
"Buenos días"
"Gracias, hasta luego"
```

**Por qué**: `intent == "saludo"` o `"despedida"` → `should_call_openai()` retorna `False`  
**Respuesta**: Variantes de saludo determinísticas (sin OpenAI)

---

#### 3. **Mensajes Off-Topic**
**Ejemplo de mensaje**:
```
"Quiero aprender Python"
"Tengo una tarea de matemáticas"
```

**Por qué**: `message_type == NON_BUSINESS` → `should_call_openai()` retorna `False`  
**Respuesta**: Redirección fija (sin OpenAI)

---

#### 4. **Cache Hit**
**Ejemplo de mensaje**:
```
"Cuál es el horario?" (ya preguntado antes)
```

**Por qué**: `cache_hit == True` → `should_call_openai()` retorna `False`  
**Respuesta**: Respuesta cacheada (sin OpenAI)

---

#### 5. **Respuesta Determinística Robusta Disponible**
**Ejemplo de mensaje**:
```
"Quiero una máquina industrial para gorras"
```

**Por qué**: `context.has_robust_deterministic == True` → `should_call_openai()` retorna `False`  
**Respuesta**: Reglas determinísticas (sin OpenAI)

---

## Garantías del Sistema

### ✅ Nunca Bloquea Respuestas

**Mecanismo**:
1. Si `OPENAI_MAX_CALLS_PER_CONVERSATION` se excede → Fallback automático
2. Si OpenAI falla (timeout, error) → Fallback automático
3. Si OpenAI retorna vacío → Fallback automático

**Código relevante**: `llm_adapter.py:471-618` (siempre retorna fallback si falla)

**Ejemplo**:
```
Conversación usa 6 llamadas → Llamada 7:
- OpenAI NO se llama (límite excedido)
- Se usa fallback heurístico
- Usuario recibe respuesta (nunca silencio)
```

---

### ✅ Costo Controlado

**Estimación de costo por conversación** (con esta configuración):

**Escenario típico**:
- Conversación: 8 mensajes
- Mensajes que usan OpenAI: 2-3 (objeciones/complejas)
- Tokens por llamada: ~150 output + ~200 input = ~350 tokens
- Costo por 1000 tokens (gpt-4o-mini): ~$0.15 / 1000 tokens

**Cálculo**:
- 3 llamadas × 350 tokens = 1,050 tokens
- Costo: 1.05 × $0.15 = **~$0.16 por conversación**

**Con límite de 6 llamadas**:
- Máximo: 6 × 350 = 2,100 tokens
- Costo máximo: 2.1 × $0.15 = **~$0.32 por conversación**

**Para 100 conversaciones/día**:
- Costo promedio: 100 × $0.16 = **~$16/día**
- Costo máximo: 100 × $0.32 = **~$32/día**

**Con TTL=12h**: Permite 2 conversaciones por día por cliente sin reset = **~$0.64 máximo por cliente/día**

---

## Comparación de Configuraciones

| Configuración | `MAX_CALLS` | `TTL_HOURS` | `MAX_TOKENS` | `TEMP` | Uso en Demo | Costo/Día (100 conv) |
|---------------|-------------|-------------|--------------|--------|-------------|----------------------|
| **Recomendada (Demo)** | 6 | 12 | 150 | 0.3 | ✅ Generoso sin exceso | ~$16-32 |
| **Conservadora** | 4 | 24 | 120 | 0.2 | ⚠️ Puede bloquear en conv largas | ~$10-20 |
| **Generosa** | 10 | 6 | 200 | 0.4 | ⚠️ Costo innecesario | ~$30-60 |
| **Deshabilitada** | - | - | - | - | ❌ Sin OpenAI (solo heurísticas) | $0 |

---

## Checklist de Verificación

Antes de la demo, verificar:

- [ ] `OPENAI_ENABLED=true` en `.env`
- [ ] `OPENAI_API_KEY` está configurado y válido
- [ ] `OPENAI_MAX_CALLS_PER_CONVERSATION=6` (o al menos 4)
- [ ] `OPENAI_CONVERSATION_TTL_HOURS=12` (o menos)
- [ ] `OPENAI_MAX_OUTPUT_TOKENS=150` (suficiente para respuestas cortas)
- [ ] `OPENAI_TEMPERATURE=0.3` (determinístico)
- [ ] Probar mensaje de objeción: "Está muy caro" → Debe usar OpenAI
- [ ] Probar mensaje FAQ: "Cuál es el horario?" → NO debe usar OpenAI
- [ ] Verificar logs: `openai_decision_made` aparece solo en casos complejos

---

## Ejemplos de Prueba

### Test 1: Objeción (debe usar OpenAI)
```
Usuario: "Está muy caro, no tengo ese presupuesto"
Esperado: OpenAI se llama (task_type=objecion)
Log esperado: "openai_decision_made" con reason_for_llm_use="objecion:..."
```

### Test 2: Consulta Compleja (debe usar OpenAI)
```
Usuario: "Quiero montar un taller, qué necesito?"
Esperado: OpenAI se llama (task_type=consulta_compleja)
Log esperado: "openai_decision_made" con reason_for_llm_use="consulta_compleja:..."
```

### Test 3: FAQ Simple (NO debe usar OpenAI)
```
Usuario: "Cuál es el horario?"
Esperado: OpenAI NO se llama (cache/reglas)
Log esperado: NO aparece "openai_decision_made"
```

### Test 4: Límite Excedido (fallback automático)
```
Conversación con 6 llamadas ya usadas
Usuario: "Tengo otra objeción..."
Esperado: OpenAI NO se llama (límite excedido), fallback heurístico
Log esperado: "LLM Adapter: Límite excedido, usando fallback"
```

---

## Resumen Ejecutivo

### Configuración Final (.env)

```bash
OPENAI_ENABLED=true
OPENAI_MAX_CALLS_PER_CONVERSATION=6
OPENAI_CONVERSATION_TTL_HOURS=12
OPENAI_MAX_OUTPUT_TOKENS=150
OPENAI_TEMPERATURE=0.3
OPENAI_MODEL=gpt-4o-mini
```

### Casos que Disparan OpenAI

1. ✅ **Objeciones** ("muy caro", "solo averiguando")
2. ✅ **Consultas complejas** ("qué necesito para montar taller?")
3. ✅ **Explicaciones técnicas** ("cuál es la diferencia?")
4. ✅ **Redacción comercial** (cuando hay contexto completo)

### Casos que NO Disparan OpenAI

1. ❌ FAQs simples (horarios, dirección, precios básicos)
2. ❌ Saludos/despedidas
3. ❌ Mensajes off-topic
4. ❌ Cache hits
5. ❌ Respuestas determinísticas robustas disponibles

### Garantías

- ✅ **Nunca bloquea**: Siempre hay fallback si OpenAI falla o se excede límite
- ✅ **Costo controlado**: ~$0.16-0.32 por conversación (máximo)
- ✅ **Solo cuando mejora**: Gating estricto asegura uso solo en casos complejos

---

**Última actualización**: 2025-01-05  
**Estado**: ✅ Listo para demo comercial

