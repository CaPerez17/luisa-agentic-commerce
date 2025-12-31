# SalesBrain v1 - LUISA Asesor Comercial Inteligente

## 📋 Resumen

SalesBrain v1 convierte LUISA en un asistente comercial "difícil de detectar" usando OpenAI de forma estratégica (barata, gated) sin inventar datos del negocio.

### Arquitectura: DECIDE → PLAN → SPEAK

1. **DECIDE**: Determina intent base (determinístico primero, OpenAI si ambiguo)
2. **PLAN**: Genera plan de venta estructurado (OpenAI solo cuando aporta valor)
3. **SPEAK**: Genera respuesta final (playbook + planner + humanizer)

---

## 📁 Archivos Nuevos/Modificados

### Archivos Nuevos

1. **`backend/app/domain/business_facts.py`**
   - Datos duros del negocio (horarios, dirección, garantía, promociones, precios)
   - Función `get_business_facts_summary()` para pasar a OpenAI

2. **`backend/app/domain/schemas.py`**
   - Pydantic models: `PlannerOutput`, `ClassifierOutput`, `Recommendation`
   - Validación estricta de JSON de OpenAI

3. **`backend/app/services/openai_classifier.py`**
   - Clasifica intents ambiguos con JSON estricto
   - Solo se llama cuando el mensaje es ambiguo o mezcla intents

4. **`backend/app/services/openai_planner.py`**
   - Genera plan de venta estructurado (JSON)
   - Valida que no invente precios (solo usa facts)

5. **`backend/app/services/sales_brain.py`**
   - Orquestador principal: DECIDE → PLAN → SPEAK
   - Control de costo: cache, límites por conversación, gating
   - Integración con playbook y humanizer

6. **`backend/scripts/test_sales_brain.py`**
   - 12 casos "trampa" para validar comportamiento inteligente

### Archivos Modificados

1. **`backend/app/config.py`**
   - Nuevas env vars: `SALESBRAIN_ENABLED`, `SALESBRAIN_PLANNER_ENABLED`, etc.

2. **`backend/app/routers/whatsapp.py`**
   - Integración de SalesBrain en el webhook
   - Fallback a Sales Dialogue Manager si SalesBrain está deshabilitado

---

## 🔧 Configuración (.env)

```bash
# OpenAI (requerido para SalesBrain)
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...

# SalesBrain
SALESBRAIN_ENABLED=true
SALESBRAIN_PLANNER_ENABLED=true
SALESBRAIN_CLASSIFIER_ENABLED=true
SALESBRAIN_MAX_CALLS_PER_CONVERSATION=4
SALESBRAIN_CACHE_TTL_SECONDS=300
OPENAI_MODEL_CLASSIFIER=gpt-4o-mini
OPENAI_MODEL_PLANNER=gpt-4o-mini
```

---

## 🚀 Despliegue en VPS

```bash
# 1. Conectarse al VPS
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

# 2. Actualizar código
cd /opt/luisa
git pull origin main

# 3. Actualizar .env (agregar nuevas variables)
nano .env
# Agregar:
# SALESBRAIN_ENABLED=true
# SALESBRAIN_PLANNER_ENABLED=true
# SALESBRAIN_CLASSIFIER_ENABLED=true
# SALESBRAIN_MAX_CALLS_PER_CONVERSATION=4
# SALESBRAIN_CACHE_TTL_SECONDS=300
# OPENAI_MODEL_CLASSIFIER=gpt-4o-mini
# OPENAI_MODEL_PLANNER=gpt-4o-mini

# 4. Rebuild y restart
sudo docker compose build --no-cache backend
sudo docker compose up -d backend
sleep 10

# 5. Verificar logs
sudo docker compose logs -f --tail=200 backend

# 6. Verificar health
curl -s https://luisa-agent.online/health | python3 -m json.tool
```

---

## 💬 10 Ejemplos de Conversaciones (3-8 mensajes)

### A) Gorras 20 unidades

```
Usuario: Hola
Luisa: ¡Hola! 😊 Soy Luisa del Almacén El Sastre. Cuéntame qué necesitas y te ayudo (máquinas, repuestos o soporte).

Usuario: Quiero industrial para gorras
Luisa: Perfecto, para gorras. ¿Cuántas al mes aprox?

Usuario: 20
Luisa: Para 20 gorras ocasional, KT-D3 te va bien; si piensas escalar, KS-8800 te dura más. ¿Cuál te suena más: ahorrar hoy o pensar en crecimiento?

Usuario: La primera
Luisa: Perfecto. ¿Te separo una o quieres ver fotos primero?
```

### B) Indeciso

```
Usuario: Industrial
Luisa: Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?

Usuario: No sé cuál
Luisa: Te recomiendo 2 opciones:

• KINGTER KT-D3: $1.230.000 - Ideal para gorras y ropa
• KANSEW KS-8800: $1.300.000 - Más robusta, para producción constante

¿Buscas gastar menos hoy o una más robusta para crecer?

Usuario: Ahorrar hoy
Luisa: Perfecto, KT-D3 es la mejor opción. ¿Te separo una o quieres ver fotos primero?
```

### C) Objeción caro

