# Release Plan v2.1.0: Production Deployment + GitHub Update

**Release Engineer:** Auto  
**Date:** 2025-01-XX  
**Version:** 2.1.0

## A) Pre-flight Checklist

### Required Environment Variables

**WhatsApp (Required for production):**
- `WHATSAPP_ENABLED=true`
- `WHATSAPP_VERIFY_TOKEN` (must match Meta Dashboard exactly, case-sensitive)
- `WHATSAPP_ACCESS_TOKEN` (from Meta Business Dashboard)
- `WHATSAPP_PHONE_NUMBER_ID` (from Meta Business Dashboard)
- `WHATSAPP_API_VERSION=v18.0` (default)
- `LUISA_HUMAN_NOTIFY_NUMBER` (for internal notifications)

**OpenAI (Optional but recommended for canary):**
- `OPENAI_ENABLED=true` (if using OpenAI)
- `OPENAI_API_KEY=sk-...`
- `OPENAI_MODEL=gpt-4o-mini` (default)
- `OPENAI_CANARY_ALLOWLIST` (comma-separated: conversation_id or phone last4, e.g., "wa_573142156486,test_conv_001,1234")
- `OPENAI_MAX_CALLS_PER_CONVERSATION=4` (default)
- `OPENAI_CONVERSATION_TTL_HOURS=24` (default)

**Database:**
- `DB_PATH=/app/data/luisa.db` (default in Docker)

**Production Settings:**
- `PRODUCTION_MODE=true`
- `LOG_FORMAT=json`
- `LOG_LEVEL=INFO`

### Local Verification Commands

```bash
# 1. Verify environment variables exist
cd /Users/camilope/AI-Agents/Sastre
grep -E "WHATSAPP_ENABLED|WHATSAPP_ACCESS_TOKEN|WHATSAPP_PHONE_NUMBER_ID|OPENAI_CANARY_ALLOWLIST" .env || echo "⚠️ Missing env vars"

# 2. Run go_no_go checks locally
cd backend
python scripts/go_no_go.py --hard-fail

# 3. Test ops snapshot endpoint (if server running)
curl http://localhost:8000/ops/snapshot | jq

# 4. Run filtering validation
python scripts/validate_filtering.py

# 5. Check for linting errors
python -m pylint app/ --disable=all --enable=E,F || true
```

### Server Verification Commands

```bash
# SSH to server
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

# 1. Check containers running
cd /opt/luisa
sudo docker compose ps

# 2. Check health endpoint
curl http://localhost:8000/health | jq
curl https://luisa-agent.online/health | jq

# 3. Check ops snapshot
curl http://localhost:8000/ops/snapshot | jq

# 4. Check logs for errors
sudo docker compose logs backend --tail=50 | grep -i error

# 5. Verify WhatsApp webhook accessible (see section C for detailed verification)
```

## B) Deployment Plan

### 0) Backup/Rollback Plan

**Database Backup:**
```bash
# On server, before deployment
cd /opt/luisa
sudo docker compose exec backend sqlite3 /app/data/luisa.db ".backup /app/data/luisa.db.backup.$(date +%Y%m%d_%H%M%S)"
# Or from host (if DB is mounted):
sudo cp ./data/luisa.db ./data/luisa.db.backup.$(date +%Y%m%d_%H%M%S)
```

**Docker Image Tagging (Robust Method):**
```bash
# Get actual image name used by docker compose
cd /opt/luisa
IMAGE_NAME=$(sudo docker compose config --images | grep backend | head -1)
echo "Image name: $IMAGE_NAME"
# Expected: sastre-backend:latest or similar

# Get current image ID before rebuild
CURRENT_IMAGE_ID=$(sudo docker images --format "{{.ID}}" --filter "reference=${IMAGE_NAME}" | head -1)
echo "Current image ID: $CURRENT_IMAGE_ID"

# Tag current image with timestamp
BACKUP_TAG="backup-$(date +%Y%m%d_%H%M%S)"
sudo docker tag "${IMAGE_NAME}" "${IMAGE_NAME%:*}:${BACKUP_TAG}"
echo "Tagged backup: ${IMAGE_NAME%:*}:${BACKUP_TAG}"

# Verify backup tag exists
sudo docker images | grep "${BACKUP_TAG}"
```

