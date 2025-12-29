# Production GO/NO-GO Checklist

## 1. WhatsApp Cloud API - End-to-End Requirements

### ✅ Already Implemented
- Webhook router (`/whatsapp/webhook` GET/POST)
- Message parsing (`parse_webhook_message`)
- Rate limiting (20 req/min per phone)
- Internal notifications (`send_internal_notification`)
- Shadow mode (`HUMAN_ACTIVE` when handoff triggered)
- Phone number masking in logs

### ⚠️ Required Configuration
1. **Environment Variables** (set in `.env`):
   ```bash
   WHATSAPP_ENABLED=true
   WHATSAPP_ACCESS_TOKEN=EAA...  # From Meta Business Dashboard
   WHATSAPP_PHONE_NUMBER_ID=...  # From Meta Business Dashboard
   WHATSAPP_VERIFY_TOKEN=your-secure-random-token  # Must match Meta config
   TEST_NOTIFY_NUMBER=+57XXXXXXXXXX  # Internal notifications destination
   ```

2. **Meta Business Dashboard Setup**:
   - Create WhatsApp Business Account
   - Get `WHATSAPP_ACCESS_TOKEN` (temporary or permanent)
   - Get `WHATSAPP_PHONE_NUMBER_ID`
   - Configure webhook URL: `https://your-domain.com/whatsapp/webhook`
   - Set `WHATSAPP_VERIFY_TOKEN` in Meta dashboard (must match `.env`)

3. **Public Endpoint Exposure**:
   - `/whatsapp/webhook` must be publicly accessible
   - Use HTTPS (required by Meta)
   - Options:
     - **Production**: Deploy to cloud (AWS, GCP, Azure) with HTTPS
     - **Testing**: Use ngrok: `ngrok http 8000` → use HTTPS URL

4. **Webhook Verification**:
   - Meta sends GET request: `?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=CHALLENGE`
   - Our endpoint returns `CHALLENGE` as plain text
   - Verification must succeed before Meta sends messages

### 🔍 Testing Checklist
- [ ] Webhook verification succeeds (GET `/whatsapp/webhook`)
- [ ] Incoming messages parsed correctly (POST `/whatsapp/webhook`)
- [ ] Rate limiting works (429 after 20 req/min)
- [ ] Internal notifications sent to `TEST_NOTIFY_NUMBER`
- [ ] Shadow mode activates on handoff (`HUMAN_ACTIVE`)
- [ ] Bot silenced when `HUMAN_ACTIVE` is active

---

## 2. OpenAI - Secure Activation Requirements

### ✅ Already Implemented
- Guardrails (`classify_message_type`: EMPTY_OR_GIBBERISH, NON_BUSINESS, BUSINESS_FAQ, BUSINESS_CONSULT)
- Gating logic (`should_call_openai`: checks message_type, intent, cache_hit)
- Timeout protection (8s default)
- Input limits (1200 chars, 6 turns history)
- Cost controls (max_output_tokens=180, temperature=0.4)
- Fallback to deterministic rules if OpenAI fails

### ⚠️ Required Configuration
1. **Environment Variables** (set in `.env`):
   ```bash
   OPENAI_ENABLED=true
   OPENAI_API_KEY=sk-...  # From OpenAI Platform
   OPENAI_MODEL=gpt-4o-mini  # Recommended: cost-effective
   OPENAI_MAX_OUTPUT_TOKENS=180
   OPENAI_TEMPERATURE=0.4
   OPENAI_TIMEOUT_SECONDS=8
   OPENAI_MAX_INPUT_CHARS=1200
   ```

2. **OpenAI Platform Setup**:
   - Create account at https://platform.openai.com
   - Generate API key (Settings → API Keys)
   - Set usage limits (Settings → Billing → Limits)
   - Monitor usage: https://platform.openai.com/usage

### 🔍 Guardrails Validation
OpenAI is called **ONLY** when:
- ✅ `message_type == BUSINESS_CONSULT`
- ✅ `intent NOT IN {saludo, despedida, envios, pagos, horarios, direccion, ubicacion}`
- ✅ `cache_hit == false`
- ✅ No robust deterministic response available

OpenAI is **BLOCKED** for:
- ❌ Non-business messages (programming, tasks, etc.)
- ❌ Simple FAQs (horarios, direccion, envios, pagos)
- ❌ Greetings/gibberish
- ❌ Empty messages

### 🔍 Testing Checklist
- [ ] Non-business message → `openai_called=false`
- [ ] FAQ (horarios) → `openai_called=false`
- [ ] Greeting → `openai_called=false`
- [ ] Complex business consult → `openai_called=true` (if enabled)
- [ ] OpenAI timeout handled gracefully (fallback to rules)
- [ ] Input truncation works (max 1200 chars)

