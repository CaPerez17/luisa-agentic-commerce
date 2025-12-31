#!/bin/bash
# Script wrapper seguro para ejecutar provision.sh
# Uso: ./run_provision_safe.sh
#
# Este script ejecuta verificaciones PRE-ejecución críticas antes de
# ejecutar provision.sh. Si alguna verificación falla, ABORTA.

set -euo pipefail

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] [INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] [WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] [ERROR]${NC} $1"
}

log_abort() {
    log_error "🚨 ABORTANDO: $1"
    exit 1
}

echo "=========================================="
echo "🔒 VERIFICACIÓN PRE-EJECUCIÓN: provision.sh"
echo "=========================================="
echo ""

# ============================================================================
# A) Verificar acceso SSH seguro (UFW)
# ============================================================================
log_info "A) Verificando acceso SSH seguro (UFW)..."

if sudo ufw status verbose 2>/dev/null | grep -q "22/tcp.*ALLOW"; then
    log_info "✅ SSH (22/tcp) está permitido en UFW"
elif sudo ufw status 2>/dev/null | grep -q "Status: active"; then
    log_abort "SSH (22/tcp) NO está permitido pero UFW está activo. Esto es PELIGROSO."
else
    log_warn "UFW no está activo aún (normal en primera ejecución)"
fi

# ============================================================================
# B) Verificar procesos apt activos
# ============================================================================
log_info "B) Verificando procesos apt activos..."

MAX_WAIT=120
WAITED=0

while systemctl is-active --quiet apt-daily.service 2>/dev/null || \
      systemctl is-active --quiet apt-daily-upgrade.service 2>/dev/null || \
      systemctl is-active --quiet unattended-upgrades.service 2>/dev/null || \
      pgrep -x apt >/dev/null 2>&1 || \
      pgrep -x apt-get >/dev/null 2>&1 || \
      pgrep -x dpkg >/dev/null 2>&1; do
    
    if [ $WAITED -ge $MAX_WAIT ]; then
        log_abort "Procesos apt siguen activos después de ${MAX_WAIT}s. Espera y reintenta."
    fi
    
    log_warn "Procesos apt activos detectados, esperando... (${WAITED}s/${MAX_WAIT}s)"
    sleep 5
    WAITED=$((WAITED + 5))
done

log_info "✅ No hay procesos apt activos"

# ============================================================================
# C) Verificar espacio en disco
# ============================================================================
log_info "C) Verificando espacio en disco..."

AVAILABLE=$(df -BG / | tail -1 | awk '{print $4}' | sed 's/G//')
REQUIRED=2

if [ -z "$AVAILABLE" ] || [ "$AVAILABLE" -lt "$REQUIRED" ]; then
    log_abort "Espacio insuficiente: ${AVAILABLE}GB disponible, se requieren ${REQUIRED}GB mínimo"
fi

log_info "✅ Espacio disponible: ${AVAILABLE}GB (requerido: ${REQUIRED}GB)"

# ============================================================================
# D) Verificar conectividad básica
# ============================================================================
log_info "D) Verificando conectividad de red..."

if ping -c 2 -W 5 8.8.8.8 >/dev/null 2>&1; then
    log_info "✅ Conectividad a internet OK"
elif curl --max-time 5 -s https://archive.ubuntu.com >/dev/null 2>&1; then
    log_info "✅ Conectividad a repositorios Ubuntu OK"
else
    log_abort "Sin conectividad de red. Verifica tu conexión a internet."
fi

# ============================================================================
# E) Verificar permisos
# ============================================================================
log_info "E) Verificando permisos..."

# Verificar usuario
if [ "$(whoami)" != "ubuntu" ]; then
    log_warn "Usuario actual: $(whoami) (esperado: ubuntu)"
fi

# Verificar sudo sin password
if sudo -n true 2>/dev/null; then
    log_info "✅ Sudo funciona sin contraseña"
else
    log_abort "Sudo requiere contraseña. Ejecuta: sudo ./run_provision_safe.sh"
fi

# ============================================================================
# RESUMEN PRE-VERIFICACIONES
# ============================================================================
echo ""
echo "=========================================="
log_info "✅ TODAS LAS VERIFICACIONES PRE-EJECUCIÓN PASARON"
echo "=========================================="
echo ""
log_warn "🚨 NO CANCELAR: este proceso puede tardar 5-15 minutos en VPS pequeños"
log_warn "🚨 Los tiempos largos en apt-get son NORMALES - NO canceles"
echo ""
read -p "Presiona ENTER para continuar con provision.sh (Ctrl+C para abortar): " -r
echo ""

