# LUISA Agentic Commerce

Production-ready commercial + technical assistant for **Almacén y Taller El Sastre**. It handles intent routing, guarded LLM usage, visual catalog matching, human handoff, and full interaction tracing.

## What is LUISA?
LUISA is an AI-driven sales and support agent that chats with customers, recommends sewing machines and services, and escalates to humans when needed. It runs with strong guardrails, deterministic rules, and full traceability for compliance and cost control.

**LUISA is not a chatbot.** It is an agentic commerce system designed to operate safely in production, with humans in the loop and full decision traceability.

## Key Features
- **WhatsApp Cloud API**: inbound webhook + outbound replies; internal notifications to humans.
- **OpenAI (optional, guarded)**: only for business consults; strict gating, timeouts, and cost controls.
- **Human handoffs**: internal WhatsApp notification + `HUMAN_ACTIVE` shadow mode to silence bot.
- **Visual catalog**: local assets or Drive proxy; deterministic selection by intent/context.
- **Cache & traces**: in-memory cache for FAQs; SQLite `interaction_traces` with decision_path and latency.
- **Closed-question post-processor**: ensures every informative reply ends with a clear next step.

## Architecture Overview

### Message Processing Pipeline
```
Incoming Message
    ↓
1. Rate Limiting (per conversation_id/phone)
    ↓
2. Message Classification (EMPTY_OR_GIBBERISH | NON_BUSINESS | BUSINESS_FAQ | BUSINESS_CONSULT)
    ↓
3. Business Guardrails (is_business_related check)
    ↓
4. Cache Check (LRU, TTL=12h, max_size=200)
    ↓
5. Intent Analysis (deterministic keyword matching + context extraction)
    ↓
6. Context Extraction (tipo_maquina, uso, volumen, ciudad, marca_interes)
    ↓
7. Handoff Detection (should_handoff rules → Team.COMERCIAL | Team.TECNICA)
    ↓
8. Asset Selection (deterministic catalog matching by intent + context)
    ↓
9. Response Generation:
    ├─ Cache Hit → Return cached
    ├─ Deterministic Rules → Return rule-based response
    └─ OpenAI (if BUSINESS_CONSULT + no robust deterministic) → Generate with guardrails
    ↓
10. Post-processing (ensure_next_step_question: add closed question if missing)
    ↓
11. Trace Persistence (interaction_traces table with decision_path, latency_ms, message_type)
    ↓
12. Shadow Mode Check (if HUMAN_ACTIVE → silence bot, only log)
    ↓
Response Sent
```

### Core Components

#### 1. **Intent Service** (`app/services/intent_service.py`)
- Wraps legacy `intent_analyzer.py` sub-agent
- Returns: `{intent, confidence, entities}`
- Intents: `saludo`, `buscar_maquina_industrial`, `buscar_maquina_familiar`, `envios`, `pagos`, `repuestos`, `asesoria_negocio`, etc.

#### 2. **Context Service** (`app/services/context_service.py`)
- Extracts conversational context from last 12 messages
- Tracks: `tipo_maquina`, `uso`, `volumen`, `ciudad`, `marca_interes`, `modelo_interes`
- Used for progressive narrowing (reduce options as conversation advances)

#### 3. **Business Guardrails** (`app/rules/business_guardrails.py`)
- **Message Classification**: `EMPTY_OR_GIBBERISH`, `NON_BUSINESS`, `BUSINESS_FAQ`, `BUSINESS_CONSULT`
- **Blacklist**: non-business keywords (python, javascript, código, tarea, universidad, etc.)
- **Response for NON_BUSINESS**: fixed redirection message (no OpenAI call)

#### 4. **OpenAI Gating** (`app/services/response_service.py::should_call_openai`)
OpenAI is called **ONLY** if:
- `OPENAI_ENABLED == true`
- `message_type == BUSINESS_CONSULT`
- `intent NOT IN {saludo, despedida, envios, pagos, horarios, direccion, ubicacion}` (simple FAQs)
- `cache_hit == false`
- No robust deterministic response available
- Input limited to `OPENAI_MAX_INPUT_CHARS` (default: 1200)
- History limited to last 6 turns
- Timeout: `OPENAI_TIMEOUT_SECONDS` (default: 8s)

