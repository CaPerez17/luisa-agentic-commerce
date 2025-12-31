#!/bin/bash
# Script de PROVISIONAMIENTO para VPS pequeños (512MB-1GB RAM)
# 
# Uso: sudo ./provision.sh
#
# Ejecuta UNA SOLA VEZ para:
# - Instalar Docker
# - Configurar firewall (UFW)
# - Clonar repositorio

set -euo pipefail

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuración
REPO_URL="https://github.com/CaPerez17/luisa-agentic-commerce.git"
APP_DIR="/opt/luisa"

log_info() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] [INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] [WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] [ERROR]${NC} $1"
}

# Verificar root
if [ "$EUID" -ne 0 ]; then
    log_error "Ejecuta con sudo: sudo ./provision.sh"
    exit 1
fi

echo "=========================================="
log_info "🚀 PROVISIONAMIENTO LUISA"
log_warn "⚠️  Tiempo estimado: 5-10 minutos"
log_warn "⚠️  NO CANCELES el proceso"
echo "=========================================="

# ============================================================================
# 1. Esperar procesos apt
# ============================================================================
log_info "Esperando procesos apt..."

MAX_WAIT=180
WAITED=0

while pgrep -x apt >/dev/null 2>&1 || \
      pgrep -x apt-get >/dev/null 2>&1 || \
      pgrep -x dpkg >/dev/null 2>&1 || \
      fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
    
    if [ $WAITED -ge $MAX_WAIT ]; then
        log_error "Procesos apt siguen activos después de ${MAX_WAIT}s"
        exit 1
    fi
    
    log_info "   Esperando... (${WAITED}s/${MAX_WAIT}s)"
    sleep 10
    WAITED=$((WAITED + 10))
done

log_info "✅ No hay procesos apt activos"

# ============================================================================
# 2. Configurar UFW (SSH primero!)
# ============================================================================
log_info "🔥 Configurando firewall..."

export DEBIAN_FRONTEND=noninteractive

# Instalar UFW si no está
apt-get update -qq
apt-get install -yqq ufw curl git

# CRÍTICO: SSH primero
if ! ufw status 2>/dev/null | grep -q "22/tcp.*ALLOW"; then
    log_warn "Agregando regla SSH..."
    ufw allow 22/tcp comment 'SSH'
    
    if ! ufw status 2>/dev/null | grep -q "22/tcp.*ALLOW"; then
        log_error "CRÍTICO: No se pudo agregar regla SSH"
        exit 1
    fi
fi
log_info "✅ SSH permitido"

# Otras reglas
ufw allow 80/tcp comment 'HTTP' || true
ufw allow 443/tcp comment 'HTTPS' || true
ufw allow 443/udp comment 'HTTPS/QUIC' || true

# Activar UFW
if ! ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw --force enable
fi
log_info "✅ UFW activo"

# ============================================================================
# 3. Instalar Docker
# ============================================================================
log_info "🐳 Instalando Docker..."

if command -v docker &> /dev/null; then
    log_info "Docker ya instalado"
else
    # Instalar Docker usando el script oficial
    curl -fsSL https://get.docker.com | sh
    
    # Agregar usuario ubuntu al grupo docker
    usermod -aG docker ubuntu 2>/dev/null || true
    
    # Iniciar Docker
    systemctl enable docker
    systemctl start docker
    
    # Esperar a que Docker esté listo
    for i in {1..12}; do
        if docker info >/dev/null 2>&1; then
            log_info "✅ Docker funcionando"
            break
        fi
        sleep 5
    done
fi

# Verificar Docker Compose
if ! docker compose version &> /dev/null; then
    log_error "Docker Compose no disponible"
    exit 1
fi
log_info "✅ Docker Compose disponible"

# ============================================================================
# 4. Clonar repositorio
# ============================================================================
log_info "📥 Clonando repositorio..."

mkdir -p "$APP_DIR"
cd "$APP_DIR"

if [ -d ".git" ]; then
    log_info "Repositorio existe, actualizando..."
    git fetch origin
    git reset --hard origin/main
    git clean -fd
else
    git clone "$REPO_URL" .
fi

# Crear directorio de datos
mkdir -p data
chown -R ubuntu:ubuntu data 2>/dev/null || true

log_info "✅ Repositorio en $APP_DIR"

# ============================================================================
# 5. Crear .env
# ============================================================================
if [ ! -f ".env" ]; then
    cp .env.example .env
    chmod 600 .env
    chown ubuntu:ubuntu .env 2>/dev/null || true
    log_warn "⚠️  Edita .env con tus credenciales"
fi

# ============================================================================
# Fin
# ============================================================================
echo ""
echo "=========================================="
log_info "✅ PROVISIONAMIENTO COMPLETADO"
echo "=========================================="
echo ""
echo "Próximos pasos:"
echo "1. Edita credenciales: sudo nano /opt/luisa/.env"
echo "2. Despliega: cd /opt/luisa && sudo ./deploy.sh"
echo ""
echo "Verificaciones:"
echo "  docker --version"
echo "  sudo ufw status"
echo ""
echo "=========================================="