# ============================================================================
# EJECUTAR provision.sh
# ============================================================================
PROVISION_SCRIPT="./provision.sh"
if [ ! -f "$PROVISION_SCRIPT" ]; then
    PROVISION_SCRIPT="/opt/provision.sh"
fi

if [ ! -f "$PROVISION_SCRIPT" ]; then
    log_abort "provision.sh no encontrado en ./ ni /opt/"
fi

log_info "🚀 Ejecutando provision.sh..."
log_info "   Logs guardados en: provision.log"
echo ""

# Ejecutar provision.sh con logging
sudo bash "$PROVISION_SCRIPT" 2>&1 | tee provision.log

PROVISION_EXIT_CODE=${PIPESTATUS[0]}

if [ $PROVISION_EXIT_CODE -ne 0 ]; then
    log_error "❌ provision.sh falló con código de salida: $PROVISION_EXIT_CODE"
    log_error "Revisa provision.log para detalles"
    exit $PROVISION_EXIT_CODE
fi

echo ""
echo "=========================================="
log_info "✅ provision.sh completado exitosamente"
echo "=========================================="
echo ""

# ============================================================================
# VERIFICACIONES POST-EJECUCIÓN
# ============================================================================
log_info "🔍 Ejecutando verificaciones POST-ejecución..."

POST_ERRORS=0

# 1) Confirmar SSH sigue permitido
log_info "1) Verificando SSH sigue permitido..."
if sudo ufw status 2>/dev/null | grep -q "22/tcp.*ALLOW"; then
    log_info "   ✅ SSH (22/tcp) permitido"
else
    log_error "   ❌ SSH (22/tcp) NO permitido - VERIFICAR MANUALMENTE"
    POST_ERRORS=$((POST_ERRORS + 1))
fi

# 2) Confirmar Docker funcionando
log_info "2) Verificando Docker..."
if docker --version >/dev/null 2>&1; then
    DOCKER_VERSION=$(docker --version)
    log_info "   ✅ Docker instalado: $DOCKER_VERSION"
    
    if docker info >/dev/null 2>&1; then
        log_info "   ✅ Docker funcionando correctamente"
    else
        log_error "   ❌ Docker instalado pero no responde"
        POST_ERRORS=$((POST_ERRORS + 1))
    fi
else
    log_error "   ❌ Docker NO instalado"
    POST_ERRORS=$((POST_ERRORS + 1))
fi

# 3) Confirmar Docker Compose
log_info "3) Verificando Docker Compose..."
if docker compose version >/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version)
    log_info "   ✅ Docker Compose disponible: $COMPOSE_VERSION"
else
    log_error "   ❌ Docker Compose NO disponible"
    POST_ERRORS=$((POST_ERRORS + 1))
fi

# 4) Confirmar UFW activo
log_info "4) Verificando UFW..."
if sudo ufw status 2>/dev/null | grep -q "Status: active"; then
    log_info "   ✅ UFW está activo"
    sudo ufw status | grep -E "22/tcp|80/tcp|443/tcp" | while read -r line; do
        log_info "   ✅ Regla: $line"
    done
else
    log_error "   ❌ UFW NO está activo"
    POST_ERRORS=$((POST_ERRORS + 1))
fi

# 5) Confirmar directorios esperados
log_info "5) Verificando directorios..."
if [ -d "/opt/luisa" ]; then
    log_info "   ✅ /opt/luisa existe"
else
    log_error "   ❌ /opt/luisa NO existe"
    POST_ERRORS=$((POST_ERRORS + 1))
fi

# ============================================================================
# RESUMEN FINAL
# ============================================================================
echo ""
echo "=========================================="
if [ $POST_ERRORS -eq 0 ]; then
    log_info "✅ VERIFICACIONES POST-EJECUCIÓN: TODAS PASARON"
    echo "=========================================="
    echo ""
    log_info "🎉 PROVISIONAMIENTO COMPLETADO EXITOSAMENTE"
    echo ""
    echo "Próximos pasos:"
    echo "1. Clona el repositorio en /opt/luisa"
    echo "2. Ejecuta: sudo ./deploy.sh"
    echo ""
    echo "Verificaciones manuales recomendadas:"
    echo "  - SSH desde otra terminal: ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112"
    echo "  - Docker: docker --version && docker info"
    echo "  - UFW: sudo ufw status verbose"
    echo ""
    exit 0
else
    log_error "❌ VERIFICACIONES POST-EJECUCIÓN: $POST_ERRORS ERROR(ES) DETECTADO(S)"
    echo "=========================================="
    echo ""
    log_error "🚨 PROVISIONAMIENTO COMPLETADO CON ERRORES"
    log_error "Revisa los errores arriba y corrige manualmente antes de continuar."
    echo ""
    exit 1
fi

