# LUISA - Agentic Commerce Assistant

Production-ready AI assistant for **Almacén y Taller El Sastre** (Montería, Colombia). LUISA handles customer inquiries via WhatsApp, provides product recommendations, and escalates to human agents when needed.

## Overview

LUISA is an agentic commerce system that combines:
- **Deterministic rules** for fast, reliable responses
- **Guarded LLM usage** (OpenAI) for complex scenarios only
- **Full traceability** for cost control and compliance
- **Human-in-the-loop** handoff system with shadow mode

**Key Principle**: LUISA never stays silent. Even in shadow mode, it responds with courteous messages to maintain engagement.

## Quick Start

### Local Development

```bash
# 1. Clone repository
git clone <repository-url>
cd Sastre

# 2. Setup backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp ../.env.example .env
# Edit .env with your settings (defaults work for local dev)

# 4. Initialize database
python scripts/init_db.py

# 5. Start server
python main.py
# Server runs on http://localhost:8000
```

### Production Deployment

See [docs/deployment/DEPLOYMENT_AND_CONFIGURATION.md](docs/deployment/DEPLOYMENT_AND_CONFIGURATION.md) for complete deployment guide.

**Quick deploy with Docker:**
```bash
docker compose up -d
```

## Features

### Core Capabilities

- **WhatsApp Integration**: Cloud API webhook for receiving and sending messages
- **Intent Classification**: Detects user intent (greeting, product search, support, etc.)
- **Context Extraction**: Tracks conversation context (machine type, usage, location)
- **Product Catalog**: Visual catalog matching with asset serving
- **Handoff System**: Automatic escalation to human agents (commercial/technical teams)
- **Shadow Mode**: `HUMAN_ACTIVE` mode with TTL (auto-revert after 12 hours)
- **Full Tracing**: Every interaction logged with decision path and latency

### Guardrails & Safety

- **Business Guardrails**: Blocks non-business messages (programming, tasks, etc.)
- **OpenAI Gating**: Only calls OpenAI for complex business consultations
- **Rate Limiting**: 20 req/min (WhatsApp), 30 req/min (API) per conversation
- **Cost Control**: Tracks OpenAI usage, limits input/output tokens
- **Timeout Protection**: 8s timeout for OpenAI calls, graceful fallback

## Configuration

### Environment Variables

**Required for WhatsApp:**
```bash
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=EAA...          # From Meta Business Dashboard
WHATSAPP_PHONE_NUMBER_ID=...          # From Meta Business Dashboard
WHATSAPP_VERIFY_TOKEN=secure-token   # Must match Meta dashboard
TEST_NOTIFY_NUMBER=+57XXXXXXXXXX      # Internal notifications
```

**Optional for OpenAI:**
```bash
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=180
OPENAI_TIMEOUT_SECONDS=8
```

**Shadow Mode:**
```bash
HUMAN_TTL_HOURS=12                   # Hours before reverting HUMAN_ACTIVE
HANDOFF_COOLDOWN_MINUTES=30          # Cooldown after handoff
```

**Silent Mode for Personal Messages:**
```bash
PERSONAL_MESSAGES_MODE=silent        # silent | polite (default: silent)
ENHANCED_FILTERING_WITH_LLM=true     # Use LLM for ambiguous cases (default: true)
```

**Business Hours (Optional):**
```bash
BUSINESS_HOURS_ENABLED=false         # Enable working hours filter (default: false)
BUSINESS_HOURS_START=8               # Start hour (8am)
BUSINESS_HOURS_END=21                # End hour (9pm)
BUSINESS_HOURS_NEW_CONVERSATION_CUTOFF=18  # Cutoff for new conversations (6pm)
```

See `.env.example` for complete configuration reference.

## Operations

### Observability

**Ops Snapshot Endpoint:**
```bash
curl http://localhost:8000/ops/snapshot | jq
```

Returns metrics for last 60 minutes:
- `total_msgs_60m`: Total messages processed
- `pct_personal`: % personal messages (filtering effectiveness)
- `pct_handoff`: % handoffs (escalation rate)
- `pct_openai`: % OpenAI calls (cost indicator)
- `errores_count`: Error count
- `p95_latency_ms`: 95th percentile latency

**CLI Script:**
```bash
python backend/scripts/ops_snapshot.py
```

### Pre-Deployment Checks

**Run go_no_go suite:**
```bash
python backend/scripts/go_no_go.py --hard-fail
```

Validates:
- Health endpoint
- Greeting responses
- Non-business message filtering
- FAQ responses (with cache)
- Asset selection
- Handoff flow
- OpenAI usage (if enabled)

