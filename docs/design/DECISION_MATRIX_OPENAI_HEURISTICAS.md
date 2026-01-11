# Decision Matrix: OpenAI vs Heurísticas - LUISA

**Product Architect + AI Engineer Analysis**  
**Objetivo**: Definir cuándo LUISA usa OpenAI vs heurísticas puras

---

## Clasificación de Tipos de Mensaje

### Categorías de Decisión

| Categoría | Descripción | Usa OpenAI | Uso Estimado |
|-----------|-------------|------------|--------------|
| **A) Heurística Pura** | Datos duros, intents claros, FAQs | ❌ NO | 70% |
| **B) Heurística + LLM Copy** | Contenido estructurado, redacción natural | ✅ SÍ (copy only) | 15% |
| **C) LLM Razonamiento** | Casos complejos, objeciones, ambigüedad | ✅ SÍ (full reasoning) | 15% |

---

## Taxonomía Completa de Mensajes

### CATEGORÍA A: Heurística Pura (NO OpenAI) - 70%

| Tipo de Mensaje | Ejemplo Real | Estrategia | Usa OpenAI | Motivo |
|-----------------|--------------|------------|------------|--------|
| **Saludos** | "Hola", "Buenos días", "Buenas tardes" | Respuesta fija determinística | ❌ NO | Respuesta estándar predefinida, no requiere adaptación |
| **Despedidas** | "Gracias", "Chau", "Hasta luego" | Respuesta fija de cortesía | ❌ NO | Cierre conversacional estándar |
| **Confirmaciones simples** | "Sí", "Ok", "Dale", "Claro" | Resolver contexto previo + siguiente paso | ❌ NO | Intent claro, lógica determinística |
| **Negaciones simples** | "No", "No gracias", "Otro" | Opciones alternativas predefinidas | ❌ NO | Flujo conversacional controlado |
| **Precios generales** | "¿Cuánto cuesta una máquina?", "¿Precio?" | Respuesta desde business_facts.py | ❌ NO | Datos duros del negocio, NO inventar |
| **Precios específicos** | "¿Cuánto vale la Singer 4423?", "Precio de fileteadora" | Búsqueda en catálogo + business_facts | ❌ NO | Datos estructurados, no requiere razonamiento |
| **Horarios** | "¿Qué horarios tienen?", "¿A qué hora abren?" | Respuesta desde business_facts.py | ❌ NO | Información fija del negocio |
| **Dirección/Ubicación** | "¿Dónde están ubicados?", "¿Cómo llegar?" | Respuesta desde business_facts.py | ❌ NO | Información fija del negocio |
| **Formas de pago** | "¿Aceptan Addi?", "¿Cómo puedo pagar?" | Respuesta predefinida (Addi, Sistecrédito, contado) | ❌ NO | Opciones limitadas y conocidas |
| **Disponibilidad stock** | "¿Tienen máquina industrial?", "¿Hay stock?" | Consulta catálogo/DB | ❌ NO | Consulta estructurada a base de datos |
| **Solicitud de fotos** | "¿Tienes fotos?", "Muéstrame imágenes" | Retornar asset_url desde catálogo | ❌ NO | Búsqueda determinística en catálogo |
| **Envios generales** | "¿Hacen envíos?", "¿A dónde envían?" | Respuesta predefinida (ciudades, costos) | ❌ NO | Información estática del negocio |
| **Repuestos genéricos** | "¿Tienen agujas?", "¿Venden bobinas?" | Respuesta predefinida (sí/no + catálogo) | ❌ NO | Catálogo estructurado |
| **Garantía general** | "¿Qué garantía tiene?", "¿Cubren daños?" | Respuesta desde business_facts.py | ❌ NO | Política fija del negocio |
| **Mensajes fuera del negocio** | "¿Cómo programar en Python?", "Tarea de matemáticas" | Redirección fija predefinida | ❌ NO | Guardrail estricto, no procesar |
| **Mensajes vacíos/gibberish** | ".", "jaja", "👍", solo emojis | Respuesta fija amigable | ❌ NO | Manejo de edge cases |

