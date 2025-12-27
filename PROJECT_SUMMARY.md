# Resumen del Proyecto - Sistema Luisa para Almacén y Taller El Sastre

## Objetivo del Proyecto

Construir un sistema de asistente comercial que simula conversaciones entrantes desde Facebook Marketplace/Messenger, donde:
- El cliente siempre cree que habla con Luisa (asistente comercial)
- Nunca se menciona bot, sistema, IA, equipo ni transferencia
- El sistema guía la conversación de forma humana y técnica
- Cuando detecta que se requiere atención humana, notifica a Luisa por WhatsApp con output estructurado y accionable
- El cliente nunca queda en silencio: el sistema mantiene el lead caliente con mensajes puente

## Contexto del Negocio

**Almacén y Taller El Sastre** es un negocio en Montería, Colombia que:
- Vende máquinas de coser familiares e industriales
- Tiene taller de reparación de máquinas
- Vende accesorios y repuestos
- Ayuda a emprendedores a elegir máquinas según su proyecto y presupuesto
- Ofrece servicio técnico con garantía
- Hace envíos a todo el país

**Información del negocio:**
- Ubicación: Calle 34 # 1-30, Montería, Colombia
- Teléfono: 304 4895059
- Email: chelena-21@hotmail.com
- Horarios: Lunes a viernes 9am-6pm, Sábados 9am-2pm
- Website: almacenytallerelsastre.com

**Marcas que manejan:**
- KINGTER
- KANSEW
- WILLCOX
- Y otras marcas reconocidas

**Promociones activas (diciembre 2024):**
- Máquina plana mecatrónica KINGTER KT-D3: $1.230.000
- Máquina plana mecatrónica KANSEW KS-8800: $1.300.000

## Stack Tecnológico

### Backend
- **Framework:** FastAPI (Python)
- **Base de datos:** SQLite (`luisa.db`)
- **Puerto:** 8000
- **Endpoints principales:**
  - `POST /api/chat` - Recibe mensajes y genera respuestas
  - `GET /api/handoffs` - Obtiene todos los handoffs generados
  - `GET /api/conversations/{conversation_id}` - Obtiene una conversación completa

### Frontend
- **Tecnología:** HTML/CSS/JavaScript puro (sin frameworks)
- **UI:** Interfaz tipo Messenger con diseño moderno
- **Características:**
  - Simulación de typing indicator
  - Tiempos de respuesta adaptativos según longitud del mensaje
  - Vista interna para ver handoffs (botón 🔍)
  - Diseño responsive tipo WhatsApp/Messenger

### Notificaciones
- **Modo demo:** Imprime en consola + guarda JSON en `/outbox`
- **Modo producción:** Integración desacoplada lista para WhatsApp Cloud API o Twilio

## Estructura del Proyecto

```
Sastre/
├── backend/
│   ├── main.py              # API FastAPI completa
│   ├── requirements.txt     # Dependencias Python
│   └── venv/                # Entorno virtual (no en git)
├── frontend/
│   ├── index.html           # Interfaz tipo Messenger
│   ├── styles.css           # Estilos modernos
│   └── app.js               # Lógica del frontend
├── outbox/                  # Handoffs generados (JSON)
├── README.md                # Instrucciones de uso
├── DEMO_SCENARIOS.md        # Guía de escenarios
├── PROJECT_SUMMARY.md       # Este archivo
└── start.sh                 # Script de inicio rápido
```

## Base de Datos (SQLite)

### Tabla: conversations
- `conversation_id` (TEXT PRIMARY KEY)
- `customer_name` (TEXT)
- `status` (TEXT) - active, escalated, closed
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

### Tabla: messages
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `conversation_id` (TEXT, FOREIGN KEY)
- `text` (TEXT)
- `sender` (TEXT) - "customer" o "luisa"
- `timestamp` (TIMESTAMP)

### Tabla: handoffs
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `conversation_id` (TEXT, FOREIGN KEY)
- `reason` (TEXT)
- `priority` (TEXT) - urgent, high, medium, low
- `summary` (TEXT)
- `suggested_response` (TEXT)
- `customer_name` (TEXT)
- `timestamp` (TIMESTAMP)

## Motor de Decisión

### Análisis de Mensajes

El sistema analiza cada mensaje para determinar:
1. **Si necesita escalamiento humano**
2. **Prioridad del escalamiento** (urgent, high, medium, low)
3. **Respuesta apropiada** según el contexto

### Palabras Clave para Escalamiento

**Urgente:**
- "urgente", "ya", "inmediato", "ahora mismo", "emergencia"
- "roto", "no funciona", "mal estado", "defectuoso"
- "reclamo", "demanda", "abogado", "legal"

**Alto:**
- "problema", "error", "no llegó", "perdido", "equivocado"
- "devolución", "reembolso", "cancelar", "cancelación"
- "insatisfecho", "mal servicio", "defectuoso", "rota", "no funciona"
- "reclamo", "queja", "mal estado"