**Rollback Procedure:**
```bash
# If deployment fails:

# 1. Get backup image name
cd /opt/luisa
IMAGE_NAME=$(sudo docker compose config --images | grep backend | head -1)
BACKUP_TAG="backup-TIMESTAMP"  # Replace TIMESTAMP with actual timestamp

# 2. Restore previous image
sudo docker tag "${IMAGE_NAME%:*}:${BACKUP_TAG}" "${IMAGE_NAME}"
sudo docker compose up -d backend

# 3. Restore database (if needed)
sudo docker cp ./data/luisa.db.backup.TIMESTAMP luisa-backend:/app/data/luisa.db
# Or if mounted:
sudo cp ./data/luisa.db.backup.TIMESTAMP ./data/luisa.db

# 4. Verify rollback
sleep 10
curl http://localhost:8000/health
sudo docker compose logs backend --tail=20
```

### 1) Pull Latest Code

```bash
# On server
cd /opt/luisa
git fetch origin
git log HEAD..origin/main --oneline  # Review changes
git pull origin main
```

### 2) Build Docker Image

**Default Build (with cache - recommended for faster builds):**
```bash
cd /opt/luisa
sudo docker compose build backend
```

**Force Rebuild (--no-cache - use only if cache issues suspected):**
```bash
cd /opt/luisa
sudo docker compose build --no-cache backend
```

**Verify Build:**
```bash
# Check image was built
IMAGE_NAME=$(sudo docker compose config --images | grep backend | head -1)
sudo docker images | grep "${IMAGE_NAME%:*}"
```

### 3) Run DB Migrations Safely

**Important:** `init_db()` runs automatically on startup (called in `app/main.py` line 43), but we verify schema explicitly before restarting.

**Explicit Migration Verification:**
```bash
# Run init_db manually to ensure migrations are applied
cd /opt/luisa
sudo docker compose exec backend python -c "
from app.models.database import init_db, get_connection
import sys

# Run init_db (idempotent - safe to run multiple times)
print('Running init_db()...')
init_db()
print('✅ init_db() completed')

# Verify schema with PRAGMA
conn = get_connection()
cursor = conn.cursor()

# Check interaction_traces columns
print('Checking interaction_traces schema...')
cursor.execute('PRAGMA table_info(interaction_traces)')
columns = [row[1] for row in cursor.fetchall()]

required_columns = [
    'whatsapp_send_success', 'whatsapp_send_latency_ms', 'whatsapp_send_error_code',
    'classification', 'is_personal', 'classification_score', 'classification_reasons', 'classifier_version',
    'openai_canary_allowed', 'openai_latency_ms', 'openai_error', 'openai_fallback_used'
]

missing = [col for col in required_columns if col not in columns]
if missing:
    print(f'❌ Missing columns in interaction_traces: {missing}')
    sys.exit(1)
else:
    print('✅ All required interaction_traces columns exist')

# Check conversations columns
print('Checking conversations schema...')
cursor.execute('PRAGMA table_info(conversations)')
conv_columns = [row[1] for row in cursor.fetchall()]
if 'mode_updated_at_epoch' not in conv_columns:
    print('❌ Missing mode_updated_at_epoch in conversations')
    sys.exit(1)
else:
    print('✅ mode_updated_at_epoch exists in conversations')

conn.close()
print('✅ Schema verification complete - all migrations applied')
"

# Hard-fail if verification fails
if [ $? -ne 0 ]; then
    echo "❌ Schema verification failed - DO NOT PROCEED WITH DEPLOYMENT"
    exit 1
fi
```

### 4) Restart Containers

```bash
# Graceful restart (minimal downtime)
cd /opt/luisa
sudo docker compose up -d backend

# Wait for healthcheck (healthcheck interval is 30s, start_period is 60s)
echo "Waiting for backend healthcheck..."
sleep 70

# Verify health
curl -f http://localhost:8000/health || {
    echo "❌ Health check failed"
    sudo docker compose logs backend --tail=50
    exit 1
}
```

### 5) Post-Deploy Verification