```
Usuario: Precio
Luisa: Listo 🙌 En promoción están:

• KINGTER KT-D3: $1.230.000
• KANSEW KS-8800: $1.300.000

Ambas incluyen mesa, motor ahorrador e instalación.

¿La necesitas para producción constante o pocas unidades?

Usuario: Muy caro
Luisa: Entiendo. Tenemos opciones:

• Financiación con Addi o Sistecrédito
• Usadas en buen estado (pregunta por disponibilidad)
• Familiares desde $400.000

¿Qué presupuesto manejas?

Usuario: 800 mil
Luisa: Con $800.000 puedes optar por una familiar nueva o una industrial usada. ¿Qué prefieres: nueva familiar o usada industrial?
```

### D) Solo averiguando

```
Usuario: Hola
Luisa: ¡Hola! 😊 Soy Luisa del Almacén El Sastre. Cuéntame qué necesitas y te ayudo (máquinas, repuestos o soporte).

Usuario: Solo estoy averiguando
Luisa: Sin problema. Te mando 2 opciones y listo. ¿Industrial o familiar?

Usuario: Industrial
Luisa: Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?
```

### E) Repuestos

```
Usuario: Repuestos
Luisa: Sí, tenemos repuestos para las marcas que vendemos. De una, así te lo doy exacto. ¿Me confirmas la marca o me envías foto de la placa?

Usuario: Singer
Luisa: Perfecto, Singer. ¿Qué repuesto necesitas: agujas, bobinas, prensatela u otro?
```

### F) Garantía

```
Usuario: Garantía
Luisa: Todas nuestras máquinas tienen garantía de 3 meses en partes y mano de obra. Si algo falla, la revisamos sin costo. ¿Qué máquina tienes o estás pensando comprar?

Usuario: Tengo una KT-D3
Luisa: Perfecto, KT-D3. ¿Qué síntoma tiene o cuándo la compraste?
```

### G) Soporte hilo

```
Usuario: Se me revienta el hilo
Luisa: Te puedo ayudar. Para darte la mejor solución: ¿Qué síntoma tiene (no prende, ruido, etc.)? ¿Marca/modelo? ¿La compraste aquí o en otro lado?

Usuario: KT-D3, la compré aquí
Luisa: Perfecto, KT-D3 comprada aquí. Si está en garantía (3 meses), la revisamos sin costo. ¿Cuándo la compraste?
```

### H) Urgencia

```
Usuario: Industrial
Luisa: Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?

Usuario: Lo necesito para mañana
Luisa: Entiendo la urgencia. Si vienes hoy a la tienda, podemos coordinar instalación para mañana. ¿Te queda mejor venir hoy o mañana?

Usuario: Hoy
Luisa: Perfecto, te esperamos hoy. ¿Mañana o tarde?
```

### I) Visita

```
Usuario: Puedo visitar la tienda? donde queda?
Luisa: Estamos en Calle 34 #1-30, Montería.

🕘 Lunes a viernes: 9am-6pm
🕘 Sábados: 9am-2pm

¿Te queda mejor venir hoy o mañana?

Usuario: Mañana
Luisa: Perfecto, te esperamos mañana. ¿Te llamamos al mismo número de WhatsApp para confirmar?

Usuario: Sí
Luisa: Listo 🙌 ¿Te llamamos al mismo número de WhatsApp? ¿Hoy o mañana? ¿Mañana o tarde?

Usuario: Mañana en la mañana
Luisa: Perfecto, mañana en la mañana. Te esperamos 🙌
```

### J) Envío

```
Usuario: Industrial
Luisa: Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?

Usuario: Gorras
Luisa: Perfecto, para gorras. ¿Cuántas al mes aprox?

Usuario: 20
Luisa: Para 20 gorras ocasional, KT-D3 te va bien; si piensas escalar, KS-8800 te dura más. ¿Cuál te suena más: ahorrar hoy o pensar en crecimiento?

Usuario: La primera, envío a Montelíbano
Luisa: Perfecto, envío a Montelíbano. ¿Dirección completa para el envío?

Usuario: Calle 5 #10-20
Luisa: Perfecto, Calle 5 #10-20, Montelíbano. ¿Te separo una KT-D3 para envío?
```

---

## ✅ Validaciones de Tests

Los tests validan:

- ✅ 1 pregunta máximo por mensaje
- ✅ No menú por defecto
- ✅ No inventa facts (precios/horarios/dirección)
- ✅ Pregunta dato correcto cuando falta
- ✅ Cierres existen (visita/envío/reservar)
- ✅ OpenAI se llama solo cuando corresponde (gated)

---

## 🎯 Control de Costo

- OpenAI solo se llama si:
  - Mensaje ambiguo OR
  - Usuario indeciso OR
  - Objeción detectada OR
  - Soporte técnico complejo

- Límites:
  - Máximo 4 llamadas por conversación
  - Cache TTL: 300 segundos
  - Modelos baratos: `gpt-4o-mini`

---

## 🔒 No Inventa Datos

- Precios: solo de `business_facts.py` (KT-D3: $1.230.000, KS-8800: $1.300.000)
- Horarios: solo de `business_facts.py` (Lunes a viernes: 9am-6pm, Sábados: 9am-2pm)
- Dirección: solo de `business_facts.py` (Calle 34 #1-30, Montería)
- Garantía: solo de `business_facts.py` (3 meses en partes y mano de obra)

Si no sabe, responde humano y pide dato o escala.

---

## 📊 Decision Path (Trazabilidad)

Ejemplos de `decision_path`:

- `salesbrain_planner->humanized`
- `playbook->humanized`
- `salesbrain_planner->openai_called=true->reason=ambiguous_message`
- `playbook->openai_called=false->reason=rules_sufficient`