**Total Categoría A: ~70% de mensajes**

---

### CATEGORÍA B: Heurística + LLM Copy (OpenAI solo redacta) - 15%

| Tipo de Mensaje | Ejemplo Real | Estrategia | Usa OpenAI | Motivo |
|-----------------|--------------|------------|------------|--------|
| **Recomendación con contexto completo** | "Quiero una máquina para producir ropa constante, tengo presupuesto de $1.5M" | Heurísticas determinan: industrial + productos + precios → OpenAI redacta respuesta natural | ✅ SÍ (copy) | Contenido estructurado, pero necesita redacción natural y contextual |
| **Comparación entre opciones** | "¿Cuál es mejor entre la Singer 4423 y la Kingter KT-D3?" | Heurísticas extraen modelos + specs → OpenAI redacta comparación natural | ✅ SÍ (copy) | Datos estructurados, requiere explicación relacional |
| **Confirmación de compra con detalles** | "Sí, me interesa la industrial para empezar mi taller" | Heurísticas detectan confirmación + extraen contexto → OpenAI redacta respuesta de cierre natural | ✅ SÍ (copy) | Flujo estructurado, pero requiere tono personalizado |
| **Respuesta a pregunta específica sobre producto** | "¿La máquina industrial sirve para coser cuero grueso?" | Heurísticas identifican producto + característica → OpenAI redacta explicación técnica natural | ✅ SÍ (copy) | Información estructurada, pero requiere explicación adaptativa |
| **Seguimiento conversacional** | "¿Y cuánto cuesta esa que me mostraste?" (referencia a producto anterior) | Heurísticas resuelven referencia + producto → OpenAI redacta respuesta con continuidad conversacional | ✅ SÍ (copy) | Lógica determinística, pero requiere coherencia conversacional |
| **Clasificación de uso específico** | "Necesito máquina para hacer gorras y producir 50 unidades diarias" | Heurísticas clasifican: industrial + uso + volumen → OpenAI redacta recomendación personalizada | ✅ SÍ (copy) | Contexto estructurado, pero necesita personalización en redacción |

**Cómo funciona:**
1. Heurísticas determinan **QUÉ** decir (contenido, datos, productos)
2. OpenAI solo **REDACTA** de forma natural y contextual
3. Post-procesamiento asegura pregunta cerrada

**Ejemplo técnico:**
```python
# Heurísticas determinan contenido
content = {
    "producto": "Singer 4423",
    "precio": "$1.800.000",
    "uso": "Producción constante ropa",
    "características": ["Velocidad alta", "Motor fuerte"]
}

# OpenAI redacta
prompt = f"""Redacta respuesta comercial natural basándote en estos datos:
Producto: {content['producto']}
Precio: {content['precio']}
Uso: {content['uso']}
Características: {content['características']}

NO inventes datos, solo redacta de forma natural y amigable."""

response = openai_call(prompt)
# Resultado: "Para producción constante de ropa, la Singer 4423 es excelente. 
#             Cuesta $1.800.000 y tiene velocidad alta y motor fuerte. 
#             ¿Te interesa o prefieres ver otra opción?"
```

**Total Categoría B: ~15% de mensajes**

---

### CATEGORÍA C: LLM Razonamiento (Casos complejos) - 15%