**Hard-fail checks:** Health, greeting, non-business, FAQ (blocks deploy if fail)
**Warning checks:** Asset, handoff, OpenAI (warns but doesn't block)

### End-to-End WhatsApp Test

1. **Verify webhook configured in Meta Dashboard:**
   - URL: `https://luisa-agent.online/whatsapp/webhook`
   - Verify Token: Must match `WHATSAPP_VERIFY_TOKEN` in `.env`
   - Subscription: `messages` field enabled

2. **Send test message:**
   - From test number: "hola"
   - Expected: LUISA responds with greeting

3. **Verify in database:**
   ```bash
   docker compose exec backend sqlite3 /app/data/luisa.db "
   SELECT classification, classification_score, response_text, whatsapp_send_success
   FROM interaction_traces 
   WHERE created_at > datetime('now', '-5 minutes')
   ORDER BY id DESC LIMIT 1;
   "
   ```

4. **Check logs:**
   ```bash
   docker compose logs backend | grep -E "message_received|whatsapp_send_success"
   ```

See [docs/OPERATIONS_AND_TRADEOFFS.md](docs/OPERATIONS_AND_TRADEOFFS.md) for architecture decisions and trade-offs.

## Features

### Silent Mode for Personal Messages

LUISA automatically distinguishes between business and personal messages:

- **Business Messages**: Bot responds normally with full assistance
- **Personal Messages**: Bot stays silent (Carmen can respond manually)
- **Zero Friction**: Works automatically without configuration
- **Enhanced Filtering**: Uses LLM (gpt-4o-mini) for ambiguous cases

This is especially useful when using a personal WhatsApp number for business. See [docs/deployment/SOLUCION_NUMERO_PERSONAL_CARMEN.md](docs/deployment/SOLUCION_NUMERO_PERSONAL_CARMEN.md) for details.

### Business Hours (Optional)

Optional working hours filter:

- **Working Hours**: 8am - 9pm (configurable)
- **New Conversation Cutoff**: 6pm (no new conversations after this time)
- **Message Queuing**: Messages outside hours get automatic response
- **Continuation**: Existing conversations can continue until closing time

Configure with `BUSINESS_HOURS_ENABLED=true` in `.env`.

## Architecture

### Message Processing Flow

```
WhatsApp Message
    ↓
Rate Limiting
    ↓
Message Classification (EMPTY | NON_BUSINESS | BUSINESS_FAQ | BUSINESS_CONSULT)
    ↓
Cache Check (if FAQ)
    ↓
Intent Analysis
    ↓
Context Extraction
    ↓
Handoff Detection
    ↓
Response Generation (Cache | Rules | OpenAI)
    ↓
Post-processing (ensure closed question)
    ↓
Trace Persistence
    ↓
Shadow Mode Check (HUMAN_ACTIVE with TTL)
    ↓
Send Response
```

### Key Components

- **Intent Service**: Analyzes user messages to determine intent
- **Context Service**: Extracts conversational context from history
- **Business Guardrails**: Classifies and filters non-business messages
- **Handoff Service**: Detects when human intervention is needed
- **Cache Service**: LRU cache for safe FAQs (in-memory)
- **Trace Service**: Persists every interaction for audit
- **Asset Service**: Manages product catalog and asset serving

For detailed architecture documentation, see [docs/development/ARCHITECTURE.md](docs/development/ARCHITECTURE.md).

## Project Structure

```
Sastre/
├── backend/
│   ├── app/                    # Main application
│   │   ├── config.py           # Configuration
│   │   ├── models/             # Database models
│   │   ├── routers/            # API routes
│   │   ├── services/           # Business logic
│   │   └── rules/              # Business rules
│   ├── assets/                 # Product catalog
│   ├── scripts/                # Utility scripts
│   └── tests/                  # Test suite
├── frontend/                   # Demo UI
├── docker-compose.yml          # Docker orchestration
├── Caddyfile                   # Reverse proxy config
└── .env.example                # Environment template
```

## Documentation

### Guías Principales

- **[DEPLOYMENT_AND_CONFIGURATION.md](DEPLOYMENT_AND_CONFIGURATION.md)**: Guía consolidada de despliegue, configuración y activación en producción
- **[docs/development/DEVELOPMENT_AND_TESTING.md](docs/development/DEVELOPMENT_AND_TESTING.md)**: Guía consolidada de desarrollo, implementación, diseño y pruebas

### Documentación Adicional

- **[docs/deployment/DEPLOYMENT_AND_CONFIGURATION.md](docs/deployment/DEPLOYMENT_AND_CONFIGURATION.md)**: Guía detallada de despliegue y configuración
- **[docs/development/ARCHITECTURE.md](docs/development/ARCHITECTURE.md)**: Arquitectura del sistema y diseño
- **[docs/development/TROUBLESHOOTING.md](docs/development/TROUBLESHOOTING.md)**: Solución de problemas comunes
- **[SECURITY.md](SECURITY.md)**: Mejores prácticas de seguridad
- **[CHANGELOG.md](CHANGELOG.md)**: Historial de versiones

## Scripts

### Analyze Traces
```bash
cd backend
python scripts/analyze_traces.py
```
Generates cost audit, quality metrics, and performance analysis.

### Go/No-Go Check
```bash
cd backend
python scripts/go_no_go.py
```
Runs automated health checks before deployment.

## Testing

```bash
cd backend
pytest tests/ -v
```

**Test Coverage:**
- Business guardrails
- Cache (LRU, TTL)
- Rate limiting
- Shadow mode (HUMAN_ACTIVE)
- Handoff triggers
- Conversation flows

## Recent Fixes

### FIX P0: Eliminate Silence
LUISA now responds with courteous messages even in `HUMAN_ACTIVE` mode, ensuring it never stays silent.

### FIX P1: TTL Auto-Revert
`HUMAN_ACTIVE` mode automatically reverts to `AI_ACTIVE` after `HUMAN_TTL_HOURS` (default: 12 hours).

## Security

- **Secrets**: Never committed (`.env` in `.gitignore`)
- **PII Masking**: Phone numbers show only last 4 digits in logs
- **Rate Limiting**: Prevents abuse on public endpoints
- **Input Validation**: Length limits, type checking
- **HTTPS**: Required in production (Caddy automatic SSL)

See [SECURITY.md](SECURITY.md) for detailed security guidelines.

## License

MIT License (see [LICENSE](LICENSE))

## Support

For deployment issues, see [docs/deployment/DEPLOYMENT_AND_CONFIGURATION.md](docs/deployment/DEPLOYMENT_AND_CONFIGURATION.md).  
For troubleshooting, see [docs/development/TROUBLESHOOTING.md](docs/development/TROUBLESHOOTING.md).

---

**Version**: 2.0.0  
**Last Updated**: 2025-01-XX