```bash
# 1. Health check
curl http://localhost:8000/health | jq
# Expected: {"status":"healthy","service":"luisa","version":"2.0.0","whatsapp_enabled":true}

# 2. Ops snapshot
curl http://localhost:8000/ops/snapshot | jq
# Expected: {"total_msgs_60m":N,"pct_personal":X,"pct_handoff":Y,...}

# 3. Run go_no_go
cd /opt/luisa/backend
sudo docker compose exec backend python scripts/go_no_go.py --hard-fail
# Expected: All hard-fail checks pass

# 4. Verify logs show new fields
sudo docker compose logs backend --tail=100 | grep -E "whatsapp_send_success|whatsapp_send_failed|classification|openai_canary"
# Expected: Logs contain new structured fields
```

## C) End-to-End WhatsApp Test

### Webhook Configuration Verification

**Meta Dashboard Setup:**
1. Webhook URL: `https://luisa-agent.online/whatsapp/webhook` (NO trailing slash)
2. Verify Token: Must match `WHATSAPP_VERIFY_TOKEN` in `.env` (case-sensitive)
3. Subscription Fields: `messages` must be checked

**Test Verification (with and without trailing slash):**
```bash
# Get verify token from container
cd /opt/luisa
VERIFY_TOKEN=$(sudo docker compose exec -T backend python -c "from app.config import WHATSAPP_VERIFY_TOKEN; print(WHATSAPP_VERIFY_TOKEN)" | tr -d '\r\n')
echo "Verify token: $VERIFY_TOKEN"

# Test WITHOUT trailing slash (correct)
curl -v "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=${VERIFY_TOKEN}&hub.challenge=TEST123" 2>&1 | grep -E "HTTP|TEST123"
# Expected: HTTP/2 200, body contains exactly "TEST123" (text/plain, not JSON)

# Test WITH trailing slash (should also work, but prefer without)
curl -v "https://luisa-agent.online/whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=${VERIFY_TOKEN}&hub.challenge=TEST456" 2>&1 | grep -E "HTTP|TEST456"
# Expected: HTTP/2 200, body contains exactly "TEST456"

# Verify response is text/plain (not JSON)
RESPONSE=$(curl -s "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=${VERIFY_TOKEN}&hub.challenge=TEST789")
if [ "$RESPONSE" = "TEST789" ]; then
    echo "✅ Webhook verification correct (text/plain response)"
else
    echo "❌ Webhook verification failed - response: $RESPONSE"
    exit 1
fi

# Check backend logs for verification request
sudo docker compose logs backend --tail=20 | grep -i "webhook.*verificado\|verification"
```

### Deterministic Test Procedure

**Step 1: Send "hola" from test number**
- Use WhatsApp test number configured in Meta Dashboard
- Send message: "hola"
- Wait 5-10 seconds for response

**Step 2: Expected Success Criteria**
Success is defined as:
- ✅ Reply delivered (user receives response)
- ✅ `interaction_traces` row exists with the message
- ✅ `whatsapp_send_success = 1` in the trace

**Note:** Classification can be BUSINESS or PERSONAL - both are valid. We don't enforce classification type.

**Step 3: Verify in interaction_traces (Robust Query)**
```bash
# On server, after sending "hola"
sudo docker compose exec backend sqlite3 /app/data/luisa.db "
SELECT 
    id,
    conversation_id,
    raw_text,
    classification,
    is_personal,
    classification_score,
    response_text,
    whatsapp_send_success,
    whatsapp_send_latency_ms,
    openai_called,
    created_at
FROM interaction_traces 
WHERE created_at > datetime('now', '-10 minutes')
ORDER BY id DESC 
LIMIT 1;
"

# Expected output format:
# id|conversation_id|raw_text|classification|is_personal|classification_score|response_text|whatsapp_send_success|whatsapp_send_latency_ms|openai_called|created_at
# X|wa_XXXX|hola|BUSINESS|0|0.95|¡Hola! 😊 ¿En qué puedo ayudarte...|1|XXX.XX|0|2025-01-XX...

# Success criteria check:
# - whatsapp_send_success = 1 (required)
# - response_text IS NOT NULL (required)
# - classification IS NOT NULL (required)
# - created_at within last 10 minutes (required)
```