**Medio (Asesoría técnica):**
- "presupuesto", "cuál me recomiendas", "qué máquina"
- "asesoría", "emprendimiento", "qué necesito"
- "recomendación", "comparar"
- Combinado con intención de compra: "quiero comprar", "me interesa"

**Solicitud de persona:**
- "quiero hablar con", "hablar con alguien", "hablar con el dueño"

### Generación de Respuestas

Luisa tiene conocimiento específico sobre:

1. **Tipos de máquinas:**
   - Familiares vs industriales
   - Planas mecatrónicas
   - Fileteadoras/overlock

2. **Marcas específicas:**
   - KINGTER KT-D3 (promoción $1.230.000)
   - KANSEW KS-8800 (promoción $1.300.000)
   - WILLCOX y otras

3. **Servicios:**
   - Taller de reparación
   - Servicio técnico con garantía
   - Envíos nacionales
   - Asesoría para emprendedores

4. **Información del negocio:**
   - Ubicación, teléfono, horarios
   - Promociones activas

## Flujo de Conversación

1. Cliente envía mensaje → `POST /api/chat`
2. Sistema analiza el mensaje con `analyze_message()`
3. Genera respuesta con `generate_response()` (conocimiento técnico específico)
4. Guarda mensaje del cliente y respuesta de Luisa en DB
5. Si necesita escalamiento:
   - Crea handoff con resumen estructurado
   - Guarda en DB y `/outbox` como JSON
   - Imprime notificación en consola (simula WhatsApp)
   - Actualiza estado de conversación a "escalated"
6. Cliente recibe respuesta inmediata (nunca queda sin respuesta)

## Handoffs (Escalamiento)

### Estructura del Handoff JSON

```json
{
  "conversation_id": "conv_1234567890_abc123",
  "reason": "Cliente necesita asesoría técnica personalizada para compra",
  "priority": "medium",
  "summary": "📋 RESUMEN DE CONVERSACIÓN\n\nÚltimo mensaje del cliente: ...\n\nHistorial reciente:\n👤 Cliente: ...\n💬 Luisa: ...\n\n💡 CONTEXTO: Cliente interesado en compra de máquina",
  "suggested_response": "Perfecto, déjame consultar con nuestros especialistas...",
  "customer_name": null,
  "timestamp": "2024-12-13T14:50:00"
}
```

### Prioridades

- **urgent:** Requiere atención inmediata (problemas críticos, urgencias)
- **high:** Problemas o consultas complejas (reclamos, devoluciones)
- **medium:** Asesoría técnica personalizada, solicitudes de persona
- **low:** (No se usa actualmente, todas las consultas se escalan)

## Características Clave

### Reglas Críticas Implementadas

✅ **CERO botones o menús** en la conversación
✅ **CERO menciones** a bot, automatización, sistema o IA
✅ El nombre visible **SIEMPRE es "Luisa"**
✅ Tono técnico-comercial humano
✅ Código funcional, no pseudo-código
✅ El cliente **nunca queda en silencio**

### Experiencia de Usuario

- **Typing simulation:** Tiempos adaptativos según longitud del mensaje (1.5-4 segundos)
- **Variaciones en respuestas:** Múltiples opciones para evitar repetición
- **Mensajes puente:** Mantienen el lead caliente durante escalamiento
- **Vista interna:** Solo para demo, muestra handoffs generados

## Ejecución

### Inicio Rápido

```bash
cd Sastre
./start.sh
```

Luego abrir `frontend/index.html` en el navegador.

### Manual

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# Frontend
# Abrir frontend/index.html directamente en navegador
```

## Estado Actual

✅ **Backend completo y funcional**
✅ **Frontend completo con UI tipo Messenger**
✅ **Motor de decisión con conocimiento técnico específico**
✅ **Sistema de handoffs funcionando**
✅ **Base de datos SQLite operativa**
✅ **Notificaciones simuladas (consola + JSON)**
✅ **Vista interna para ver handoffs**

## Próximos Pasos (Opcionales)

- Integración real con WhatsApp Cloud API o Twilio
- Mejorar detección de intención con NLP más avanzado
- Agregar más conocimiento sobre productos específicos
- Sistema de seguimiento de leads
- Dashboard para gestión de handoffs

## Archivos Importantes

- `backend/main.py` - Lógica principal del sistema (546 líneas)
- `frontend/app.js` - Lógica del frontend (241 líneas)
- `frontend/styles.css` - Estilos de la interfaz
- `frontend/index.html` - Estructura HTML

## Notas Técnicas

- El sistema usa reglas basadas en palabras clave (no NLP avanzado)
- Las respuestas son predefinidas pero con variaciones aleatorias
- El escalamiento es automático basado en detección de patrones
- Los handoffs se generan automáticamente cuando se detecta necesidad
- El sistema está diseñado para ser creíble y humano, no para ser perfecto

## Contacto y Soporte

Para preguntas sobre el proyecto, revisar:
- `README.md` - Instrucciones de uso
- `DEMO_SCENARIOS.md` - Escenarios de prueba
- Código fuente con comentarios en español

---

**Última actualización:** Diciembre 2024
**Versión:** 1.0 - Demo funcional completo

