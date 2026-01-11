# 🏗️ Architecture Documentation - LUISA

Complete technical architecture and system design documentation.

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Components](#core-components)
3. [Message Processing Pipeline](#message-processing-pipeline)
4. [Data Models](#data-models)
5. [Integration Points](#integration-points)
6. [SalesBrain System](#salesbrain-system)
7. [Handoff System](#handoff-system)
8. [Asset Management](#asset-management)

---

## System Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    WhatsApp Cloud API                        │
│                    (Meta Business)                          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ HTTPS Webhook
                        │
        ┌───────────────▼───────────────┐
        │      Caddy (Reverse Proxy)     │
        │    Port 80/443, Auto HTTPS    │
        └───────────────┬───────────────┘
                        │
                        │ localhost:8000
                        │
        ┌───────────────▼───────────────┐
        │    FastAPI Backend (Python)   │
        │  ┌─────────────────────────┐  │
        │  │  WhatsApp Router         │  │
        │  │  /whatsapp/webhook       │  │
        │  └───────────┬─────────────┘  │
        │              │                 │
        │  ┌───────────▼─────────────┐  │
        │  │  Message Processor       │  │
        │  │  - Intent Analysis       │  │
        │  │  - Context Extraction    │  │
        │  │  - Handoff Detection     │  │
        │  │  - Response Generation   │  │
        │  └───────────┬─────────────┘  │
        │              │                 │
        │  ┌───────────▼─────────────┐  │
        │  │  Services Layer          │  │
        │  │  - SalesBrain            │  │
        │  │  - Handoff Service       │  │
        │  │  - Asset Service         │  │
        │  │  - Cache Service         │  │
        │  └───────────┬─────────────┘  │
        │              │                 │
        │  ┌───────────▼─────────────┐  │
        │  │  SQLite Database         │  │
        │  │  - conversations         │  │
        │  │  - messages              │  │
        │  │  - interaction_traces    │  │
        │  │  - handoffs              │  │
        │  └─────────────────────────┘  │
        └─────────────────────────────────┘
```

### Technology Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: SQLite 3 (with WAL mode for concurrency)
- **Reverse Proxy**: Caddy 2 (automatic HTTPS)
- **Containerization**: Docker + Docker Compose
- **LLM Integration**: OpenAI API (optional, guarded)
- **Messaging**: WhatsApp Cloud API (Meta)

---

## Core Components

### 1. Intent Service

**Location**: `backend/app/services/intent_service.py`

**Purpose**: Analyzes user messages to determine intent and extract entities.

**Intents Supported**:
- `saludo` - Greetings
- `buscar_maquina_industrial` - Industrial machine search
- `buscar_maquina_familiar` - Home machine search
- `envios` - Shipping inquiries
- `pagos` - Payment inquiries
- `repuestos` - Parts inquiries
- `asesoria_negocio` - Business consultation

**Returns**:
```python
{
    "intent": "buscar_maquina_industrial",
    "confidence": 0.85,
    "entities": {"tipo": "industrial", "uso": "produccion"}
}
```

### 2. Context Service

**Location**: `backend/app/services/context_service.py`

**Purpose**: Extracts conversational context from message history.

**Context Slots**:
- `tipo_maquina` - Machine type (industrial/familiar)
- `uso` - Use case (produccion, arreglos, proyectos)
- `volumen` - Production volume
- `ciudad` - City/location
- `marca_interes` - Brand interest
- `modelo_interes` - Model interest

**Usage**: Progressive narrowing - reduces options as conversation advances.

### 3. Business Guardrails

**Location**: `backend/app/rules/business_guardrails.py`

**Purpose**: Classifies messages and blocks non-business content.

**Message Types**:
- `EMPTY_OR_GIBBERISH` - Empty or meaningless messages
- `NON_BUSINESS` - Off-topic (programming, tasks, etc.)
- `BUSINESS_FAQ` - Simple business FAQs (horarios, direccion)
- `BUSINESS_CONSULT` - Complex business consultations

**Blacklist**: Non-business keywords (python, javascript, código, tarea, universidad, etc.)

### 4. Handoff Service

**Location**: `backend/app/services/handoff_service.py`

**Purpose**: Detects when human intervention is needed and routes to appropriate team.

**Handoff Triggers**:
- **URGENT**: Critical problems → `Team.TECNICA`, `Priority.URGENT`
- **PROBLEMS**: Complaints/returns → `Team.COMERCIAL`, `Priority.HIGH`
- **BUSINESS_IMPACT**: Business projects → `Team.COMERCIAL`, `Priority.HIGH`
- **DIFFERENTIAL_SERVICE**: Installation/visit → `Team.TECNICA`, `Priority.HIGH`
- **GEOGRAPHIC**: City outside Montería → `Team.COMERCIAL`, `Priority.MEDIUM`

**Actions**:
1. Sends internal WhatsApp notification to `TEST_NOTIFY_NUMBER`
2. Sets `conversation_mode = HUMAN_ACTIVE` (with TTL: 12 hours)
3. Logs handoff in database

### 5. Cache Service

**Location**: `backend/app/services/cache_service.py`

**Purpose**: In-memory LRU cache for safe FAQs.

**Configuration**:
- Max size: 200 entries
- TTL: 12 hours
- Only caches: horarios, direccion, envios, pagos, catalogo

**Cacheable Intents**: Configurable via `OPENAI_CACHEABLE_INTENTS` env var.

### 6. Trace Service

**Location**: `backend/app/services/trace_service.py`

**Purpose**: Persists every interaction for audit, cost control, and debugging.

**Fields Tracked**:
- `request_id` - Unique request identifier
- `conversation_id` - Conversation identifier
- `message_type` - Message classification
- `intent` - Detected intent
- `routed_team` - Team routed to (if handoff)
- `openai_called` - Whether OpenAI was called
- `cache_hit` - Whether cache was used
- `decision_path` - Full decision path (e.g., `msg_business_consult->cache_miss->openai_called`)
- `latency_ms` - Response latency in milliseconds
- `response_len_chars` - Response length

---

## Message Processing Pipeline

### Complete Flow

```
1. Incoming Message (WhatsApp/API)
   ↓
2. Rate Limiting Check
   - WhatsApp: 20 req/min per phone
   - API: 30 req/min per conversation_id
   ↓
3. Message Classification
   - EMPTY_OR_GIBBERISH → Fixed response
   - NON_BUSINESS → Fixed redirect message
   - BUSINESS_FAQ → Continue to cache/FAQs
   - BUSINESS_CONSULT → Continue to full pipeline
   ↓
4. Cache Check (if BUSINESS_FAQ)
   - Cache hit → Return cached response
   - Cache miss → Continue
   ↓
5. Intent Analysis
   - Deterministic keyword matching
   - Context extraction from history
   ↓
6. Context Extraction
   - Extract slots from last 12 messages
   - Build context object
   ↓
7. Handoff Detection
   - Check should_handoff() rules
   - If handoff → Route to team, set HUMAN_ACTIVE
   ↓
8. Asset Selection (if applicable)
   - Match catalog items by intent + context
   - Select best matching asset
   ↓
9. Response Generation
   ├─ Cache Hit → Return cached
   ├─ Deterministic Rules → Return rule-based
   └─ OpenAI (if BUSINESS_CONSULT + no robust deterministic)
      ↓
10. Post-processing
    - Ensure closed question (add if missing)
    - Humanize response (optional)
    ↓
11. Trace Persistence
    - Save to interaction_traces table
    - Include decision_path, latency, costs
    ↓
12. Shadow Mode Check
    - If HUMAN_ACTIVE → Send courteous response (FIX P0)
    - Check TTL → Revert to AI_ACTIVE if expired (FIX P1)
    ↓
13. Send Response
```

### Key Decision Points

**OpenAI Gating** (`should_call_openai`):
- ✅ `message_type == BUSINESS_CONSULT`
- ✅ `intent NOT IN {saludo, despedida, envios, pagos, horarios, direccion}`
- ✅ `cache_hit == false`
- ✅ No robust deterministic response available
- ✅ `OPENAI_ENABLED == true`
- ✅ Input < 1200 chars, history < 6 turns

**Handoff Triggering** (`should_handoff`):
- Urgent keywords → `Team.TECNICA`
- Problem keywords → `Team.COMERCIAL`
- Business impact keywords → `Team.COMERCIAL`
- Service keywords → `Team.TECNICA`
- Geographic keywords → `Team.COMERCIAL`

---

## Data Models

### Database Schema

#### `conversations`
```sql
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    customer_phone TEXT,
    customer_name TEXT,
    status TEXT DEFAULT 'active',
    conversation_mode TEXT DEFAULT 'AI_ACTIVE',  -- AI_ACTIVE | HUMAN_ACTIVE
    mode_updated_at TIMESTAMP,                   -- For TTL calculation
    channel TEXT DEFAULT 'api',                  -- api | whatsapp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `messages`
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,
    text TEXT,
    sender TEXT,                                -- customer | luisa
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);
```

#### `interaction_traces`
```sql
CREATE TABLE interaction_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    conversation_id TEXT,
    channel TEXT,
    customer_phone_hash TEXT,                    -- SHA-256 hash
    raw_text TEXT,
    normalized_text TEXT,
    business_related INTEGER,
    intent TEXT,
    routed_team TEXT,
    selected_asset_id TEXT,
    openai_called INTEGER DEFAULT 0,
    prompt_version TEXT,
    cache_hit INTEGER DEFAULT 0,
    response_text TEXT,
    latency_ms REAL,
    latency_us INTEGER DEFAULT 0,
    decision_path TEXT,                          -- e.g., "msg_business_consult->cache_miss->openai_called"
    response_len_chars INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `handoffs`
```sql
CREATE TABLE handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,
    reason TEXT,
    priority TEXT,                               -- URGENT | HIGH | MEDIUM
    summary TEXT,
    suggested_response TEXT,
    customer_name TEXT,
    routed_team TEXT,                            -- comercial | tecnica
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);
```

#### `wa_processed_messages`
```sql
CREATE TABLE wa_processed_messages (
    message_id TEXT PRIMARY KEY,                  -- Meta message ID
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    phone_from TEXT,
    text_preview TEXT
);
```

---

## Integration Points

### WhatsApp Cloud API

**Webhook Endpoint**: `POST /whatsapp/webhook`

**Verification Endpoint**: `GET /whatsapp/webhook`

**Message Flow**:
1. Meta sends POST to `/whatsapp/webhook`
2. FastAPI receives, validates, ACKs quickly (<1s)
3. Background task processes message
4. Response sent via Graph API

**Idempotency**: By `message_id` (unique per Meta)

**Rate Limiting**: 20 requests/minute per phone number

### OpenAI API

**Usage**: Only for `BUSINESS_CONSULT` messages with no robust deterministic response.

**Guardrails**:
- Input limited to 1200 chars
- History limited to 6 turns
- Timeout: 8 seconds
- Max output tokens: 180
- Temperature: 0.4

**Cost Control**: Traced in `interaction_traces` table.

---

## SalesBrain System

**Location**: `backend/app/services/sales_brain.py`

**Purpose**: Advanced sales conversation orchestration.

### Architecture: DECIDE → PLAN → SPEAK

#### 1. DECIDE (Triage)
- **Deterministic**: `triage_service.py` (keyword matching)
- **AI-Powered**: `openai_classifier.py` (when ambiguous)
- **Output**: Intent classification + confidence

#### 2. PLAN (Strategy)
- **Deterministic**: `sales_playbook.py` (rule-based responses)
- **AI-Powered**: `openai_planner.py` (complex scenarios)
- **Output**: Response strategy + assets to show

#### 3. SPEAK (Response)
- **Base**: Generated from PLAN stage
- **Optional**: `humanizer.py` (polish with OpenAI)
- **Output**: Final response text

**Configuration**:
- `SALESBRAIN_ENABLED=true` - Enable SalesBrain
- `SALESBRAIN_PLANNER_ENABLED=true` - Enable AI planner
- `SALESBRAIN_CLASSIFIER_ENABLED=true` - Enable AI classifier
- `SALESBRAIN_MAX_CALLS_PER_CONVERSATION=4` - Limit AI calls

---

## Handoff System

**Location**: `backend/app/services/handoff_service.py`

### Handoff Rules

| Trigger | Team | Priority | Example Keywords |
|---------|------|----------|------------------|
| Urgent | TECNICA | URGENT | "no funciona", "se rompió", "urgente" |
| Problems | COMERCIAL | HIGH | "reclamo", "devolución", "malo" |
| Business Impact | COMERCIAL | HIGH | "emprendimiento", "taller", "producción" |
| Service | TECNICA | HIGH | "instalación", "visita", "capacitación" |
| Geographic | COMERCIAL | MEDIUM | City outside Montería |

### Handoff Flow

```
1. should_handoff() detects trigger
   ↓
2. process_handoff() executes:
   - Creates summary bullets
   - Generates notification text
   - Saves to handoffs table
   - Sends internal WhatsApp notification
   - Sets conversation_mode = HUMAN_ACTIVE
   ↓
3. Shadow Mode Activated:
   - Bot silenced (but responds with courteous message - FIX P0)
   - TTL: 12 hours (auto-revert - FIX P1)
   - Human can manually revert via API
```

### Internal Notification Format

```
💰 ATENCIÓN COMERCIAL
(Or: ⚙️ ATENCIÓN TÉCNICA)

Cliente: ***XXXX (masked phone)
• Summary bullet 1
• Summary bullet 2
• Summary bullet 3

Siguiente paso: [suggested action]
```

---

## Asset Management

**Location**: `backend/app/services/asset_service.py`

### Asset Structure

```
backend/assets/catalog/
├── I001_maquina_plana/
│   ├── image_1.png
│   ├── image_2.png
│   └── meta.json
├── I002_maquina_industrial/
│   └── ...
└── catalog_index.json
```

### Asset Selection

**Deterministic Matching**:
- By intent (e.g., `buscar_maquina_industrial`)
- By context slots (tipo_maquina, uso, volumen)
- By keywords in `send_when_customer_says`

**Priority**: Assets have `priority` field (higher = shown first)

### Asset Serving

**Endpoints**:
- `GET /api/catalog/items` - List catalog items with `asset_url`
- `GET /api/assets/{image_id}` - Serve asset file (image/video)
- `POST /api/catalog/sync` - Sync items from n8n/Drive (requires `X-LUISA-API-KEY`)

**Modes**:
- **Local**: Serves from `backend/assets/catalog/`
  - Supports: `image_1.png`, `image_1.jpg`, `image_1.jpeg`, `image_1.webp`, `video_1.mp4`
  - Returns `FileResponse` or `StreamingResponse`
- **Drive**: Downloads from Google Drive (if configured)
  - Checks local cache first
  - Downloads if not cached
  - Caches with TTL (default: 24 hours)

**Configuration**:
```bash
ASSET_PROVIDER=local              # local | drive
GOOGLE_DRIVE_FOLDER_ID=...       # Required if drive mode
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=...  # Required if drive mode
CACHE_TTL_HOURS=24               # Cache TTL for Drive assets
LUISA_API_KEY=...                # API key for sync endpoint
```

### Database Schema

**`catalog_items` table**:
- `image_id` (PRIMARY KEY)
- `title`, `category`, `brand`, `model`
- `represents`, `conversation_role`
- `priority`, `send_when_customer_says`
- `meta_json` (complete JSON metadata)
- `drive_file_id`, `drive_mime_type`
- `asset_provider` (local | drive)
- `file_name`, `updated_at`

**`cache_metadata` table**:
- `cache_key` (PRIMARY KEY)
- `file_path`, `drive_file_id`
- `mime_type`, `created_at`, `expires_at`

---

## Shadow Mode (HUMAN_ACTIVE)

### Purpose

When human handoff is triggered, bot enters "shadow mode" to avoid interfering with human agent.

### Behavior

**Before FIX P0**:
- Bot completely silent (no responses)

**After FIX P0**:
- Bot responds with courteous message: "Hola 😊 sigo pendiente por aquí. Un asesor te va a contactar..."
- Never silent (MVP requirement)

**After FIX P1**:
- TTL automatic revert: After `HUMAN_TTL_HOURS` (default: 12 hours), mode reverts to `AI_ACTIVE`
- Bot resumes normal operation

### Configuration

- `HUMAN_TTL_HOURS=12` - Hours before auto-revert
- `HANDOFF_COOLDOWN_MINUTES=30` - Cooldown after handoff (not currently used)

---

## Performance Characteristics

### Latency Targets

- **Webhook ACK**: < 1 second
- **Response Generation**: < 2 seconds average
- **OpenAI Calls**: < 8 seconds (timeout)

### Resource Usage

- **Memory**: ~128-384MB (backend container)
- **Database**: SQLite with WAL mode (good for single instance)
- **Cache**: In-memory LRU (max 200 entries)

### Scalability Considerations

**Current (Single Instance)**:
- SQLite database (good for < 1000 concurrent conversations)
- In-memory cache (not shared across instances)
- In-memory rate limiting (not shared)

**Future (Multi-Instance)**:
- PostgreSQL for database
- Redis for shared cache and rate limiting
- Load balancer (Nginx/HAProxy) for multiple instances

---

## Security Architecture

### Data Protection

- **Phone Numbers**: Hashed (SHA-256) in `interaction_traces`
- **Secrets**: Never logged (sanitized in error messages)
- **PII**: Masked in logs (last 4 digits only)

### API Security

- **Rate Limiting**: Per conversation/phone
- **Input Validation**: Length limits, type checking
- **HTTPS**: Required (Caddy automatic SSL)

### Webhook Security

- **Verification Token**: Required for webhook verification
- **Signature Verification**: Not currently implemented (future enhancement)

---

**Last Updated**: 2025-01-XX