#### 5. **Handoff Service** (`app/services/handoff_service.py`)
- **Rules-based routing** to `Team.COMERCIAL` or `Team.TECNICA`
- Triggers on: urgent keywords, payment confirmations, city mentions, repair requests, installation needs
- **Internal notification** sent via WhatsApp to `TEST_NOTIFY_NUMBER`
- **Shadow mode activation**: sets `conversation_mode = HUMAN_ACTIVE` (TTL: 12h)
- Bot silenced when `HUMAN_ACTIVE` is active

#### 6. **Trace Service** (`app/services/trace_service.py`)
- Persists every interaction to `interaction_traces` table
- Fields: `request_id`, `conversation_id`, `message_type`, `intent`, `routed_team`, `openai_called`, `cache_hit`, `decision_path`, `latency_ms`, `latency_us`, `response_len_chars`
- **Decision Path**: e.g., `msg_business_consult->cache_miss->asset_selected->openai_called_fallback->question_appended`
- Used for cost audit, quality analysis, and debugging

#### 7. **Cache Service** (`app/services/cache_service.py`)
- **LRU cache** (max_size=200, TTL=12h)
- Only caches safe FAQs (horarios, direccion, envios, pagos)
- In-memory (no Redis dependency)

#### 8. **Rate Limiting** (`app/services/rate_limit.py`)
- **In-memory** rate limiter (no Redis)
- `/api/chat`: 30 requests/min per `conversation_id`
- `/whatsapp/webhook`: 20 requests/min per phone number
- Returns `429 Too Many Requests` when exceeded

### Database Schema

**Key Tables:**
- `conversations`: conversation metadata + `conversation_mode` (AI_ACTIVE | HUMAN_ACTIVE)
- `messages`: full message history
- `interaction_traces`: detailed interaction metadata (decision_path, latency, openai_called, etc.)
- `handoffs`: escalation records with team, priority, reason
- `notifications`: internal WhatsApp notifications sent
- `catalog_items`: product catalog metadata

## Project Structure
```
Sastre/
├── backend/
│   ├── app/
│   │   ├── config.py              # Centralized config (env vars)
│   │   ├── logging_config.py      # Structured JSON/text logging
│   │   ├── models/
│   │   │   ├── database.py        # SQLite connection + schema
│   │   │   └── schemas.py        # Pydantic models
│   │   ├── rules/
│   │   │   ├── keywords.py        # Centralized keyword sets
│   │   │   └── business_guardrails.py  # Message classification + guardrails
│   │   ├── services/
│   │   │   ├── asset_service.py   # Catalog asset selection
│   │   │   ├── cache_service.py   # LRU cache for FAQs
│   │   │   ├── context_service.py # Context extraction from history
│   │   │   ├── handoff_service.py # Handoff rules + notifications
│   │   │   ├── intent_service.py  # Intent analysis wrapper
│   │   │   ├── rate_limit.py      # In-memory rate limiting
│   │   │   ├── response_service.py # Main response pipeline + OpenAI
│   │   │   ├── trace_service.py   # Interaction tracing
│   │   │   └── whatsapp_service.py # WhatsApp Cloud API client
│   │   ├── routers/
│   │   │   ├── api.py             # /api/chat, /api/catalog, /health
│   │   │   └── whatsapp.py        # /whatsapp/webhook
│   │   └── prompts/
│   │       └── luisa_system_prompt_v1.txt  # Versioned OpenAI prompt
│   ├── assets/
│   │   └── catalog/               # Local catalog (IXXX_slug/image_1.png + meta.json)
│   ├── scripts/
│   │   ├── init_db.py             # Initialize SQLite schema
│   │   ├── analyze_traces.py     # Generate trace analysis report
│   │   └── go_no_go.py            # Pre-release health checks
│   ├── tests/                     # pytest test suite
│   └── main.py                    # Legacy entrypoint adapter
├── frontend/                      # Minimal demo UI (file:// ready)
├── .env.example                   # Environment template (no secrets)
└── CHANGELOG.md
```

