#!/bin/bash

# Go/No-Go checks antes de restart (P1-2)
echo "🔍 Ejecutando Go/No-Go checks..."
cd "$(dirname "$0")"
python3 backend/scripts/go_no_go.py --hard-fail
if [ $? -ne 0 ]; then
  echo "❌ go_no_go falló. Restart cancelado."
  exit 1
fi
echo "✅ Go/No-Go checks pasaron. Continuando con restart..."
echo ""
# Script para reiniciar contenedores en producción
# Uso: ./restart_produccion.sh

set -euo pipefail

SERVER_USER="ubuntu"
SERVER_IP="44.215.107.112"
SERVER_KEY="~/.ssh/luisa-lightsail.pem"
SERVER_DIR="/opt/luisa"

echo "🔄 Reiniciando contenedores en producción..."
echo ""

# Conectarse y reiniciar
ssh -i $SERVER_KEY $SERVER_USER@$SERVER_IP << 'REMOTE_EOF'
    cd /opt/luisa
    
    echo "📥 Actualizando código desde GitHub..."
    git pull origin main || echo "⚠️  Error en git pull, continuando..."
    
    echo "🔄 Reiniciando contenedores..."
    sudo docker compose restart backend caddy
    
    echo ""
    echo "✅ Reinicio completado"
    echo ""
    echo "📊 Estado de contenedores:"
    sudo docker compose ps
    
    echo ""
    echo "📋 Últimos logs del backend:"
    sudo docker compose logs backend --tail=20
REMOTE_EOF

echo ""
echo "✅ Reinicio completado"
echo ""
echo "🔍 Verificar health:"
echo "  curl https://luisa-agent.online/health"
