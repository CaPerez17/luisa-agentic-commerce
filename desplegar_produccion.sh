#!/bin/bash
# Script rápido para desplegar a producción
# Uso: ./desplegar_produccion.sh

set -euo pipefail

SERVER_USER="ubuntu"
SERVER_IP="44.215.107.112"
SERVER_KEY="~/.ssh/luisa-lightsail.pem"
SERVER_DIR="/opt/luisa"
LOCAL_DIR="/Users/camilope/AI-Agents/Sastre"

echo "🚀 Desplegando LUISA a producción..."
echo ""

# Verificar que .env existe localmente
if [ ! -f "$LOCAL_DIR/.env" ]; then
    echo "❌ Error: .env no existe en $LOCAL_DIR"
    echo "   Crea el archivo .env con todas las variables necesarias"
    exit 1
fi

echo "✅ .env encontrado localmente"
echo ""

# Copiar .env al servidor
echo "📤 Copiando .env al servidor..."
scp -i $SERVER_KEY "$LOCAL_DIR/.env" $SERVER_USER@$SERVER_IP:$SERVER_DIR/.env

# Conectarse y desplegar
echo "🔧 Conectándose al servidor y desplegando..."
ssh -i $SERVER_KEY $SERVER_USER@$SERVER_IP << 'EOF'
    cd /opt/luisa
    
    echo "📥 Actualizando código..."
    git pull origin main
    
    echo "🔨 Desplegando..."
    sudo ./deploy.sh
    
    echo ""
    echo "✅ Despliegue completado"
    echo ""
    echo "Verificando estado..."
    sudo docker compose ps
    
    echo ""
    echo "📊 Verificando variables..."
    sudo docker exec luisa-backend python3 -c "
from app.config import OPENAI_ENABLED, WHATSAPP_ENABLED, OPENAI_MAX_CALLS_PER_CONVERSATION
print(f'OPENAI_ENABLED={OPENAI_ENABLED}')
print(f'WHATSAPP_ENABLED={WHATSAPP_ENABLED}')
print(f'MAX_CALLS={OPENAI_MAX_CALLS_PER_CONVERSATION}')
" 2>/dev/null || echo "⚠️  No se pudo verificar variables (contenedor puede estar iniciando)"
EOF

echo ""
echo "✅ Despliegue completado"
echo ""
echo "🔍 Verificaciones:"
echo "  curl https://luisa-agent.online/health"
echo ""
echo "📊 Logs:"
echo "  ssh -i $SERVER_KEY $SERVER_USER@$SERVER_IP 'cd $SERVER_DIR && sudo docker compose logs -f backend'"
echo ""

