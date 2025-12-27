# LUISA Agentic Commerce

Production-ready commercial + technical assistant for **Almacén y Taller El Sastre**. It handles intent routing, guarded LLM usage, visual catalog matching, human handoff, and full interaction tracing.

## What is LUISA?
LUISA is an AI-driven sales and support agent that chats with customers, recommends sewing machines and services, and escalates to humans when needed. It runs with strong guardrails, deterministic rules, and full traceability for compliance and cost control.

## Key Features
- **WhatsApp Cloud API**: inbound webhook + outbound replies; internal notifications to humans.
- **OpenAI (optional, guarded)**: only for business consults; strict gating, timeouts, and cost controls.
- **Human handoffs**: internal WhatsApp notification + `HUMAN_ACTIVE` shadow mode to silence bot.
- **Visual catalog**: local assets or Drive proxy; deterministic selection by intent/context.
- **Cache & traces**: in-memory cache for FAQs; SQLite `interaction_traces` with decision_path and latency.
- **Closed-question post-processor**: ensures every informative reply ends with a clear next step.

## Project Structure (backend-focused)
```
Sastre/
├── backend/
│   ├── app/                # Modular code (config, models, rules, services, routers, prompts)
│   ├── assets/             # Local catalog (images + metadata)
│   ├── scripts/            # Utilities (init_db, analyze_traces, go_no_go, etc.)
│   ├── tests/              # Automated tests
│   └── main.py             # Legacy entrypoint adapter
├── frontend/               # Minimal demo UI (file:// ready)
├── .env.example            # Environment template (no secrets)
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
```
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=8
OPENAI_MAX_INPUT_CHARS=1200
```
Guardrails block non-business, FAQs, greetings, and gibberish before calling OpenAI.

## Enable WhatsApp (Cloud API)
In `.env`:
```
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=EAA...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=your-webhook-verify
TEST_NOTIFY_NUMBER=+57XXXXXXXXXX   # internal notifications
```
Webhook:
- Expose `/whatsapp/webhook` (GET for verify, POST for messages).
- Configure the verify token in Meta; we rate-limit per phone (20/min).

## Scripts
- `python scripts/analyze_traces.py` — Markdown report of last traces (cost, routing, quality).
- `python scripts/go_no_go.py` — Health + chat scenarios + trace growth for pre-release checks.

## Security Notes
- Never commit secrets or DBs. `.env` is gitignored; use `.env.example` as reference.
- Masked logging: phone numbers are masked; PII and tokens are not logged.
- PRODUCTION_MODE=true forces JSON logs and reduces verbosity.

## License
MIT (see `LICENSE`).