## Quickstart (local, no WhatsApp/OpenAI)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env    # keep defaults (OPENAI_ENABLED=false, WHATSAPP_ENABLED=false)
python scripts/init_db.py
python main.py             # http://localhost:8000

# Frontend (optional demo)
cd ../frontend
open index.html            # or python3 -m http.server 8080
```

## Enable OpenAI (optional)
Set in `.env`:
```bash
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=180
OPENAI_TEMPERATURE=0.4
OPENAI_TIMEOUT_SECONDS=8
OPENAI_MAX_INPUT_CHARS=1200
```

**Guardrails:**
- Non-business messages → fixed response (no OpenAI call)
- Simple FAQs (horarios, direccion, envios) → deterministic rules (no OpenAI call)
- Greetings/gibberish → fixed response (no OpenAI call)
- Only `BUSINESS_CONSULT` messages with no robust deterministic response → OpenAI call

## Enable WhatsApp (Cloud API)
In `.env`:
```bash
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=EAA...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=your-webhook-verify
TEST_NOTIFY_NUMBER=+57XXXXXXXXXX   # internal notifications
```

**Webhook Setup:**
1. Expose `/whatsapp/webhook` publicly (use ngrok for testing)
2. Configure verify token in Meta Business Dashboard
3. Rate limiting: 20 requests/min per phone number

**Internal Notifications:**
- Format: `💰 ATENCIÓN COMERCIAL` or `⚙️ ATENCIÓN TÉCNICA`
- Sent to `TEST_NOTIFY_NUMBER` when handoff triggered
- Includes: customer phone (masked), summary bullets, next step suggestion

## Scripts

### Analyze Traces
```bash
cd backend
python scripts/analyze_traces.py
```
Generates `trace_analysis_report.md` with:
- Cost audit (OpenAI usage breakdown)
- Conversation quality metrics (responses without closed questions, length analysis)
- Routing analysis (top routed teams, false positives)
- Asset matching accuracy
- Latency statistics (avg, median, p95)

### Go/No-Go Pre-Release Check
```bash
cd backend
python scripts/go_no_go.py
```
Runs automated health checks:
- `GET /health` validation
- Chat scenarios (saludo, non-business, FAQ, industrial query, handoff)
- Trace growth validation
- Decision path flag verification

## Security & Production

### Rate Limiting
- **In-memory** (no Redis dependency)
- `/api/chat`: 30 req/min per `conversation_id`
- `/whatsapp/webhook`: 20 req/min per phone number
- Returns `429 Too Many Requests` when exceeded

### Logging
- **Masked PII**: phone numbers show only last 4 digits
- **No secrets logged**: API keys, tokens never appear in logs
- **Structured logs**: JSON format when `PRODUCTION_MODE=true`
- **Log levels**: DEBUG (dev) → INFO (prod)

### Shadow Mode
- When handoff triggered → `conversation_mode = HUMAN_ACTIVE`
- Bot silenced: messages logged but no automatic responses
- TTL: 12 hours (configurable via `HUMAN_TTL_HOURS`)
- Human can manually set back to `AI_ACTIVE` via API

### Production Mode
Set `PRODUCTION_MODE=true` in `.env`:
- Forces JSON logs
- Reduces DEBUG verbosity
- Blocks dangerous endpoints (if any)

## Security Notes
- **Never commit secrets**: `.env` is gitignored; use `.env.example` as reference
- **Masked logging**: phone numbers are masked; PII and tokens are not logged
- **Rate limiting**: prevents abuse on public endpoints
- **Input sanitization**: OpenAI input limited to 1200 chars; history limited to 6 turns
- **Timeout protection**: OpenAI calls timeout at 8s; WhatsApp sends timeout at 8s with 2 retries

## Testing
```bash
cd backend
pytest tests/ -v
```

**Test Coverage:**
- Guardrails (non-business blocking)
- Cache (LRU, TTL)
- Rate limiting
- Shadow mode (HUMAN_ACTIVE)
- Asset selection
- Routing (handoff triggers)
- Conversation smoke tests

## License
MIT (see `LICENSE`).
