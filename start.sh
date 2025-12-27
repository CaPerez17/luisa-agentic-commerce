#!/bin/bash

echo "🚀 Iniciando Sistema Luisa..."
echo ""

# Crear directorio outbox si no existe
mkdir -p outbox

# Verificar si existe venv
if [ ! -d "backend/venv" ]; then
    echo "📦 Creando entorno virtual..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

echo "🔧 Iniciando backend..."
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

echo ""
echo "✅ Backend iniciado en http://localhost:8000"
echo "📱 Abre frontend/index.html en tu navegador"
echo ""
echo "Para detener el servidor, presiona Ctrl+C"
echo ""

wait $BACKEND_PID