| Tipo de Mensaje | Ejemplo Real | Estrategia | Usa OpenAI | Motivo |
|-----------------|--------------|------------|------------|--------|
| **Mensajes ambiguos** | "No sé qué necesito", "Ayúdame a elegir", "¿Cuál me conviene?" | OpenAI Classifier determina intent → OpenAI Planner genera estrategia → OpenAI redacta | ✅ SÍ (reasoning) | No hay suficiente contexto para heurísticas, requiere razonamiento |
| **Objeciones de precio** | "Es muy caro", "No tengo ese presupuesto", "¿No tienen algo más barato?" | OpenAI detecta objeción + razona alternativas → OpenAI genera respuesta que maneja objeción | ✅ SÍ (reasoning) | Requiere razonamiento sobre alternativas y manejo de objeciones |
| **Consultas complejas de asesoría** | "Quiero montar un taller de confección, ¿qué máquinas necesito y en qué orden comprarlas?" | OpenAI analiza contexto del negocio + razona secuencia lógica → OpenAI genera plan personalizado | ✅ SÍ (reasoning) | Requiere razonamiento multi-paso y planeación estratégica |
| **Objeciones de indecisión** | "Solo estoy averiguando", "No estoy seguro", "Todavía no sé si necesito" | OpenAI detecta estado emocional + razona estrategia de avance → OpenAI genera respuesta que reduce fricción | ✅ SÍ (reasoning) | Requiere razonamiento sobre psicología de compra |
| **Problemas técnicos complejos** | "Mi máquina hace ruido raro, a veces avanza y a veces no, y el hilo se rompe. ¿Qué puede ser?" | OpenAI analiza múltiples síntomas + razona diagnóstico → OpenAI genera respuesta diagnóstica | ✅ SÍ (reasoning) | Requiere razonamiento causal multi-variable |
| **Consultas de emprendimiento** | "Tengo $2 millones, quiero empezar a producir ropa para vender, ¿es suficiente? ¿Qué necesito?" | OpenAI razona sobre viabilidad + recursos necesarios + secuencia lógica → OpenAI genera plan | ✅ SÍ (reasoning) | Requiere razonamiento de planeación de negocio |
| **Comparaciones complejas** | "Estoy entre empezar con familiar y después industrial, o ir directo a industrial. ¿Qué me conviene si planeo crecer en 6 meses?" | OpenAI razona sobre proyección temporal + ROI + riesgos → OpenAI genera análisis personalizado | ✅ SÍ (reasoning) | Requiere razonamiento temporal y estratégico |
| **Casos multi-intent mezclados** | "Quiero comprar máquina pero también necesito saber si hacen instalación y cuánto cuesta enviar a Bogotá" | OpenAI clasifica múltiples intents → OpenAI razona prioridades → OpenAI estructura respuesta | ✅ SÍ (reasoning) | Requiere razonamiento sobre múltiples dimensiones simultáneas |

**Cómo funciona:**
1. Heurísticas detectan que es **complejo/ambiguo**
2. OpenAI **RAZONA** sobre el problema
3. OpenAI **GENERA** estrategia y contenido
4. Post-procesamiento valida que no inventa datos

**Ejemplo técnico:**
```python
# Heurísticas detectan complejidad
if is_ambiguous or has_objection or is_complex_consult:
    # OpenAI razona
    classifier_output = openai_classifier(message)  # Decide intent
    
    # OpenAI planea estrategia
    planner_output = openai_planner(
        message, 
        intent=classifier_output.intent,
        context=context,
        history=history
    )  # Genera: next_question, recommended_reply, handoff_needed
    
    # OpenAI redacta
    response = openai_redact(planner_output)
    
    # Validación: no inventar datos
    response = validate_no_facts_invented(response, business_facts)
```

**Total Categoría C: ~15% de mensajes**

---

## Tabla Resumen Ejecutiva

| Categoría | Tipo | % | OpenAI | Función de OpenAI |
|-----------|------|---|--------|-------------------|
| **A) Heurística Pura** | Saludos, FAQs, Datos duros, Confirmaciones simples | 70% | ❌ NO | - |
| **B) Heurística + Copy** | Recomendaciones estructuradas, Comparaciones, Respuestas contextuales | 15% | ✅ SÍ | Solo redacción natural |
| **C) LLM Razonamiento** | Ambiguos, Objeciones, Consultas complejas, Multi-intent | 15% | ✅ SÍ | Clasificación + Planeación + Redacción |

---

## Flujo de Decisión Técnico

