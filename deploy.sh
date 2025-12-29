#!/bin/bash
# Script de despliegue idempotente para LUISA en producción
# Uso: ./deploy.sh

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuración
REPO_URL="https://github.com/CaPerez17/luisa-agentic-commerce.git"
APP_DIR="/opt/luisa"
DOMAIN="luisa-agent.online"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que estamos como root o con sudo
if [ "$EUID" -ne 0 ]; then
    log_error "Este script debe ejecutarse con sudo"
    exit 1
fi

log_info "🚀 Iniciando despliegue de LUISA en producción..."

# ============================================================================
# 1. Actualizar sistema
# ============================================================================
log_info "📦 Actualizando sistema..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl \
    git \
    ufw \
    ca-certificates \
    gnupg \
    lsb-release

# ============================================================================
# 2. Configurar firewall (UFW)
# ============================================================================
log_info "🔥 Configurando firewall (UFW)..."
# Permitir SSH primero (importante!)
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 443/udp comment 'HTTPS/QUIC'

# Habilitar UFW si no está activo (idempotente)
if ! ufw status | grep -q "Status: active"; then
    log_warn "UFW no está activo. Activando..."
    ufw --force enable
else
    log_info "UFW ya está activo"
fi

# ============================================================================
# 3. Instalar Docker
# ============================================================================
log_info "🐳 Verificando Docker..."
if ! command -v docker &> /dev/null; then
    log_info "Instalando Docker..."
    
    # Agregar repositorio oficial de Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Agregar usuario ubuntu al grupo docker (si existe)
    if id "ubuntu" &>/dev/null; then
        usermod -aG docker ubuntu
        log_info "Usuario ubuntu agregado al grupo docker"
    fi
    
    # Iniciar Docker
    systemctl enable docker
    systemctl start docker
    
    log_info "Docker instalado correctamente"
else
    log_info "Docker ya está instalado"
    # Asegurar que Docker está corriendo
    systemctl start docker || true
fi

# Verificar Docker Compose
if ! docker compose version &> /dev/null; then
    log_error "Docker Compose no está disponible"
    exit 1
fi

# ============================================================================
# 4. Clonar/Actualizar repositorio
# ============================================================================
log_info "📥 Clonando/actualizando repositorio..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

if [ -d ".git" ]; then
    log_info "Repositorio ya existe, actualizando..."
    git fetch origin
    git reset --hard origin/main
    git clean -fd
else
    log_info "Clonando repositorio..."
    git clone "$REPO_URL" .
fi

# ============================================================================
# 5. Crear/Validar .env
# ============================================================================
log_info "⚙️ Configurando variables de entorno..."
ENV_FILE="$APP_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    log_info "Creando .env desde .env.example..."
    cp "$APP_DIR/.env.example" "$ENV_FILE"
    
    # Generar valores por defecto seguros
    if ! grep -q "LUISA_API_KEY=" "$ENV_FILE"; then
        echo "LUISA_API_KEY=$(openssl rand -hex 32)" >> "$ENV_FILE"
    fi
    
    if ! grep -q "WHATSAPP_VERIFY_TOKEN=" "$ENV_FILE"; then
        echo "WHATSAPP_VERIFY_TOKEN=$(openssl rand -hex 16)" >> "$ENV_FILE"
    fi
    
    log_warn "⚠️  IMPORTANTE: Edita $ENV_FILE con tus credenciales reales:"
    log_warn "   - OPENAI_API_KEY (si usas OpenAI)"
    log_warn "   - WHATSAPP_ACCESS_TOKEN (si usas WhatsApp)"
    log_warn "   - WHATSAPP_PHONE_NUMBER_ID"
    log_warn "   - TEST_NOTIFY_NUMBER"
else
    log_info ".env ya existe, validando..."
    
    # Validar que tiene valores críticos
    if grep -q "OPENAI_API_KEY=sk-your" "$ENV_FILE"; then
        log_warn "OPENAI_API_KEY parece ser placeholder, actualízalo si usas OpenAI"
    fi
    
    if grep -q "WHATSAPP_VERIFY_TOKEN=luisa-verify-token-2024" "$ENV_FILE"; then
        log_warn "WHATSAPP_VERIFY_TOKEN es el default, cámbialo por seguridad"
    fi
fi