**Step 4: Confirm in Logs**
```bash
# On server
sudo docker compose logs backend --tail=200 | grep -E "message_received|whatsapp_send_success|whatsapp_send_failed|classification"
# Expected: Structured logs with all fields

# Specifically check for success log
sudo docker compose logs backend --tail=200 | grep "whatsapp_send_success" | tail -1
# Expected: Log entry with conversation_id, message_id, latency_ms, and success=true
```

### Troubleshooting Branches

**Webhook not receiving:**
```bash
# 1. Check webhook URL in Meta Dashboard (no trailing slash)
# 2. Verify HTTPS certificate valid
curl -v https://luisa-agent.online/whatsapp/webhook

# 3. Check Caddy logs
sudo docker compose logs caddy | grep -i error

# 4. Verify WHATSAPP_ENABLED=true
sudo docker compose exec backend python -c "from app.config import WHATSAPP_ENABLED; print(WHATSAPP_ENABLED)"

# 5. Check backend logs for webhook requests
sudo docker compose logs backend | grep -i "webhook\|verification" | tail -20
```

**Message received but no reply:**
```bash
# 1. Check logs for processing
sudo docker compose logs backend | grep -A 10 "message_received"

# 2. Check if PERSONAL_MESSAGES_MODE=silent blocked it
sudo docker compose logs backend | grep "personal_message_silent"

# 3. Check if HUMAN_ACTIVE mode blocked it
sudo docker compose logs backend | grep "HUMAN_ACTIVE"

# 4. Check for errors in processing
sudo docker compose logs backend | grep -i error | tail -20

# 5. Check if message was classified as personal
sudo docker compose exec backend sqlite3 /app/data/luisa.db "
SELECT classification, is_personal, response_text, whatsapp_send_success
FROM interaction_traces 
WHERE created_at > datetime('now', '-10 minutes')
ORDER BY id DESC LIMIT 1;
"
```

**Reply failed on WhatsApp send:**
```bash
# 1. Check whatsapp_send_success in traces
sudo docker compose exec backend sqlite3 /app/data/luisa.db "
SELECT whatsapp_send_success, whatsapp_send_error_code, whatsapp_send_latency_ms, created_at
FROM interaction_traces 
WHERE created_at > datetime('now', '-10 minutes')
ORDER BY id DESC LIMIT 5;
"

# 2. Check logs for send errors
sudo docker compose logs backend | grep "whatsapp_send_failed"

# 3. Verify WHATSAPP_ACCESS_TOKEN valid
# (Check Meta Dashboard for token expiration)
sudo docker compose exec backend python -c "from app.config import WHATSAPP_ACCESS_TOKEN; print('Token length:', len(WHATSAPP_ACCESS_TOKEN))"
```

**HUMAN_ACTIVE stuck:**
```bash
# Run fix script
sudo docker compose exec backend python scripts/fix_stuck_human_active.py

# Verify
sudo docker compose exec backend sqlite3 /app/data/luisa.db "
SELECT conversation_id, conversation_mode, mode_updated_at_epoch,
       (strftime('%s', 'now') - mode_updated_at_epoch) as seconds_ago
FROM conversations 
WHERE conversation_mode = 'HUMAN_ACTIVE';
"
```

**OpenAI called unexpectedly (canary gating):**
```bash
# Check canary allowlist
sudo docker compose exec backend python -c "
from app.config import OPENAI_CANARY_ALLOWLIST
print(f'Allowlist: {OPENAI_CANARY_ALLOWLIST}')
"

# Check traces for unauthorized calls
sudo docker compose exec backend sqlite3 /app/data/luisa.db "
SELECT 
    conversation_id,
    openai_called,
    openai_canary_allowed,
    created_at
FROM interaction_traces 
WHERE openai_called = 1 AND openai_canary_allowed = 0
ORDER BY created_at DESC 
LIMIT 10;
"
```

## D) Mini Ops Dashboard (Recommendation)

**Decision: NO build dashboard now**

**Justification:**
- `/ops/snapshot` endpoint + `ops_snapshot.py` script provide sufficient observability
- Current stack (FastAPI + Caddy) doesn't include static file serving setup
- Adding React/HTML dashboard requires:
  - New build step
  - Static file serving in Caddy or FastAPI
  - Basic auth setup
  - Additional maintenance burden