```
Mensaje Entrante
    ↓
1. Clasificación (Heurísticas) → MessageType
    ├─ EMPTY/NON_BUSINESS → Respuesta fija (A)
    ├─ BUSINESS_FAQ → Cache/Reglas (A)
    └─ BUSINESS_CONSULT → Continúa...
    ↓
2. Intent Analysis (Heurísticas)
    ├─ Intent claro (confidence > 0.7) → Clasificar por categoría
    └─ Intent ambiguo → CATEGORÍA C (OpenAI Classifier)
    ↓
3. Categorización
    ├─ CATEGORÍA A: Datos duros, FAQs, Confirmaciones → Heurísticas puras
    ├─ CATEGORÍA B: Contenido estructurado → Heurísticas + OpenAI Copy
    └─ CATEGORÍA C: Complejo/Ambiguo → OpenAI Reasoning completo
    ↓
4. Generación de Respuesta
    ├─ A: Respuesta determinística (0ms OpenAI)
    ├─ B: OpenAI redacta contenido estructurado (~1s, copy only)
    └─ C: OpenAI razona + genera (~2-3s, full reasoning)
    ↓
5. Post-procesamiento
    └─ Validar datos + Asegurar pregunta cerrada
```

---

## Criterios de Decisión Detallados

### ¿Cuándo usar CATEGORÍA A (Heurística Pura)?

**SÍ usar si:**
- ✅ El mensaje tiene un intent claro y determinístico
- ✅ La respuesta requiere solo datos duros del negocio
- ✅ Existe una regla o respuesta predefinida que cubre el caso
- ✅ No requiere adaptación contextual compleja

**NO usar si:**
- ❌ El mensaje es ambiguo o mezcla múltiples intents
- ❌ Requiere razonamiento sobre alternativas o estrategias
- ❌ Involucra objeciones o estados emocionales del cliente

### ¿Cuándo usar CATEGORÍA B (Heurística + LLM Copy)?

**SÍ usar si:**
- ✅ Las heurísticas pueden determinar **QUÉ** decir (contenido, productos, datos)
- ✅ Se necesita redacción natural y contextual
- ✅ El contenido es estructurado pero la forma de presentarlo debe ser personalizada
- ✅ Se requiere coherencia conversacional pero sin razonamiento complejo

**Ejemplos:**
- Producto ya determinado por heurísticas → OpenAI redacta presentación
- Comparación entre opciones ya identificadas → OpenAI explica diferencias
- Confirmación con contexto completo → OpenAI redacta cierre natural

### ¿Cuándo usar CATEGORÍA C (LLM Razonamiento)?

**SÍ usar si:**
- ✅ El mensaje es ambiguo o no tiene intent claro
- ✅ Requiere razonamiento sobre múltiples alternativas o estrategias
- ✅ Involucra objeciones que necesitan manejo psicológico
- ✅ Es una consulta compleja que requiere planeación o análisis
- ✅ Mezcla múltiples intents simultáneos

**Ejemplos:**
- "No sé qué necesito" → Razonar sobre necesidades según contexto
- "Es muy caro" → Razonar alternativas y manejo de objeción
- "Quiero montar taller, ¿qué necesito?" → Razonar plan de negocio

---

## Configuración Recomendada por Escenario

### MVP/Demo Comercial (Costo: $0)

```bash
OPENAI_ENABLED=false
SALESBRAIN_ENABLED=false
```

**Resultado:**
- 100% Categoría A (Heurísticas puras)
- Cero costo
- Latencia < 100ms
- Cubre 70% de casos bien, 30% con respuestas genéricas

### Producción Inicial (Costo: $10-30/mes)

```bash
OPENAI_ENABLED=true
SALESBRAIN_ENABLED=true
SALESBRAIN_MAX_CALLS_PER_CONVERSATION=4
SALESBRAIN_CLASSIFIER_ENABLED=true
SALESBRAIN_PLANNER_ENABLED=true
```

**Resultado:**
- 70% Categoría A (Heurísticas)
- 15% Categoría B (Copy)
- 15% Categoría C (Reasoning)
- Costo promedio: $0.01-0.03 por conversación

### Producción Escalada (Costo: $30-100/mes)

```bash
# Misma configuración, con más tráfico
# Ajustar límites según volumen
SALESBRAIN_MAX_CALLS_PER_CONVERSATION=6
```

