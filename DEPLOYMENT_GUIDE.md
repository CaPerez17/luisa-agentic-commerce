# 🚀 Guía de Despliegue en Producción - LUISA

## Requisitos Previos

- Servidor Ubuntu 22.04+ (AWS Lightsail recomendado)
- Dominio apuntando al servidor (ej: `luisa-agent.online`)
- Acceso SSH al servidor
- Llave SSH configurada (`~/.ssh/luisa-lightsail.pem`)

## Arquitectura de Despliegue

```
Internet
   ↓
Caddy (Puerto 80/443) → HTTPS automático con Let's Encrypt
   ↓
Backend (Puerto 8000, solo localhost) → FastAPI + SQLite
```

## Pasos de Despliegue

### 1. Conectarse al Servidor

```bash
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112
```

### 2. Subir Scripts de Despliegue

Desde tu máquina local:

```bash
# Copiar scripts al servidor
scp -i ~/.ssh/luisa-lightsail.pem deploy.sh ubuntu@44.215.107.112:/tmp/
scp -i ~/.ssh/luisa-lightsail.pem diagnose.sh ubuntu@44.215.107.112:/tmp/
```

### 3. Ejecutar Script de Despliegue

En el servidor:

```bash
# Mover scripts a ubicación permanente
sudo mv /tmp/deploy.sh /opt/
sudo mv /tmp/diagnose.sh /opt/
sudo chmod +x /opt/deploy.sh /opt/diagnose.sh

# Ejecutar despliegue
sudo /opt/deploy.sh
```

El script es **idempotente**: puedes ejecutarlo múltiples veces sin problemas.

### 4. Configurar Variables de Entorno

Después del despliegue inicial, edita `.env`:

```bash
sudo nano /opt/luisa/.env
```

Configura:
- `OPENAI_API_KEY` (si usas OpenAI)
- `WHATSAPP_ACCESS_TOKEN` (si usas WhatsApp)
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_VERIFY_TOKEN` (debe ser seguro, no usar default)
- `TEST_NOTIFY_NUMBER`

Luego reinicia:

```bash
cd /opt/luisa
sudo docker compose restart backend
```

## Verificación Post-Despliegue

### Checklist

- [ ] Firewall configurado (UFW): `sudo ufw status`
- [ ] Contenedores corriendo: `docker compose ps`
- [ ] Health check local: `curl http://localhost:8000/health`
- [ ] Health check público: `curl https://luisa-agent.online/health`
- [ ] Certificado SSL válido: `curl -vI https://luisa-agent.online/health`
- [ ] Logs sin errores: `docker compose logs backend`

## Comandos Útiles

### Ver logs
```bash
cd /opt/luisa
docker compose logs -f backend    # Backend
docker compose logs -f caddy       # Caddy
docker compose logs -f             # Todos
```

### Reiniciar servicios
```bash
cd /opt/luisa
docker compose restart             # Todos
docker compose restart backend     # Solo backend
docker compose restart caddy       # Solo Caddy
```

### Detener servicios
```bash
cd /opt/luisa
docker compose down
```

### Actualizar código
```bash
cd /opt/luisa
git pull origin main
docker compose build --no-cache
docker compose up -d
```

### Verificar estado
```bash
cd /opt/luisa
docker compose ps
docker compose top
```

## Diagnóstico

Si algo falla, ejecuta el script de diagnóstico:

```bash
# Desde tu máquina local
./diagnose.sh

# O manualmente en el servidor
cd /opt/luisa
docker compose logs --tail=50 backend
docker compose logs --tail=50 caddy
curl -v http://localhost:8000/health
curl -v https://luisa-agent.online/health
```

## Seguridad

### Firewall (UFW)
- Puerto 22 (SSH): Permitido
- Puerto 80 (HTTP): Permitido (redirección a HTTPS)
- Puerto 443 (HTTPS): Permitido
- Otros puertos: Bloqueados

### Variables de Entorno
- `.env` tiene permisos 600 (solo root puede leer)
- No se commitean secretos en git
- Caddy maneja certificados SSL automáticamente

### Contenedores
- Backend corre como usuario no-root (`luisa`)
- Backend solo escucha en `127.0.0.1:8000` (no expuesto públicamente)
- Caddy actúa como reverse proxy

## Troubleshooting

### Backend no responde
```bash
docker compose logs backend
docker compose restart backend
```

### Caddy no obtiene certificado SSL
```bash
docker compose logs caddy
# Verificar que el dominio apunta al servidor
dig luisa-agent.online
```

### Error de permisos en .env
```bash
sudo chmod 600 /opt/luisa/.env
sudo chown ubuntu:ubuntu /opt/luisa/.env
```

### Base de datos no se crea
```bash
cd /opt/luisa
docker compose exec backend python scripts/init_db.py
```

## Monitoreo

### Health Checks
- Backend: `http://localhost:8000/health`
- Público: `https://luisa-agent.online/health`

### Métricas
```bash
# Uso de recursos
docker stats

# Espacio en disco
df -h

# Logs de sistema
journalctl -u docker -n 50
```

## Actualización

Para actualizar a una nueva versión:

```bash
cd /opt/luisa
git pull origin main
docker compose build --no-cache backend
docker compose up -d
docker compose logs -f backend
```

## Rollback

Si necesitas volver a una versión anterior:

```bash
cd /opt/luisa
git checkout <commit-hash>
docker compose build --no-cache backend
docker compose up -d
```

