#!/bin/bash

# Go/No-Go checks antes de deploy (P1-2)
echo "🔍 Ejecutando Go/No-Go checks..."
cd "$(dirname "$0")"
python3 backend/scripts/go_no_go.py --hard-fail
if [ $? -ne 0 ]; then
  echo "❌ go_no_go falló. Deploy cancelado."
  exit 1
fi
echo "✅ Go/No-Go checks pasaron. Continuando con deploy..."
echo ""
# Script de DESPLIEGUE para LUISA
# Optimizado para VPS pequeños (512MB-1GB RAM)
#
# Uso: sudo ./deploy.sh
#
# PRERREQUISITOS:
# - Docker y Docker Compose instalados (ejecuta provision.sh primero)
# - Repositorio clonado en /opt/luisa
# - .env configurado

set -euo pipefail

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuración
APP_DIR="/opt/luisa"
DOMAIN="luisa-agent.online"

log_info() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] [INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] [WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] [ERROR]${NC} $1"
}

# Verificar prerrequisitos
if ! command -v docker &> /dev/null; then
    log_error "Docker no está instalado. Ejecuta primero: sudo ./provision.sh"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    log_error "Docker Compose no está disponible. Ejecuta primero: sudo ./provision.sh"
    exit 1
fi

log_info "🚀 Iniciando despliegue de LUISA..."
log_warn "⚠️  Tiempo estimado: 3-8 minutos en VPS pequeños"

# ============================================================================
# 1. Preparar directorio
# ============================================================================
log_info "📁 Preparando directorio..."
cd "$APP_DIR"

# Crear directorio de datos si no existe
mkdir -p data

# ============================================================================
# 2. Crear/Validar .env
# ============================================================================
log_info "⚙️  Verificando .env..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        log_info "Creando .env desde .env.example..."
        cp .env.example .env
        chmod 600 .env
        log_warn "⚠️  IMPORTANTE: Edita .env con tus credenciales reales"
    else
        log_error ".env.example no encontrado"
        exit 1
    fi
else
    log_info ".env ya existe"
fi

# ============================================================================
# 3. Liberar memoria antes del build
# ============================================================================
log_info "🧹 Liberando memoria para build..."

# Detener contenedores existentes
docker compose down 2>/dev/null || true

# Limpiar recursos Docker no usados
docker system prune -f 2>/dev/null || true
docker builder prune -f 2>/dev/null || true

# Mostrar memoria disponible
log_info "Memoria disponible:"
free -h | head -2

# ============================================================================
# 4. Construir imagen del backend
# ============================================================================
log_info "🔨 Construyendo imagen del backend..."
log_warn "   Esto puede tardar 3-5 minutos en VPS pequeños - NO CANCELES"

# Build con límites de memoria
if docker compose build --no-cache backend 2>&1; then
    log_info "✅ Imagen construida exitosamente"
else
    log_error "❌ Build falló"
    log_error "Posibles causas:"
    log_error "  - Memoria insuficiente (ejecuta: docker system prune -af)"
    log_error "  - Error en Dockerfile"
    exit 1
fi

# ============================================================================
# 5. Levantar servicios
# ============================================================================
log_info "🚀 Levantando servicios..."

if docker compose up -d; then
    log_info "✅ Servicios iniciados"
else
    log_error "❌ Fallo al levantar servicios"
    exit 1
fi

# ============================================================================
# 6. Esperar a que los servicios estén listos
# ============================================================================
log_info "⏳ Esperando a que los servicios estén listos..."

# Esperar hasta 90 segundos por el backend
MAX_WAIT=90
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log_info "✅ Backend responde en localhost:8000"
        break
    fi
    
    if [ $WAITED -ge $MAX_WAIT ]; then
        log_error "❌ Backend no responde después de ${MAX_WAIT}s"
        log_error "Verifica logs: docker compose logs backend"
        exit 1
    fi
    
    log_info "   Esperando backend... (${WAITED}s/${MAX_WAIT}s)"
    sleep 5
    WAITED=$((WAITED + 5))
done

# Verificar HTTPS (puede tardar por certificado SSL)
log_info "Verificando HTTPS público..."
log_warn "   El certificado SSL puede tardar 1-2 minutos en obtenerse"

if curl -sf --max-time 10 https://$DOMAIN/health > /dev/null 2>&1; then
    log_info "✅ HTTPS público funciona: https://$DOMAIN/health"
else
    log_warn "⚠️  HTTPS no responde aún (normal si es primera vez)"
    log_warn "   Caddy está obteniendo el certificado SSL"
    log_warn "   Espera 2 minutos y verifica: curl https://$DOMAIN/health"
fi

# ============================================================================
# 7. Mostrar estado final
# ============================================================================
echo ""
echo "=========================================="
log_info "✅ DESPLIEGUE COMPLETADO"
echo "=========================================="
echo ""

docker compose ps

echo ""
echo "📋 VERIFICACIONES:"
echo "  curl http://localhost:8000/health"
echo "  curl https://$DOMAIN/health"
echo ""
echo "📋 LOGS:"
echo "  docker compose logs -f backend"
echo "  docker compose logs -f caddy"
echo ""
echo "=========================================="
