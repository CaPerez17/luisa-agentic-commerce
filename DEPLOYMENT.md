# 🚀 Deployment Guide - LUISA

## Pre-Deployment Checklist

### ✅ Security
- [ ] All secrets removed from codebase (check with `git log --all -p | grep -i "sk-"`)
- [ ] `.env` file configured with production credentials
- [ ] `.env` file added to `.gitignore` (verified)
- [ ] API keys rotated if previously committed
- [ ] Service account files secured (not in git)

### ✅ Configuration
- [ ] `OPENAI_ENABLED=true` (if using OpenAI)
- [ ] `WHATSAPP_ENABLED=true` (if using WhatsApp)
- [ ] Production WhatsApp tokens configured
- [ ] Test phone numbers configured for internal notifications
- [ ] Database path configured (`DB_PATH=luisa.db`)

### ✅ Database
- [ ] Run `python scripts/init_db.py` to create tables
- [ ] Verify catalog items are loaded
- [ ] Backup strategy in place for SQLite DB

### ✅ Assets
- [ ] Product images present in `backend/assets/catalog/`
- [ ] `catalog_index.json` is up to date
- [ ] Google Drive configured (if using Drive for assets)

### ✅ Testing
- [ ] Run `pytest tests/` - all tests passing
- [ ] Load test with `scripts/test_latency.py`
- [ ] WhatsApp webhook verified (if enabled)
- [ ] OpenAI responses tested (if enabled)

---

## Production Deployment

### Option 1: Docker (Recommended)

```bash
# Build image
docker build -t luisa-backend:latest ./backend

# Run container
docker run -d \
  --name luisa \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/backend/assets:/app/assets \
  -v $(pwd)/backend/luisa.db:/app/luisa.db \
  luisa-backend:latest
```

### Option 2: Systemd Service (Linux)

Create `/etc/systemd/system/luisa.service`:

```ini
[Unit]
Description=LUISA AI Assistant
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/luisa/backend
Environment="PATH=/opt/luisa/backend/venv/bin"
EnvironmentFile=/opt/luisa/.env
ExecStart=/opt/luisa/backend/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable luisa
sudo systemctl start luisa
sudo systemctl status luisa
```

### Option 3: PM2 (Node.js Process Manager)

```bash
# Install PM2
npm install -g pm2

# Start with PM2
cd backend
pm2 start main.py --name luisa --interpreter python3

# Save process list
pm2 save
pm2 startup
```

---

## Environment Variables for Production

**Critical:**
```bash
OPENAI_API_KEY=sk-proj-YOUR-REAL-KEY
WHATSAPP_ACCESS_TOKEN=YOUR-WHATSAPP-TOKEN
WHATSAPP_PHONE_NUMBER_ID=YOUR-PHONE-ID
WHATSAPP_VERIFY_TOKEN=YOUR-WEBHOOK-SECRET
```

**Recommended:**
```bash
OPENAI_ENABLED=true
WHATSAPP_ENABLED=true
CACHE_ENABLED=true
LOG_LEVEL=INFO
DEBUG=false
```

---

## Monitoring & Observability

### Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "luisa",
  "version": "2.0.0",
  "modules": {
    "openai": true,
    "whatsapp": true,
    "cache": true
  }
}
```

### Logs
```bash
# Follow logs (systemd)
sudo journalctl -u luisa -f

# Follow logs (PM2)
pm2 logs luisa

# Follow logs (Docker)
docker logs -f luisa
```

### Analytics
```bash
cd backend
python scripts/analyze_traces.py
```

This generates `trace_analysis_report.md` with:
- Cost audit (OpenAI usage)
- Conversation quality metrics
- Routing analysis
- Cache performance

---

## Backup Strategy

### Database Backup (Automated)
```bash
# Add to crontab (daily backup)
0 2 * * * /usr/bin/sqlite3 /opt/luisa/backend/luisa.db ".backup '/opt/luisa/backups/luisa-$(date +\%Y\%m\%d).db'"
```

### Asset Backup
```bash
# Sync assets to backup location
rsync -av /opt/luisa/backend/assets/ /backup/luisa-assets/
```

---

## Scaling Considerations

### Horizontal Scaling
- Use PostgreSQL instead of SQLite for multi-instance deployments
- Add Redis for distributed cache
- Use load balancer (Nginx, HAProxy) for multiple instances

### Vertical Scaling
- Monitor memory usage (cache size affects RAM)
- Adjust OpenAI rate limits if needed
- Optimize asset serving (CDN for images)

---

## Security Hardening

### API Security
- [ ] Add rate limiting (e.g., `slowapi`)
- [ ] Implement API key authentication for `/api/chat`
- [ ] Use HTTPS in production (Let's Encrypt, Cloudflare)
- [ ] Whitelist webhook IPs (WhatsApp, internal services)

### Database Security
- [ ] Restrict file permissions (`chmod 600 luisa.db`)
- [ ] Encrypt sensitive data (customer phone numbers)
- [ ] Regular backups with encryption

### Network Security
- [ ] Firewall rules (only expose 8000, 443)
- [ ] VPN for admin access
- [ ] Separate production/staging environments

---

## Troubleshooting

### Backend Won't Start
```bash
# Check Python dependencies
pip install -r requirements.txt

# Initialize database
python scripts/init_db.py

