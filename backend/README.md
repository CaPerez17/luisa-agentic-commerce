# LUISA - Asistente Virtual El Sastre

Sistema de asistente comercial para Almacén y Taller El Sastre en Montería, Colombia.

## 🚀 Arquitectura v2.0

```
backend/
├── main.py                 # Entrypoint legacy + integración nuevos módulos
├── intent_analyzer.py      # Analizador de intención (legacy)
├── luisa.db               # Base de datos SQLite
│
├── app/                    # Nueva estructura modular
│   ├── main.py            # FastAPI app factory
│   ├── config.py          # Configuración centralizada
│   ├── logging_config.py  # Logger estructurado
│   │
│   ├── models/
│   │   ├── database.py    # Conexión y tablas SQLite
│   │   └── schemas.py     # Pydantic schemas
│   │
│   ├── rules/
│   │   ├── keywords.py    # Keywords centralizados
│   │   └── business_guardrails.py  # Guardrails anti-abuso
│   │
│   ├── services/
│   │   ├── asset_service.py     # Catálogo y assets
│   │   ├── cache_service.py     # Cache LRU in-memory
│   │   ├── context_service.py   # Extracción de contexto
│   │   ├── handoff_service.py   # Handoff y notificaciones
│   │   ├── intent_service.py    # Wrapper intenciones
│   │   ├── response_service.py  # Generación respuestas + OpenAI
│   │   ├── trace_service.py     # Trazabilidad
│   │   └── whatsapp_service.py  # WhatsApp Cloud API
│   │
│   ├── routers/
│   │   ├── api.py         # Endpoints /api/*
│   │   └── whatsapp.py    # Webhook WhatsApp
│   │
│   └── prompts/
│       └── luisa_system_prompt_v1.txt  # Prompt OpenAI versionado
│
├── assets/
│   └── catalog/           # Assets del catálogo
│
└── tests/                 # Tests unitarios
```

## 📦 Instalación

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## ⚙️ Configuración

Crear archivo `.env` en `backend/`:

```bash
# Mínimo para demo local
LUISA_API_KEY=demo-key

# Para habilitar OpenAI
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-your-key-here

# Para habilitar WhatsApp
WHATSAPP_ENABLED=true
WHATSAPP_VERIFY_TOKEN=tu-token
WHATSAPP_ACCESS_TOKEN=tu-access-token
WHATSAPP_PHONE_NUMBER_ID=tu-phone-id
TEST_NOTIFY_NUMBER=+573142156486
```

## 🏃 Ejecución

### Demo Local (sin WhatsApp ni OpenAI)

```bash
cd backend
source venv/bin/activate
python main.py
```

El servidor estará en `http://localhost:8000`.

### Con OpenAI Habilitado

```bash
export OPENAI_ENABLED=true
export OPENAI_API_KEY=sk-your-key
python main.py
```

### Con WhatsApp Habilitado

```bash
export WHATSAPP_ENABLED=true
export WHATSAPP_VERIFY_TOKEN=tu-token
export WHATSAPP_ACCESS_TOKEN=tu-access-token
export WHATSAPP_PHONE_NUMBER_ID=tu-phone-id
python main.py
```

## 🔌 Endpoints

### API Principal

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/chat` | Enviar mensaje y recibir respuesta |
| GET | `/api/catalog/items` | Listar items del catálogo |
| GET | `/api/assets/{image_id}` | Obtener imagen/video |
| GET | `/api/handoffs` | Ver handoffs pendientes |
| GET | `/api/cache/stats` | Estadísticas del cache |
| GET | `/health` | Health check |

### WhatsApp (si está habilitado)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/whatsapp/webhook` | Verificación de webhook |
| POST | `/whatsapp/webhook` | Recibir mensajes |

## 🧪 Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

Tests disponibles:
- `test_guardrails.py`: Verifica que preguntas fuera del negocio no llamen OpenAI
- `test_cache.py`: Cache LRU funciona correctamente
- `test_routing.py`: Routing comercial vs técnico
- `test_shadow_mode.py`: Modo sombra silencia respuestas
- `test_assets.py`: Servicio de assets
- `test_conversation_smoke.py`: Smoke tests de /api/chat

## 📊 Trazabilidad

Las trazas se guardan en `interaction_traces`:

| Campo | Descripción |
|-------|-------------|
| request_id | ID único de la interacción |
| conversation_id | ID de la conversación |
| channel | "api" o "whatsapp" |
| business_related | Si es consulta del negocio |
| intent | Intención detectada |
| routed_team | Equipo de handoff |
| openai_called | Si se llamó a OpenAI |
| cache_hit | Si hubo cache hit |
| latency_ms | Latencia en ms |

Ver trazas:
```bash
sqlite3 luisa.db "SELECT * FROM interaction_traces ORDER BY created_at DESC LIMIT 10;"
```

## 📱 Notificaciones Internas

Formato de notificaciones (en español, sin anglicismos):

```
💰 ATENCIÓN COMERCIAL

Cliente: Juan Pérez
Número: +57 314 215 6486

Resumen del caso:
• Último mensaje: "quiero comprar una máquina industrial"
• Busca máquina industrial
• Para fabricar: gorras
• Ubicación: Bogotá
• Etapa: Listo para decidir

Siguiente paso recomendado:
Coordinar envío e instalación a Bogotá
```

## 🛡️ Guardrails

El sistema protege contra:
- Preguntas fuera del negocio (programación, medicina, etc.)
- Consultas sensibles (datos personales, pagos)
- Abuso de tokens de OpenAI

Respuesta para mensajes fuera del negocio:
> "Hola 😊 Yo te ayudo con máquinas de coser, repuestos, servicio técnico y asesoría del Sastre. ¿Qué necesitas sobre eso?"

## 📝 Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| OPENAI_ENABLED | false | Habilitar OpenAI |
| OPENAI_API_KEY | - | API key de OpenAI |
| OPENAI_MODEL | gpt-4o-mini | Modelo a usar |
| OPENAI_MAX_OUTPUT_TOKENS | 180 | Límite de tokens |
| WHATSAPP_ENABLED | false | Habilitar WhatsApp |
| WHATSAPP_VERIFY_TOKEN | - | Token de verificación |
| CACHE_ENABLED | true | Habilitar cache |
| CACHE_MAX_SIZE | 200 | Tamaño máximo cache |
| HUMAN_TTL_HOURS | 12 | Horas de modo sombra |
| LOG_FORMAT | json | "json" o "text" |

## 🔄 Modo Sombra

Cuando se hace handoff:
1. LUISA envía notificación interna
2. Marca conversación como `HUMAN_ACTIVE`
3. LUISA deja de responder automáticamente
4. Solo registra mensajes
5. Después de `HUMAN_TTL_HOURS` sin actividad, vuelve a `AI_ACTIVE`

## 📈 Monitoreo

### Health Check
```bash
curl http://localhost:8000/health
```

### Cache Stats
```bash
curl http://localhost:8000/api/cache/stats
```

### Logs Estructurados
```bash
# En producción (JSON)
LOG_FORMAT=json python main.py 2>&1 | jq .

# En desarrollo (texto)
LOG_FORMAT=text python main.py
```

## 🚀 Guías de Configuración

### Habilitar OpenAI

```bash
# 1. Obtener API key de OpenAI
# Ve a https://platform.openai.com/api-keys

# 2. Configurar variables
export OPENAI_ENABLED=true
export OPENAI_API_KEY=sk-proj-tu-api-key-aqui

# 3. Reiniciar servidor
cd backend && python main.py
```

**Nota**: Nunca hardcodees la API key en el código.

### Habilitar WhatsApp

```bash
# 1. Crear app en Facebook Developers
# Ve a https://developers.facebook.com/apps/

# 2. Configurar Webhooks para WhatsApp
# - Callback URL: https://tu-dominio.com/whatsapp/webhook
# - Verify Token: tu-token-secreto

# 3. Configurar variables
export WHATSAPP_ENABLED=true
export WHATSAPP_VERIFY_TOKEN=tu-token-secreto
export WHATSAPP_ACCESS_TOKEN=tu-access-token
export WHATSAPP_PHONE_NUMBER_ID=tu-phone-number-id

# 4. Reiniciar servidor
cd backend && python main.py
```

### Verificar Configuración

```bash
# Health check
curl http://localhost:8000/health

# Debe mostrar:
{
  "modules": {
    "new_modules": true,
    "whatsapp": true,    // si está habilitado
    "openai": true,      // si está habilitado
    "cache": true
  }
}
```