**Resultado:**
- Misma distribución 70/15/15
- Mayor volumen = mayor costo pero proporcional
- Optimización: Cache más agresivo para Categoría B

---

## Métricas de Validación

### KPIs a Monitorear

```sql
-- Distribución por categoría
SELECT 
    CASE 
        WHEN openai_called = 0 THEN 'A) Heurística Pura'
        WHEN decision_path LIKE '%copy%' OR decision_path LIKE '%redact%' THEN 'B) Heurística + Copy'
        WHEN decision_path LIKE '%reasoning%' OR decision_path LIKE '%classifier%' OR decision_path LIKE '%planner%' THEN 'C) LLM Razonamiento'
        ELSE 'Unknown'
    END as categoria,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM interaction_traces WHERE created_at > datetime('now', '-7 days')), 2) as percentage,
    AVG(latency_ms) as avg_latency_ms,
    AVG(CASE WHEN openai_called = 1 THEN 0.02 ELSE 0 END) as avg_cost_usd
FROM interaction_traces
WHERE created_at > datetime('now', '-7 days')
GROUP BY categoria;
```

**Objetivos:**
- Categoría A: 65-75% (heurísticas puras)
- Categoría B: 12-18% (copy)
- Categoría C: 12-18% (reasoning)

---

## Reglas de Oro

1. **Nunca usar OpenAI para:**
   - Datos duros (precios, horarios, dirección)
   - Lógica de negocio (handoff, routing)
   - Validaciones (rate limiting, guardrails)
   - Respuestas predefinidas estándar

2. **Siempre usar heurísticas primero:**
   - Clasificación de mensajes
   - Extracción de contexto
   - Determinación de productos/datos relevantes

3. **OpenAI solo cuando:**
   - Las heurísticas no pueden determinar contenido claro (Categoría C)
   - O cuando el contenido está claro pero necesita redacción natural (Categoría B)

4. **Validar siempre:**
   - OpenAI no inventa datos duros
   - Respuesta termina con pregunta cerrada
   - No menciona ser "bot/IA"
   - Respeta límites de tokens y tiempo

---

## Conclusión: % Estimado de Uso de OpenAI

### Distribución Final

| Métrica | Valor | Explicación |
|---------|-------|-------------|
| **Categoría A (Heurística Pura)** | **70%** | Casos simples, datos duros, FAQs, confirmaciones |
| **Categoría B (Copy)** | **15%** | Contenido estructurado que necesita redacción natural |
| **Categoría C (Reasoning)** | **15%** | Casos complejos, ambiguos, objeciones, consultas avanzadas |
| **Total que usa OpenAI** | **30%** | Solo cuando realmente aporta valor |
| **Total sin OpenAI** | **70%** | Heurísticas puras, cero costo |

### Costo Estimado

**Por conversación promedio:**
- Categoría A: $0.00 (0 llamadas OpenAI)
- Categoría B: $0.01 (1 llamada copy)
- Categoría C: $0.02-0.05 (2-3 llamadas: classifier + planner + redact)

**Costo promedio ponderado:**
```
(0.70 × $0.00) + (0.15 × $0.01) + (0.15 × $0.03) = $0.006 por conversación
```

**Con 1000 conversaciones/mes:**
- Costo total: ~$6-9/mes
- Comparado con OpenAI puro: $150-600/mes
- **Ahorro: 95-98%**

### Ventajas del Enfoque Híbrido

1. ✅ **Costo controlado**: Solo pagas por casos que realmente necesitan IA
2. ✅ **Latencia balanceada**: Rápido para mayoría (70%), inteligente para complejos (30%)
3. ✅ **Confiabilidad**: Fallback a heurísticas si OpenAI falla
4. ✅ **Escalabilidad**: Ajustable según necesidades y presupuesto
5. ✅ **No es "otro chatbot"**: Combina datos duros + inteligencia contextual

---

**Última actualización**: 2025-01-05  
**Revisión**: Product Architect + AI Engineer

