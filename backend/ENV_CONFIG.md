# Configuración de Variables de Entorno

## Variables Disponibles

### API
```bash
API_HOST=0.0.0.0
API_PORT=8000
LUISA_API_KEY=demo-key-change-in-production
```

### OpenAI (opcional)
```bash
OPENAI_ENABLED=false
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=180
OPENAI_TEMPERATURE=0.4
OPENAI_TIMEOUT_SECONDS=8
```

### WhatsApp Cloud API (opcional)
```bash
WHATSAPP_ENABLED=false
WHATSAPP_VERIFY_TOKEN=luisa-verify-token-2024
WHATSAPP_ACCESS_TOKEN=your-whatsapp-access-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
WHATSAPP_API_VERSION=v18.0
TEST_NOTIFY_NUMBER=+573142156486
```

### Modo Sombra
```bash
HUMAN_TTL_HOURS=12
HANDOFF_SILENCE_MINUTES=30
```

### Cache
```bash
CACHE_ENABLED=true
CACHE_MAX_SIZE=200
CACHE_TTL_HOURS=12
```

### Feature Flags
```bash
FEATURE_NEW_ARCHITECTURE=true
FEATURE_TRACES_ENABLED=true
```

## Cómo Configurar

1. Crea un archivo `.env` en `backend/`
2. Agrega las variables que necesites
3. Reinicia el servidor

## Ejemplos de Uso

### Solo Demo (sin OpenAI ni WhatsApp)
```bash
# No se requiere .env, usa defaults
```

### Con OpenAI Habilitado
```bash
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-proj-...
```

### Con WhatsApp Habilitado
```bash
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=EAAG...
WHATSAPP_PHONE_NUMBER_ID=123456789
```