- Scripts (`ops_snapshot.py`, `monitor_openai_costs.py`, `analyze_traces.py`) are more flexible for ops team
- Can be added later if needed (P2 improvement)

**Alternative:**
- Use `ops_snapshot.py` in cron job
- Pipe to monitoring system (if available)
- Or create simple shell script that calls endpoint and formats output

## E) GitHub Repository Update

### Commit Plan (Already Completed)

All commits have been created and are ready for push:
1. feat(ops): Add /ops/snapshot endpoint and ops_snapshot.py script
2. feat(whatsapp): Harden send_whatsapp_message() with guaranteed logging
3. feat(handoff): Normalize HUMAN_ACTIVE TTL with epoch timestamps
4. feat(filtering): Add classification scoring and persistence
5. feat(filtering): Add versioned dataset and validation script
6. feat(openai): Add canary allowlist for controlled OpenAI usage
7. feat(openai): Add cost monitoring script
8. feat(deploy): Integrate go_no_go.py in deploy scripts
9. docs: Add operations guide and update README/CHANGELOG

### Push to GitHub

```bash
# On local machine
cd /Users/camilope/AI-Agents/Sastre

# 1. Verify .env not tracked
git ls-files | grep "\.env$" || echo "✅ .env not tracked"

# 2. Push commits
git push origin main

# 3. Tag release
git tag -a v2.1.0 -m "Release v2.1.0: Operations hardening and observability"
git push origin v2.1.0
```

## F) Final Output - Exact Commands

### Local Pre-Deployment

```bash
cd /Users/camilope/AI-Agents/Sastre

# 1. Verify env vars
grep -E "WHATSAPP_ENABLED|WHATSAPP_ACCESS_TOKEN|OPENAI_CANARY_ALLOWLIST" .env || echo "⚠️ Check .env"

# 2. Run go_no_go locally (if server running)
cd backend
python scripts/go_no_go.py --hard-fail

# 3. Validate filtering
python scripts/validate_filtering.py

# Expected output: "✅ VALIDACIÓN EXITOSA: Todos los criterios cumplidos"
```

### Server Deployment (Complete Sequence)

```bash
# SSH to server
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112

# 0. Backup database
cd /opt/luisa
sudo docker compose exec backend sqlite3 /app/data/luisa.db ".backup /app/data/luisa.db.backup.$(date +%Y%m%d_%H%M%S)"

# 0. Tag current image
IMAGE_NAME=$(sudo docker compose config --images | grep backend | head -1)
BACKUP_TAG="backup-$(date +%Y%m%d_%H%M%S)"
sudo docker tag "${IMAGE_NAME}" "${IMAGE_NAME%:*}:${BACKUP_TAG}"
echo "Backup image: ${IMAGE_NAME%:*}:${BACKUP_TAG}"

# 1. Pull latest code
git pull origin main

# 2. Build new image (with cache - faster)
sudo docker compose build backend

# 3. Verify schema (migrations run automatically on startup, but verify explicitly)
sudo docker compose exec backend python -c "
from app.models.database import init_db, get_connection
import sys
init_db()
conn = get_connection()
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(interaction_traces)')
columns = [row[1] for row in cursor.fetchall()]
required = ['whatsapp_send_success', 'classification', 'openai_canary_allowed']
missing = [c for c in required if c not in columns]
if missing:
    print(f'Missing: {missing}')
    sys.exit(1)
cursor.execute('PRAGMA table_info(conversations)')
conv_cols = [row[1] for row in cursor.fetchall()]
if 'mode_updated_at_epoch' not in conv_cols:
    sys.exit(1)
print('✅ Schema OK')
"
if [ $? -ne 0 ]; then
    echo "❌ Schema verification failed"
    exit 1
fi

# 4. Restart backend
sudo docker compose up -d backend

# 5. Wait for health
sleep 70
curl -f http://localhost:8000/health || exit 1

# 6. Verify ops snapshot
curl http://localhost:8000/ops/snapshot | jq

# 7. Run go_no_go
sudo docker compose exec backend python scripts/go_no_go.py --hard-fail

# 8. Check logs for new fields
sudo docker compose logs backend --tail=50 | grep -E "whatsapp_send_success|classification"
```