# Asegurar permisos seguros en .env
chmod 600 "$ENV_FILE"
chown ubuntu:ubuntu "$ENV_FILE" || chown root:root "$ENV_FILE"

# ============================================================================
# 6. Crear directorio de datos
# ============================================================================
log_info "📁 Creando directorios de datos..."
mkdir -p "$APP_DIR/data"
chown -R ubuntu:ubuntu "$APP_DIR/data" || chown -R root:root "$APP_DIR/data"

# Inicializar base de datos si no existe
if [ ! -f "$APP_DIR/data/luisa.db" ]; then
    log_info "Inicializando base de datos..."
    cd "$APP_DIR/backend"
    python3 -m venv venv || true
    source venv/bin/activate || true
    pip install -q -r requirements.txt || true
    python scripts/init_db.py || log_warn "No se pudo inicializar DB, se creará en el contenedor"
fi

# ============================================================================
# 7. Validar Caddyfile
# ============================================================================
log_info "🌐 Validando Caddyfile..."
CADDYFILE="$APP_DIR/Caddyfile"

if [ ! -f "$CADDYFILE" ]; then
    log_error "Caddyfile no encontrado en $APP_DIR"
    exit 1
fi

# Verificar que el dominio está correcto
if ! grep -q "$DOMAIN" "$CADDYFILE"; then
    log_warn "Caddyfile no contiene el dominio $DOMAIN, verificando..."
fi

# ============================================================================
# 8. Construir y levantar contenedores
# ============================================================================
log_info "🔨 Construyendo y levantando contenedores..."
cd "$APP_DIR"

# Parar contenedores existentes si están corriendo (idempotente)
docker compose down || true

# Construir imágenes
log_info "Construyendo imagen del backend..."
docker compose build --no-cache

# Levantar servicios
log_info "Levantando servicios..."
docker compose up -d

# Esperar a que los servicios estén saludables
log_info "Esperando a que los servicios estén listos..."
sleep 10

# ============================================================================
# 9. Verificaciones de salud
# ============================================================================
log_info "🏥 Ejecutando verificaciones de salud..."

# Verificar backend local
if curl -sf http://localhost:8000/health > /dev/null; then
    log_info "✅ Backend responde en localhost:8000"
else
    log_error "❌ Backend NO responde en localhost:8000"
    log_error "Ejecuta: docker compose logs backend"
    exit 1
fi

# Verificar HTTPS público
if curl -sf https://$DOMAIN/health > /dev/null; then
    log_info "✅ HTTPS público funciona: https://$DOMAIN/health"
else
    log_warn "⚠️  HTTPS público no responde aún (puede tardar unos minutos en obtener certificado)"
    log_warn "Verifica: docker compose logs caddy"
fi

# ============================================================================
# 10. Mostrar estado
# ============================================================================
log_info "📊 Estado de los contenedores:"
docker compose ps

log_info "📋 Logs recientes de Caddy:"
docker compose logs --tail=20 caddy || true

log_info "📋 Logs recientes del backend:"
docker compose logs --tail=20 backend || true

# ============================================================================
# Checklist de verificación
# ============================================================================
echo ""
echo "=========================================="
echo "✅ DESPLIEGUE COMPLETADO"
echo "=========================================="
echo ""
echo "📋 CHECKLIST DE VERIFICACIÓN:"
echo ""
echo "1. Firewall (UFW):"
echo "   sudo ufw status"
echo ""
echo "2. Contenedores corriendo:"
echo "   docker compose ps"
echo ""
echo "3. Health check local:"
echo "   curl http://localhost:8000/health"
echo ""
echo "4. Health check público HTTPS:"
echo "   curl https://$DOMAIN/health"
echo ""
echo "5. Logs del backend:"
echo "   docker compose logs -f backend"
echo ""
echo "6. Logs de Caddy:"
echo "   docker compose logs -f caddy"
echo ""
echo "7. Verificar certificado SSL:"
echo "   curl -vI https://$DOMAIN/health 2>&1 | grep -i certificate"
echo ""
echo "8. Reiniciar servicios si es necesario:"
echo "   docker compose restart"
echo ""
echo "9. Detener servicios:"
echo "   docker compose down"
echo ""
echo "10. Verificar variables de entorno:"
echo "    cat $ENV_FILE | grep -v '^#' | grep -v '^$'"
echo ""
echo "=========================================="
echo ""

log_info "🎉 Despliegue completado. Revisa el checklist arriba."

