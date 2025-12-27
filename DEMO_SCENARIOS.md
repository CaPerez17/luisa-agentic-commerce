# Escenarios de Demo para Luisa

## Escenarios que puedes probar durante el demo

### 1. Confirmación de Pago
**Cliente dice:**
- "Hola, ya hice el pago"
- "Transferí el dinero, ¿lo recibieron?"
- "Quiero confirmar mi pago"

**Resultado:** Luisa responde de forma empática y genera handoff si es necesario verificar.

### 2. Estado de Envío
**Cliente dice:**
- "¿Dónde está mi pedido?"
- "Mi envío no ha llegado"
- "Quiero saber el estado de mi entrega"

**Resultado:** Luisa pide número de pedido y puede generar handoff si hay problema.

### 3. Verificación de Stock
**Cliente dice:**
- "¿Tienen máquinas de coser disponibles?"
- "Hay stock de hilos?"
- "¿Cuántas tienen?"

**Resultado:** Luisa pregunta qué producto específicamente necesita.

### 4. Horario para Llevar Máquina
**Cliente dice:**
- "¿A qué hora puedo pasar?"
- "¿Cuándo están abiertos?"
- "Quiero llevar mi máquina, ¿qué día puedo?"

**Resultado:** Luisa informa horarios y puede generar handoff si necesita coordinación.

### 5. Lead Caliente / Urgente
**Cliente dice:**
- "URGENTE: necesito esto ya"
- "Mi máquina está rota, necesito ayuda inmediata"
- "Tengo un problema urgente"

**Resultado:** Genera handoff con prioridad "urgent" y notifica inmediatamente.

### 6. Problema o Reclamo
**Cliente dice:**
- "El producto llegó defectuoso"
- "Quiero hacer una devolución"
- "Estoy muy insatisfecho"

**Resultado:** Genera handoff con prioridad "high" para atención especializada.

### 7. Solicitud de Hablar con Persona
**Cliente dice:**
- "Quiero hablar con el dueño"
- "Necesito hablar con alguien"
- "¿Puedo hablar con una persona?"

**Resultado:** Genera handoff con prioridad "medium" para transferencia humana.

## Tips para el Demo

1. **Mantén conversaciones naturales** - No menciones "bot" ni "sistema"
2. **Usa la vista interna** - Presiona 🔍 para ver los handoffs generados
3. **Observa la consola** - Los handoffs también se imprimen en la terminal del backend
4. **Revisa /outbox** - Los JSON se guardan ahí para integración futura
5. **Prueba múltiples conversaciones** - Cada una tiene su propio conversation_id

## Flujo de Escalamiento

1. Cliente envía mensaje
2. Sistema analiza y determina si necesita escalamiento
3. Luisa responde manteniendo el lead caliente
4. Si necesita escalamiento:
   - Se genera handoff con JSON estructurado
   - Se guarda en base de datos
   - Se imprime en consola (simulando WhatsApp)
   - Se guarda JSON en /outbox
5. Cliente nunca queda sin respuesta