### End-to-End WhatsApp Test

```bash
# On server, after deployment

# 1. Verify webhook (get token first)
VERIFY_TOKEN=$(sudo docker compose exec -T backend python -c "from app.config import WHATSAPP_VERIFY_TOKEN; print(WHATSAPP_VERIFY_TOKEN)" | tr -d '\r\n')
curl -s "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=${VERIFY_TOKEN}&hub.challenge=TEST123"
# Expected: "TEST123" (exact match, text/plain)

# 2. Send "hola" from test WhatsApp number
# (Use Meta Dashboard test number or configured test number)
# Wait 5-10 seconds

# 3. Verify in database (robust query with time window)
sudo docker compose exec backend sqlite3 /app/data/luisa.db "
SELECT 
    id,
    conversation_id,
    raw_text,
    classification,
    classification_score,
    response_text,
    whatsapp_send_success,
    whatsapp_send_latency_ms,
    created_at
FROM interaction_traces 
WHERE created_at > datetime('now', '-10 minutes')
ORDER BY id DESC 
LIMIT 1;
"

# Success criteria:
# - whatsapp_send_success = 1
# - response_text IS NOT NULL
# - created_at within last 10 minutes

# 4. Verify in logs
sudo docker compose logs backend --tail=100 | grep -A 5 "message_received"
```

### Rollback Commands

```bash
# If deployment fails:

# 1. Get image name and restore
cd /opt/luisa
IMAGE_NAME=$(sudo docker compose config --images | grep backend | head -1)
BACKUP_TAG="backup-TIMESTAMP"  # Replace with actual timestamp
sudo docker tag "${IMAGE_NAME%:*}:${BACKUP_TAG}" "${IMAGE_NAME}"
sudo docker compose up -d backend

# 2. Restore database (if needed)
sudo docker cp ./data/luisa.db.backup.TIMESTAMP luisa-backend:/app/data/luisa.db

# 3. Verify rollback
sleep 10
curl http://localhost:8000/health
sudo docker compose logs backend --tail=20
```

### Expected Outputs

**Health Check:**
```json
{
  "status": "healthy",
  "service": "luisa",
  "version": "2.0.0",
  "whatsapp_enabled": true
}
```

**Ops Snapshot:**
```json
{
  "total_msgs_60m": 15,
  "pct_personal": 6.67,
  "pct_handoff": 0.0,
  "pct_openai": 13.33,
  "errores_count": 0,
  "p95_latency_ms": 1250.5
}
```

**go_no_go Output:**
```
🏁 Ejecutando Go/No-Go suite...
[✅ PASS] health: OK
[✅ PASS] saludo: Response contains greeting
[✅ PASS] nonbusiness: Correctly filtered
[✅ PASS] faq-horarios-1: FAQ response valid
[✅ PASS] faq-horarios-2: Cache hit confirmed
[✅ PASS] industrial-asset: Asset selected
[✅ PASS] handoff-pago: Handoff triggered

✅ RESULTADO: GO (todas las verificaciones pasaron)
```

**Webhook Verification:**
```
TEST123
```
(Exact text, no JSON, no extra characters)

**E2E Test Success:**
```
id|conversation_id|raw_text|classification|classification_score|response_text|whatsapp_send_success|whatsapp_send_latency_ms|created_at
123|wa_573142156486|hola|BUSINESS|0.95|¡Hola! 😊 ¿En qué puedo ayudarte...|1|245.67|2025-01-XX...
```

---

## Notes

- **init_db() runs automatically on startup** (app/main.py line 43), but we verify schema explicitly before restart
- **Image name is `sastre-backend`** (from docker compose config), not hardcoded
- **Webhook returns text/plain**, not JSON (Response(content=hub_challenge, media_type="text/plain"))
- **E2E success criteria:** whatsapp_send_success=1 + response exists + trace exists (classification type not enforced)
- **Dataset skew:** 15 personal / 35 business (see OPERATIONS_AND_TRADEOFFS.md for justification)
