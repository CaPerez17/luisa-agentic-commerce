# 🔧 Troubleshooting Guide - LUISA

Comprehensive troubleshooting guide for common issues and diagnostics.

## Table of Contents

1. [WhatsApp Webhook Issues](#whatsapp-webhook-issues)
2. [Message Processing Issues](#message-processing-issues)
3. [Shadow Mode & Handoff Issues](#shadow-mode--handoff-issues)
4. [Performance Issues](#performance-issues)
5. [Database Issues](#database-issues)
6. [Infrastructure Issues](#infrastructure-issues)

---

## WhatsApp Webhook Issues

### Problem: Meta Webhook Verification Fails

**Symptoms:**
- Webhook verification returns 403 in Meta Dashboard
- "Verify and Save" button fails
- No webhook events received

**Diagnosis:**

1. **Check webhook URL:**
   ```bash
   # Must be exactly (no trailing slash):
   https://luisa-agent.online/whatsapp/webhook
   ```

2. **Verify token match:**
   ```bash
   # Get token from container
   docker exec luisa-backend python -c "from app.config import WHATSAPP_VERIFY_TOKEN; print(WHATSAPP_VERIFY_TOKEN)"
   
   # Compare with Meta Dashboard (must match exactly, case-sensitive)
   ```

3. **Test GET verification manually:**
   ```bash
   curl -v "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=TEST123"
   ```
   **Expected:** Status 200, Body `TEST123` (text/plain)

**Common Causes:**
- Token mismatch (case-sensitive, spaces, typos)
- `WHATSAPP_ENABLED=false` in `.env`
- `hub.challenge` is None (bug fixed in latest version)
- Wrong webhook URL (trailing slash, wrong path)

**Fix:**
- Ensure `WHATSAPP_VERIFY_TOKEN` in `.env` matches Meta Dashboard exactly
- Verify `WHATSAPP_ENABLED=true`
- Check logs: `docker compose logs backend | grep -i "verificación\|webhook"`

---

### Problem: Meta Not Sending Messages

**Symptoms:**
- Webhook verified successfully
- "messages" subscription enabled in Meta Dashboard
- No incoming messages in logs
- No POST requests to `/whatsapp/webhook`

**Diagnosis:**

1. **Check webhook subscription:**
   - Meta Dashboard: WhatsApp > Webhooks > Edit Subscription
   - Ensure `messages` checkbox is **enabled** (not just verified)

2. **Check logs for incoming requests:**
   ```bash
   docker compose logs --tail=500 backend | grep -i "webhook\|whatsapp\|POST"
   ```

3. **Verify endpoint is publicly accessible:**
   ```bash
   curl -v -X POST https://luisa-agent.online/whatsapp/webhook \
     -H "Content-Type: application/json" \
     -d '{"test": "payload"}'
   ```

**Common Causes:**
- Webhook subscription not enabled (only verified)
- Firewall blocking Meta IPs
- Caddy reverse proxy misconfiguration
- SSL certificate issues

**Fix:**
- Enable `messages` subscription in Meta Dashboard
- Check firewall rules (allow Meta IP ranges)
- Verify Caddyfile reverse proxy configuration

---

## Message Processing Issues

### Problem: LUISA Stops Responding After Handoff

**Symptoms:**
- LUISA responds initially
- After handoff (user accepts advisor), LUISA stops responding
- User sends "Hello" hours later → No response
- No errors in logs

**Root Cause:**
`HUMAN_ACTIVE` mode set permanently after handoff, blocking all responses.

**Diagnosis:**

1. **Check conversation mode:**
   ```bash
   docker exec luisa-backend sqlite3 /app/data/luisa.db \
     "SELECT conversation_mode, mode_updated_at FROM conversations WHERE conversation_mode = 'HUMAN_ACTIVE' LIMIT 5;"
   ```

2. **Check logs for FIX P0:**
   ```bash
   docker compose logs --tail=200 backend | grep "reply_sent_in_human_active\|reply_failed_in_human_active"
   ```

**Fix Applied (FIX P0):**
- LUISA now responds with courteous message in `HUMAN_ACTIVE` mode
- Never silent: "Hola 😊 sigo pendiente por aquí. Un asesor te va a contactar..."

**Fix Applied (FIX P1):**
- TTL automatic revert: `HUMAN_ACTIVE` reverts to `AI_ACTIVE` after `HUMAN_TTL_HOURS` (default: 12 hours)

**Verification:**
```bash
# Check if TTL reversion works
docker compose logs --tail=100 backend | grep "mode_auto_reverted_to_ai"

# Simulate TTL expiration (for testing)
docker exec luisa-backend sqlite3 /app/data/luisa.db \
  "UPDATE conversations SET mode_updated_at = datetime('now', '-13 hours') WHERE conversation_mode = 'HUMAN_ACTIVE' LIMIT 1;"
```

---

### Problem: Messages Not Processed (Deduplication)

**Symptoms:**
- Messages received but not processed
- Logs show "Mensaje WhatsApp duplicado (dedup)"

**Diagnosis:**

1. **Check processed messages table:**
   ```bash
   docker exec luisa-backend sqlite3 /app/data/luisa.db \
     "SELECT COUNT(*) FROM wa_processed_messages WHERE received_at > datetime('now', '-1 hour');"
   ```

2. **Check for duplicate message_ids:**
   ```bash
   docker compose logs --tail=100 backend | grep -i "dedup\|duplicado"
   ```

**Common Causes:**
- Meta sending duplicate webhooks (normal behavior)
- Race condition in message processing
- Database lock issues

**Fix:**
- Deduplication is working correctly (by design)
- If legitimate messages are being deduplicated, check `message_id` uniqueness

---

## Shadow Mode & Handoff Issues

### Problem: Handoff Not Triggering

**Symptoms:**
- User mentions keywords that should trigger handoff
- No internal notification sent
- No `HUMAN_ACTIVE` mode set

**Diagnosis:**

1. **Check handoff rules:**
   ```bash
   # Review handoff keywords in code
   grep -r "URGENTE\|PROBLEMAS\|IMPACTO_NEGOCIO" backend/app/services/handoff_service.py
   ```

2. **Check handoff logs:**
   ```bash
   docker compose logs --tail=200 backend | grep -i "handoff\|should_handoff"
   ```

3. **Verify handoff table:**
   ```bash
   docker exec luisa-backend sqlite3 /app/data/luisa.db \
     "SELECT * FROM handoffs ORDER BY timestamp DESC LIMIT 5;"
   ```

**Common Causes:**
- Keywords not matching (case-sensitive, exact match required)
- Context not extracted correctly
- `should_handoff()` returning False

**Fix:**
- Review handoff keywords in `handoff_service.py`
- Check context extraction from conversation history
- Verify `TEST_NOTIFY_NUMBER` is configured

---

### Problem: TTL Not Reverting HUMAN_ACTIVE

**Symptoms:**
- `HUMAN_ACTIVE` mode persists beyond `HUMAN_TTL_HOURS`
- Mode never reverts to `AI_ACTIVE`

**Diagnosis:**

1. **Check TTL configuration:**
   ```bash
   docker exec luisa-backend python -c "from app.config import HUMAN_TTL_HOURS; print(f'TTL: {HUMAN_TTL_HOURS} hours')"
   ```

2. **Check mode_updated_at timestamp:**
   ```bash
   docker exec luisa-backend sqlite3 /app/data/luisa.db \
     "SELECT conversation_id, conversation_mode, mode_updated_at, \
      (julianday('now') - julianday(mode_updated_at)) * 24 as hours_elapsed \
      FROM conversations WHERE conversation_mode = 'HUMAN_ACTIVE';"
   ```

3. **Check TTL reversion logs:**
   ```bash
   docker compose logs --tail=500 backend | grep "mode_auto_reverted_to_ai"
   ```

**Common Causes:**
- `mode_updated_at` is NULL (old records)
- TTL calculation error (timezone issues)
- TTL not checked (bug in code)

**Fix Applied (FIX P1):**
- TTL check implemented in `_process_whatsapp_message()`
- Automatic revert after `HUMAN_TTL_HOURS`
- Logs `mode_auto_reverted_to_ai` when reverted

**Manual Fix:**
```bash
# Manually revert to AI_ACTIVE
docker exec luisa-backend sqlite3 /app/data/luisa.db \
  "UPDATE conversations SET conversation_mode = 'AI_ACTIVE', mode_updated_at = CURRENT_TIMESTAMP WHERE conversation_mode = 'HUMAN_ACTIVE';"
```

---

## Performance Issues

### Problem: Slow Response Times

**Symptoms:**
- Response time > 2 seconds
- User complaints about delays

**Diagnosis:**

1. **Check latency in traces:**
   ```bash
   docker exec luisa-backend sqlite3 /app/data/luisa.db \
     "SELECT AVG(latency_ms), MAX(latency_ms), COUNT(*) FROM interaction_traces WHERE created_at > datetime('now', '-1 hour');"
   ```

2. **Check OpenAI calls:**
   ```bash
   docker compose logs --tail=200 backend | grep -i "openai\|elapsed_ms"
   ```

3. **Check cache hit rate:**
   ```bash
   curl -s http://localhost:8000/api/cache/stats | jq .
   ```

**Common Causes:**
- OpenAI API slow (timeout issues)
- Cache disabled or low hit rate
- Database queries slow
- Network latency

**Fix:**
- Enable cache: `CACHE_ENABLED=true`
- Check OpenAI timeout: `OPENAI_TIMEOUT_SECONDS=8`
- Monitor cache hit rate
- Optimize database queries

---

### Problem: Rate Limiting Too Aggressive

**Symptoms:**
- Legitimate users getting 429 errors
- Rate limit logs frequent

**Diagnosis:**

1. **Check rate limit configuration:**
   ```bash
   # WhatsApp: 20 req/min per phone
   # API: 30 req/min per conversation_id
   ```

2. **Check rate limit logs:**
   ```bash
   docker compose logs --tail=200 backend | grep -i "rate.*limit\|429"
   ```

**Fix:**
- Adjust limits in code if needed
- Verify rate limit key (phone vs conversation_id)
- Check for rate limit bypass bugs

---

## Database Issues

### Problem: Database Locked

**Symptoms:**
- SQLite errors: "database is locked"
- Writes failing

**Diagnosis:**

1. **Check database file permissions:**
   ```bash
   ls -la /opt/luisa/data/luisa.db
   ```

2. **Check for long-running queries:**
   ```bash
   docker exec luisa-backend sqlite3 /app/data/luisa.db ".timeout 5000"
   ```

**Fix:**
- SQLite configured with WAL mode (better concurrency)
- Set busy timeout: `PRAGMA busy_timeout=3000`
- Check for connection leaks

---

### Problem: Database Not Initialized

**Symptoms:**
- Tables missing
- `sqlite3.OperationalError: no such table`

**Fix:**
```bash
# Initialize database
docker compose exec backend python scripts/init_db.py

# Verify tables
docker exec luisa-backend sqlite3 /app/data/luisa.db ".tables"
```

---

## Infrastructure Issues

### Problem: Containers Not Starting

**Symptoms:**
- `docker compose up -d` fails
- Containers exit immediately

**Diagnosis:**

1. **Check container logs:**
   ```bash
   docker compose logs backend
   docker compose logs caddy
   ```

2. **Check container status:**
   ```bash
   docker compose ps -a
   ```

3. **Check resource limits:**
   ```bash
   docker stats --no-stream
   free -h
   ```

**Common Causes:**
- Out of memory (OOM)
- Port conflicts
- Volume mount issues
- Environment variables missing

**Fix:**
- Free memory: `docker system prune -af`
- Check port availability: `netstat -tulpn | grep 8000`
- Verify volume mounts in `docker-compose.yml`
- Check `.env` file exists and is readable

---

### Problem: Caddy SSL Certificate Issues

**Symptoms:**
- HTTPS not working
- Certificate errors
- Caddy logs show certificate errors

**Diagnosis:**

1. **Check Caddy logs:**
   ```bash
   docker compose logs caddy | grep -i "certificate\|ssl\|tls"
   ```

2. **Verify domain DNS:**
   ```bash
   dig luisa-agent.online
   nslookup luisa-agent.online
   ```

3. **Check Caddyfile:**
   ```bash
   cat Caddyfile
   ```

**Common Causes:**
- Domain not pointing to server IP
- DNS propagation delay
- Let's Encrypt rate limits
- Firewall blocking port 80/443

**Fix:**
- Verify DNS: `dig luisa-agent.online` → should return server IP
- Wait for DNS propagation (up to 48 hours)
- Check firewall: `sudo ufw status`
- Restart Caddy: `docker compose restart caddy`

---

## Quick Diagnostic Commands

### System Health

```bash
# Containers status
docker compose ps

# Resource usage
docker stats --no-stream
free -h
df -h

# Health checks
curl http://localhost:8000/health
curl https://luisa-agent.online/health
```

### Logs Analysis

```bash
# Recent errors
docker compose logs --tail=500 backend | grep -i "error\|exception\|traceback" | tail -20

# WhatsApp activity
docker compose logs --tail=500 backend | grep -i "whatsapp\|webhook" | tail -20

# Handoff activity
docker compose logs --tail=500 backend | grep -i "handoff\|human_active" | tail -20

# Performance metrics
docker compose logs --tail=500 backend | grep -i "elapsed_ms\|latency" | tail -20
```

### Database Queries

```bash
# Recent messages
docker exec luisa-backend sqlite3 /app/data/luisa.db \
  "SELECT text, sender, timestamp FROM messages ORDER BY timestamp DESC LIMIT 10;"

# Conversation modes
docker exec luisa-backend sqlite3 /app/data/luisa.db \
  "SELECT conversation_id, conversation_mode, mode_updated_at FROM conversations ORDER BY updated_at DESC LIMIT 10;"

# Recent handoffs
docker exec luisa-backend sqlite3 /app/data/luisa.db \
  "SELECT conversation_id, reason, priority, timestamp FROM handoffs ORDER BY timestamp DESC LIMIT 10;"

# Trace statistics
docker exec luisa-backend sqlite3 /app/data/luisa.db \
  "SELECT COUNT(*), AVG(latency_ms), MAX(latency_ms) FROM interaction_traces WHERE created_at > datetime('now', '-1 hour');"
```

---

## Getting Help

If issues persist:

1. **Collect diagnostics:**
   ```bash
   # Save logs
   docker compose logs > luisa-logs-$(date +%Y%m%d).txt
   
   # Save database info
   docker exec luisa-backend sqlite3 /app/data/luisa.db ".schema" > schema.txt
   
   # Save environment (sanitized)
   docker exec luisa-backend env | grep -E "WHATSAPP|OPENAI|HUMAN_TTL" > env-sanitized.txt
   ```

2. **Check documentation:**
   - `DEPLOYMENT.md` for deployment issues
   - `ARCHITECTURE.md` for system design
   - `SECURITY.md` for security concerns

3. **Review recent changes:**
   - Check `CHANGELOG.md`
   - Review git history for recent commits

---

**Last Updated**: 2025-01-XX

