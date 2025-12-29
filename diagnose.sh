#!/bin/bash
# Script de diagnóstico para LUISA en producción
# Uso: ./diagnose.sh

set -euo pipefail

APP_DIR="/opt/luisa"
DOMAIN="luisa-agent.online"

echo "=========================================="
echo "🔍 DIAGNÓSTICO DE LUISA"
echo "=========================================="
echo ""

# 1. Verificar conectividad SSH
echo "1️⃣ Verificando acceso SSH..."
if ssh -i ~/.ssh/luisa-lightsail.pem -o ConnectTimeout=5 ubuntu@44.215.107.112 "echo 'OK'" &>/dev/null; then
    echo "   ✅ SSH funciona"
else
    echo "   ❌ SSH no funciona"
fi
echo ""

# 2. Verificar Docker
echo "2️⃣ Verificando Docker..."
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 <<'EOF'
    echo "   Docker version:"
    docker --version || echo "   ❌ Docker no instalado"
    echo ""
    echo "   Docker Compose version:"
    docker compose version || echo "   ❌ Docker Compose no disponible"
    echo ""
    echo "   Estado de Docker:"
    systemctl status docker --no-pager -l | head -5 || echo "   ❌ Docker no está corriendo"
EOF
echo ""

# 3. Verificar contenedores
echo "3️⃣ Estado de contenedores:"
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 <<'EOF'
    cd /opt/luisa 2>/dev/null || echo "   ⚠️  Directorio /opt/luisa no existe"
    docker compose ps 2>/dev/null || echo "   ⚠️  No se puede ejecutar docker compose ps"
EOF
echo ""

# 4. Verificar logs
echo "4️⃣ Últimos logs del backend:"
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 <<'EOF'
    cd /opt/luisa 2>/dev/null && docker compose logs --tail=30 backend 2>/dev/null || echo "   ⚠️  No se pueden leer logs"
EOF
echo ""

echo "5️⃣ Últimos logs de Caddy:"
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 <<'EOF'
    cd /opt/luisa 2>/dev/null && docker compose logs --tail=30 caddy 2>/dev/null || echo "   ⚠️  No se pueden leer logs"
EOF
echo ""

# 5. Verificar health endpoints
echo "6️⃣ Health check local:"
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 <<'EOF'
    curl -sf http://localhost:8000/health && echo "   ✅ Backend responde" || echo "   ❌ Backend NO responde"
EOF
echo ""

echo "7️⃣ Health check público HTTPS:"
curl -sf https://$DOMAIN/health && echo "   ✅ HTTPS público funciona" || echo "   ❌ HTTPS público NO funciona"
echo ""

# 6. Verificar firewall
echo "8️⃣ Estado del firewall (UFW):"
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 "sudo ufw status" || echo "   ⚠️  No se puede verificar UFW"
echo ""

# 7. Verificar archivos críticos
echo "9️⃣ Verificando archivos críticos:"
ssh -i ~/.ssh/luisa-lightsail.pem ubuntu@44.215.107.112 <<'EOF'
    if [ -f /opt/luisa/.env ]; then
        echo "   ✅ .env existe"
        if [ -r /opt/luisa/.env ]; then
            echo "   ✅ .env es legible"
        else
            echo "   ⚠️  .env no es legible (verificar permisos)"
        fi
    else
        echo "   ❌ .env NO existe"
    fi
    
    if [ -f /opt/luisa/Caddyfile ]; then
        echo "   ✅ Caddyfile existe"
    else
        echo "   ❌ Caddyfile NO existe"
    fi
    
    if [ -f /opt/luisa/docker-compose.yml ]; then
        echo "   ✅ docker-compose.yml existe"
    else
        echo "   ❌ docker-compose.yml NO existe"
    fi
EOF
echo ""

# 8. Verificar certificado SSL
echo "🔟 Verificando certificado SSL:"
curl -vI https://$DOMAIN/health 2>&1 | grep -i "certificate\|SSL\|TLS" | head -5 || echo "   ⚠️  No se pudo verificar certificado"
echo ""

echo "=========================================="
echo "✅ Diagnóstico completado"
echo "=========================================="