---

## 3. Public Endpoints & Testing

### Public Endpoints (Production)
1. **`GET /whatsapp/webhook`** - Webhook verification (Meta)
2. **`POST /whatsapp/webhook`** - Incoming messages (Meta)

### Protected Endpoints (Internal/API Key)
1. **`POST /api/chat`** - Chat endpoint (rate-limited, can be public with rate limiting)
2. **`GET /api/catalog/items`** - Catalog listing (can be public)
3. **`GET /api/assets/{image_id}`** - Asset serving (can be public)
4. **`GET /health`** - Health check (can be public)

### Testing Strategy

#### Local Testing (No WhatsApp/OpenAI)
```bash
# Start backend
cd backend
python main.py

# Run go/no-go script
python scripts/go_no_go.py
```

#### WhatsApp Testing (with ngrok)
```bash
# Terminal 1: Start backend
cd backend
python main.py

# Terminal 2: Expose webhook
ngrok http 8000
# Copy HTTPS URL: https://abc123.ngrok.io

# Terminal 3: Configure Meta webhook
# Webhook URL: https://abc123.ngrok.io/whatsapp/webhook
# Verify Token: (match WHATSAPP_VERIFY_TOKEN in .env)

# Terminal 4: Run WhatsApp-specific checks
python scripts/go_no_go_whatsapp_openai.py
```

#### OpenAI Testing
```bash
# Set in .env
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...

# Run checks
python scripts/go_no_go_whatsapp_openai.py
```

---

## 4. Security Checklist

### Rate Limiting
- [x] `/api/chat`: 30 req/min per `conversation_id`
- [x] `/whatsapp/webhook`: 20 req/min per phone number
- [ ] Test rate limiting (send 21 requests in 1 minute → expect 429)

### Logging
- [x] Phone numbers masked (last 4 digits only)
- [x] No API keys in logs
- [x] JSON logs in production (`PRODUCTION_MODE=true`)
- [ ] Verify logs don't contain PII

### Shadow Mode
- [x] `HUMAN_ACTIVE` silences bot
- [x] TTL: 12 hours
- [ ] Test: handoff → verify bot doesn't respond

### Timeouts
- [x] OpenAI: 8s timeout
- [x] WhatsApp send: 8s timeout + 2 retries
- [ ] Test: simulate timeout → verify fallback

---

## 5. Pre-Production Validation

Run the comprehensive check script:
```bash
cd backend
python scripts/go_no_go_whatsapp_openai.py
```

This script validates:
- ✅ Health endpoint
- ✅ Chat scenarios (saludo, non-business, FAQ)
- ✅ OpenAI gating (openai_called=0 for blocked cases)
- ✅ WhatsApp webhook readiness
- ✅ Trace growth
- ✅ Decision path flags

---

## 6. Deployment Steps

### Step 1: Environment Setup
```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env with production values
# - Set WHATSAPP_ENABLED=true
# - Set OPENAI_ENABLED=true (if using)
# - Add all required tokens/keys
```

### Step 2: Database Initialization
```bash
cd backend
python scripts/init_db.py
```

### Step 3: Run Pre-Production Checks
```bash
python scripts/go_no_go_whatsapp_openai.py
```

### Step 4: Deploy Backend
- Deploy to cloud (AWS/GCP/Azure)
- Expose HTTPS endpoint
- Configure environment variables

### Step 5: Configure WhatsApp Webhook
- In Meta Business Dashboard:
  - Webhook URL: `https://your-domain.com/whatsapp/webhook`
  - Verify Token: (match `WHATSAPP_VERIFY_TOKEN` in `.env`)
  - Subscribe to `messages` events

### Step 6: Test End-to-End
- Send test message from WhatsApp
- Verify webhook receives it
- Verify response sent back
- Verify internal notification sent (if handoff)

---

## 7. Monitoring & Alerts

### Key Metrics to Monitor
- OpenAI API calls (cost control)
- Rate limit hits (429 responses)
- Handoff frequency (team routing)
- Shadow mode activations
- Trace table growth
- Error rates

### Logs to Watch
- `interaction_traces` table (decision_path, openai_called, latency_ms)
- Application logs (errors, warnings)
- WhatsApp webhook logs (incoming/outgoing)

---

## Summary

**WhatsApp Cloud API**: Ready ✅ (requires env vars + Meta dashboard config + public HTTPS endpoint)

**OpenAI**: Ready ✅ (requires env vars + guardrails validated + cost limits set)

**Public Endpoints**: `/whatsapp/webhook` must be public; others can be rate-limited public or API-key protected

**Testing**: Use `go_no_go_whatsapp_openai.py` script for comprehensive validation

