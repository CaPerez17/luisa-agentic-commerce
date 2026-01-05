# 🚀 Deployment Guide - LUISA

Complete guide for deploying LUISA to production using Docker Compose.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Production Deployment](#production-deployment)
4. [Configuration](#configuration)
5. [Verification & Testing](#verification--testing)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance](#maintenance)

---

## Prerequisites

### Infrastructure Requirements

- **Server**: Ubuntu 22.04+ (AWS Lightsail recommended)
- **Resources**: Minimum 512MB RAM, 1GB recommended
- **Domain**: Pointing to server IP (e.g., `luisa-agent.online`)
- **Docker**: Docker 20.10+ and Docker Compose v2+
- **Ports**: 80 (HTTP), 443 (HTTPS) open in firewall

### Pre-Deployment Checklist

- [ ] All secrets removed from codebase
- [ ] `.env` file configured with production credentials
- [ ] `.env` file in `.gitignore` (verified)
- [ ] API keys rotated if previously committed
- [ ] Database backup strategy in place

---

## Quick Start

### Option 1: Automated Deployment Script (Recommended)

```bash
# 1. Provision server (first time only)
sudo ./provision.sh

# 2. Deploy application
sudo ./deploy.sh
```

The `deploy.sh` script is **idempotent** and can be run multiple times safely.

### Option 2: Manual Docker Compose

```bash
# 1. Build images
docker compose build

# 2. Start services
docker compose up -d

# 3. Verify health
curl http://localhost:8000/health
```

---

## Production Deployment

### Architecture

```
Internet
   ↓
Caddy (Port 80/443) → Automatic HTTPS with Let's Encrypt
   ↓
Backend (Port 8000, localhost only) → FastAPI + SQLite
```

### Step-by-Step Deployment

#### 1. Server Setup

```bash
# Connect to server
ssh -i ~/.ssh/your-key.pem user@your-server-ip

# Clone repository
git clone <repository-url> /opt/luisa
cd /opt/luisa
```

#### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit with production values
nano .env
```

**Required variables:**
```bash
# WhatsApp Configuration
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=EAA...          # From Meta Business Dashboard
WHATSAPP_PHONE_NUMBER_ID=...          # From Meta Business Dashboard
WHATSAPP_VERIFY_TOKEN=secure-token    # Must match Meta dashboard
TEST_NOTIFY_NUMBER=+57XXXXXXXXXX      # Internal notifications

# OpenAI (optional)
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-...

# Production Settings
PRODUCTION_MODE=true
LOG_FORMAT=json
LOG_LEVEL=INFO

# Shadow Mode TTL
HUMAN_TTL_HOURS=12                    # Hours before reverting HUMAN_ACTIVE
HANDOFF_COOLDOWN_MINUTES=30           # Cooldown after handoff
```

#### 3. Deploy with Docker Compose

```bash
# Build and start services
docker compose up -d

# Verify containers are running
docker compose ps

# Check logs
docker compose logs -f backend
```

#### 4. Verify Deployment

```bash
# Health check local
curl http://localhost:8000/health

# Health check public (may take 1-2 min for SSL)
curl https://luisa-agent.online/health

# Verify HTTPS certificate
echo | openssl s_client -connect luisa-agent.online:443 -servername luisa-agent.online 2>/dev/null | openssl x509 -noout -dates
```

---

## Configuration

### WhatsApp Webhook Setup

1. **Meta Business Dashboard:**
   - Go to WhatsApp > Configuration
   - Set **Callback URL**: `https://luisa-agent.online/whatsapp/webhook`
   - Set **Verify Token**: Must match `WHATSAPP_VERIFY_TOKEN` in `.env`
   - Click "Verify and Save"

2. **Verify Webhook:**
   ```bash
   curl -v "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=TEST123"
   ```
   **Expected:** Status 200, Body `TEST123`

3. **Subscribe to Events:**
   - In Meta Dashboard: WhatsApp > Webhooks > Edit Subscription
   - Enable: `messages` (required)
   - Optional: `message_deliveries`, `message_reads`

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WHATSAPP_ENABLED` | Yes | `false` | Enable WhatsApp integration |
| `WHATSAPP_ACCESS_TOKEN` | Yes* | - | Meta Graph API access token |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes* | - | WhatsApp Business phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | Yes* | - | Webhook verification token |
| `OPENAI_ENABLED` | No | `false` | Enable OpenAI integration |
| `OPENAI_API_KEY` | No* | - | OpenAI API key |
| `PRODUCTION_MODE` | Yes | `false` | Enable production settings |
| `HUMAN_TTL_HOURS` | No | `12` | Hours before reverting HUMAN_ACTIVE mode |
| `DB_PATH` | No | `luisa.db` | SQLite database path |

*Required if corresponding feature is enabled

---

## Verification & Testing

### GO/NO-GO Checklist

Before going live, verify all critical flows:

#### 1. Infrastructure

- [ ] Docker containers running (`docker compose ps`)
- [ ] Health check local OK (`curl http://localhost:8000/health`)
- [ ] Health check public OK (`curl https://luisa-agent.online/health`)
- [ ] HTTPS certificate valid (not expired)
- [ ] Environment variables configured correctly

#### 2. WhatsApp Integration

- [ ] Webhook GET verification works
- [ ] Webhook POST receives messages
- [ ] Messages trigger logs in backend
- [ ] No 4xx/5xx errors when responding
- [ ] Rate limiting works (20 req/min)

#### 3. Critical Business Flows

- [ ] **Flow 1**: New user → Greeting → LUISA responds
- [ ] **Flow 2**: LUISA proposes advisor → User says "yes" → Handoff triggered
- [ ] **Flow 3**: User writes "Hello" after handoff → LUISA responds (FIX P0: no silence)
- [ ] **Flow 4**: Wait TTL → User writes → LUISA reverts to AI_ACTIVE (FIX P1: TTL works)

#### 4. Logs Verification

- [ ] `reply_sent_in_human_active` present when responding in HUMAN_ACTIVE mode
- [ ] `mode_auto_reverted_to_ai` present when TTL expires
- [ ] No critical errors in logs (`docker compose logs backend | grep -i error`)

#### 5. Performance

- [ ] Response time < 2s average
- [ ] Rate limiting prevents abuse

**GO Criteria:** All checks pass, no silent failures, no critical errors.

### Testing Commands

```bash
# Verify containers
docker compose ps

# Check environment variables
docker exec luisa-backend python -c "from app.config import WHATSAPP_ENABLED, HUMAN_TTL_HOURS; print(f'WHATSAPP: {WHATSAPP_ENABLED}, TTL: {HUMAN_TTL_HOURS}')"

# Monitor logs
docker compose logs -f backend

# Check database
docker exec luisa-backend sqlite3 /app/data/luisa.db "SELECT COUNT(*) FROM messages WHERE timestamp > datetime('now', '-1 hour');"

# Test webhook verification
curl -v "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=TEST123"
```

---

## Troubleshooting

### Common Issues

#### Backend Not Responding

```bash
# Check logs
docker compose logs backend

# Restart backend
docker compose restart backend

# Verify health check
curl http://localhost:8000/health
```

#### Caddy SSL Certificate Issues

```bash
# Check Caddy logs
docker compose logs caddy

# Verify domain DNS
dig luisa-agent.online

# Force certificate renewal (if needed)
docker compose restart caddy
```

#### WhatsApp Webhook Not Receiving Messages

1. **Verify webhook URL in Meta Dashboard:**
   - Must be exactly: `https://luisa-agent.online/whatsapp/webhook`
   - No trailing slash

2. **Check verify token:**
   ```bash
   docker exec luisa-backend python -c "from app.config import WHATSAPP_VERIFY_TOKEN; print(WHATSAPP_VERIFY_TOKEN[:10])"
   ```
   Must match Meta Dashboard exactly (case-sensitive)

3. **Check webhook subscription:**
   - In Meta Dashboard: WhatsApp > Webhooks > Edit Subscription
   - Ensure `messages` is enabled

4. **Test webhook manually:**
   ```bash
   curl -v "https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=TEST123"
   ```

#### Out of Memory (OOM) Errors

If deploying on small VPS (512MB):

```bash
# Free up memory
docker system prune -af

# Check memory usage
free -h
docker stats --no-stream

# Consider upgrading VPS or adding swap
```

#### Database Issues

```bash
# Initialize database
docker compose exec backend python scripts/init_db.py

# Check database permissions
ls -la /opt/luisa/data/luisa.db

# Backup database
docker compose exec backend sqlite3 /app/data/luisa.db ".backup /app/data/luisa-backup.db"
```

---

## Maintenance

### Regular Tasks

#### View Logs

```bash
# All services
docker compose logs -f

# Backend only
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend
```

#### Restart Services

```bash
# All services
docker compose restart

# Backend only
docker compose restart backend

# Caddy only
docker compose restart caddy
```

#### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose build --no-cache
docker compose up -d

# Verify health
curl http://localhost:8000/health
```

#### Database Backup

```bash
# Create backup
docker compose exec backend sqlite3 /app/data/luisa.db ".backup /app/data/luisa-$(date +%Y%m%d).db"

# Copy backup from container
docker cp luisa-backend:/app/data/luisa-$(date +%Y%m%d).db ./backups/
```

### Monitoring

#### Health Checks

- **Local**: `http://localhost:8000/health`
- **Public**: `https://luisa-agent.online/health`
- **Expected Response:**
  ```json
  {
    "status": "healthy",
    "service": "luisa",
    "version": "2.0.0",
    "whatsapp_enabled": true
  }
  ```

#### Resource Usage

```bash
# Container stats
docker stats --no-stream

# Disk usage
df -h
docker system df
```

### Security

- **Firewall**: Only ports 22, 80, 443 open
- **Secrets**: All in `.env` (not committed)
- **Logs**: Masked PII (phone numbers show last 4 digits only)
- **Rate Limiting**: 20 req/min per phone number (WhatsApp), 30 req/min per conversation (API)

---

## Additional Resources

- **Architecture**: See `ARCHITECTURE.md` for system design details
- **Troubleshooting**: See `TROUBLESHOOTING.md` for detailed diagnostics
- **Security**: See `SECURITY.md` for security best practices
- **Changelog**: See `CHANGELOG.md` for version history

---

**Last Updated**: 2025-01-XX
