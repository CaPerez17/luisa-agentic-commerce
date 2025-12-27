# 🔒 Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in LUISA, please report it by emailing:
- **Security Contact**: [Your Security Email]

**Do not** create a public GitHub issue for security vulnerabilities.

We will respond within 48 hours and provide a timeline for fixes.

---

## Security Considerations

### 1. **API Keys & Secrets**

#### ❌ Never Commit:
- OpenAI API keys (`sk-proj-...`)
- WhatsApp access tokens
- Service account JSON files
- Private keys (`.pem`, `.key`)
- `.env` files

#### ✅ Best Practices:
- Use `.env` for all secrets (already in `.gitignore`)
- Rotate API keys if accidentally committed
- Use environment-specific secrets (dev/staging/prod)
- Audit git history: `git log --all -p | grep -i "sk-"`

### 2. **Customer Data Protection**

#### Sensitive Data:
- Customer phone numbers (hashed in traces)
- Conversation history
- Personal information in messages

#### Protections:
- Phone numbers are hashed with SHA-256 in `interaction_traces`
- No credit card or payment info is stored
- Conversations can be deleted on request

#### GDPR/Privacy:
- Implement data retention policy (delete old conversations)
- Provide data export API for customer requests
- Add consent tracking if required by jurisdiction

### 3. **Database Security**

#### SQLite Hardening:
```bash
# Restrict file permissions
chmod 600 backend/luisa.db

# Encrypt backups
gpg --encrypt luisa-backup.db

# Regular backups (automated)
sqlite3 luisa.db ".backup 'backup.db'"
```

#### Migration to PostgreSQL (Production):
- Recommended for multi-instance deployments
- Enables row-level security
- Better concurrent access control

### 4. **API Security**

#### Current State:
- No authentication on `/api/chat` (demo mode)
- CORS enabled for local development

#### Production Hardening:
```python
# Add to main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat")
@limiter.limit("10/minute")  # Rate limiting
async def chat(request: Request, payload: ChatPayload):
    # Add API key check
    api_key = request.headers.get("X-API-Key")
    if api_key != os.getenv("INTERNAL_API_KEY"):
        raise HTTPException(403, "Forbidden")
    ...
```

### 5. **WhatsApp Webhook Security**

#### Verification:
- Verify webhook signature from Meta
- Use secure `WHATSAPP_VERIFY_TOKEN`
- Whitelist WhatsApp IP ranges

```python
# Verify Meta signature
import hmac
import hashlib

def verify_webhook_signature(payload, signature):
    expected = hmac.new(
        WHATSAPP_APP_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 6. **OpenAI Security**

#### Guardrails (Already Implemented):
- Input sanitization (max 1200 chars)
- Business topic whitelist
- Cost controls (max tokens, timeouts)
- Forbidden word filtering

#### Additional:
- Monitor usage: https://platform.openai.com/usage
- Set spending limits in OpenAI dashboard
- Review logs for prompt injection attempts

### 7. **Dependency Security**

#### Regular Audits:
```bash
# Check for vulnerabilities
pip install safety
safety check

# Update dependencies
pip-review --auto

# Lock versions
pip freeze > requirements.txt
```

#### Known Secure Versions:
- Python 3.10+
- FastAPI 0.104+
- httpx 0.25+

### 8. **Network Security**

#### Production Deployment:
- Use HTTPS only (no HTTP)
- Reverse proxy (Nginx, Caddy) with TLS 1.3
- Firewall rules (only expose 443, 8000 internally)

```nginx
# Nginx example
server {
    listen 443 ssl http2;
    server_name luisa.elsastre.com;
    
    ssl_certificate /etc/letsencrypt/live/luisa.elsastre.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/luisa.elsastre.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 9. **Code Injection Prevention**

#### SQL Injection:
- ✅ Uses parameterized queries (safe)
```python
# Safe
cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
```

#### Prompt Injection:
- ✅ Input length limits
- ✅ Business topic whitelist
- ✅ Forbidden phrases filter

### 10. **Logging & Monitoring**

#### What to Log:
- API requests (sanitized)
- OpenAI usage (tokens, cost)
- Handoff triggers
- Error traces

#### What NOT to Log:
- API keys
- Customer passwords (if implementing auth)
- Raw customer personal data

#### Log Rotation:
```bash
# /etc/logrotate.d/luisa
/var/log/luisa/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
}
```

---

## Security Checklist (Pre-Production)

- [ ] All secrets in `.env` (not hardcoded)
- [ ] `.env` in `.gitignore`
- [ ] Git history audited for leaked keys
- [ ] API keys rotated (if previously exposed)
- [ ] Rate limiting enabled
- [ ] HTTPS enabled
- [ ] Webhook signature verification
- [ ] Database file permissions (600)
- [ ] Dependency vulnerability scan
- [ ] Error messages don't leak info
- [ ] Logs sanitized (no secrets)
- [ ] Backup encryption enabled
- [ ] Customer data retention policy defined
- [ ] Incident response plan documented

---

## Incident Response

### If API Key is Leaked:
1. **Immediately revoke** the key in OpenAI/WhatsApp dashboard
2. Generate new key
3. Update `.env` in production
4. Restart services
5. Review usage logs for unauthorized access
6. Notify stakeholders if abuse detected

### If Database is Compromised:
1. Take services offline
2. Restore from encrypted backup
3. Rotate all API keys
4. Audit access logs
5. Notify affected customers (if required by law)

---

## Compliance

### GDPR (If applicable):
- Implement data export API
- Add "Right to be Forgotten" (delete conversations)
- Log consent for data processing
- Provide privacy policy

### PCI DSS (If handling payments):
- **Do not store** credit card numbers
- Use payment gateway (Stripe, PayPal)
- Only store transaction IDs

---

## Contact

**Security Issues**: [Your Security Email]  
**General Support**: [Your Support Email]

**Last Updated**: 2025-12-27