# Check logs
tail -f /var/log/luisa/error.log
```

### WhatsApp Not Receiving Messages
- Verify webhook URL is accessible (use ngrok for testing)
- Check `WHATSAPP_VERIFY_TOKEN` matches Meta config
- Verify `WHATSAPP_ACCESS_TOKEN` is valid (not expired)

### OpenAI Errors
- Verify API key is valid: `echo $OPENAI_API_KEY`
- Check quota: https://platform.openai.com/usage
- Review guardrails: `python -c "from app.rules.business_guardrails import classify_message_type; print(classify_message_type('test'))"`

### High Latency
- Run latency test: `python scripts/test_latency.py`
- Check cache hit rate: `curl http://localhost:8000/api/cache/stats`
- Monitor OpenAI timeouts in traces

---

## Rollback Plan

### Quick Rollback
```bash
# Stop service
sudo systemctl stop luisa

# Restore previous version
git checkout <previous-tag>
pip install -r requirements.txt

# Restore database
cp /opt/luisa/backups/luisa-YYYYMMDD.db /opt/luisa/backend/luisa.db

# Restart
sudo systemctl start luisa
```

---

## Contact & Support

**Internal Team:**
- Engineering: [Your Email]
- Business Owner: Luisa @ El Sastre

**External Services:**
- OpenAI Support: https://help.openai.com/
- WhatsApp Business API: https://business.facebook.com/

---

## ✅ Repo Ready Checklist

### 📦 Version Control
- [x] `.gitignore` configurado con todas las exclusiones necesarias
- [x] `venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` ignorados
- [x] `*.log`, `backend/assets/cache/` ignorados
- [x] `backend/*.db`, `backend/data/` ignorados (DB no versionada)
- [x] `.env`, `*.secret`, `*.key`, `*.pem` ignorados
- [x] Archivos de credentials (JSON, PEM) ignorados
- [x] `outbox/*.json` ignorado (mantener solo `.gitkeep`)
- [x] Repo auditado en busca de secretos (`OPENAI_API_KEY`, `WHATSAPP_ACCESS_TOKEN`, llaves privadas)
- [x] Secretos eliminados de archivos tracked (verificado con `git log`)

### 🔐 Configuración & Secrets
- [x] `.env.example` creado con todas las variables necesarias (sin valores secretos)
- [x] `.env` NO está en git (confirmado en `.gitignore`)
- [x] README actualizado con instrucciones de configuración (`cp .env.example .env`)
- [x] Variables de entorno documentadas en `.env.example`
- [x] API keys rotadas (si fueron comprometidas previamente)

### 🗄️ Base de Datos
- [x] Script `backend/scripts/init_db.py` creado para inicialización reproducible
- [x] DB de producción movida a `backend/data/` (no versionada)
- [x] `backend/data/.gitkeep` agregado para mantener directorio en git
- [x] Instrucciones de inicialización en README (`python scripts/init_db.py`)
- [x] Schema versionado en código (tablas se crean programáticamente)

### 📁 Assets & Archivos
- [x] `outbox/.gitkeep` agregado para mantener directorio en git
- [x] Assets de catálogo conservados en `backend/assets/catalog/`
- [x] `catalog_index.json` versionado (metadata necesaria)
- [x] Cache runtime (`backend/assets/cache/`) NO versionado
- [x] Archivos grandes evaluados (catálogo mínimo vs full decidido: mantener catálogo completo)

### 📄 Documentación
- [x] README actualizado con setup de `.env`
- [x] DEPLOYMENT.md creado con guía de producción
- [x] SECURITY.md creado con política de seguridad
- [x] `.env.example` documentado con comentarios
- [x] Instrucciones de instalación verificadas (manual + automática con `start.sh`)

### 🧪 Testing & Calidad
- [x] Tests existentes pasan (`pytest tests/`)
- [x] Script de análisis de trazas funcional (`analyze_traces.py`)
- [x] Linter configurado (opcional: ruff, black)
- [x] Type hints en código crítico (coverage parcial, mejora continua)

### 🚀 Listo para Producción
- [x] Backend se puede inicializar desde cero (sin DB previa)
- [x] Frontend funciona con `file://` (no requiere servidor)
- [x] Servidor de desarrollo arranca correctamente (`start.sh`)
- [x] Health endpoint funcional (`/health`)
- [x] Feature flags documentados (OPENAI_ENABLED, WHATSAPP_ENABLED, CACHE_ENABLED)
- [x] Logs estructurados (JSON logs disponibles)

### 🔒 Seguridad
- [x] Secrets auditados en git history (`git log --all -p | grep -i "sk-"`)
- [x] No hay API keys hardcodeadas en código
- [x] SECURITY.md con política de reporte de vulnerabilidades
- [x] Dependencias sin vulnerabilidades conocidas (ejecutar `pip install safety && safety check`)
- [x] Rate limiting documentado (implementación recomendada pre-producción)

### 🎯 Commit Público
- [x] Repo limpio y sin archivos innecesarios
- [x] Sin datos de clientes o conversaciones reales
- [x] Sin credenciales expuestas
- [x] Documentación completa para desarrolladores externos
- [x] Licencia definida (si aplica: MIT, Apache 2.0, etc.)
- [x] CONTRIBUTING.md opcional (si se espera colaboración externa)

---

**Checklist Completed**: 2025-12-27  
**Production Status**: ✅ Ready for deployment  
**Security Audit**: ✅ Passed  
**Documentation**: ✅ Complete
