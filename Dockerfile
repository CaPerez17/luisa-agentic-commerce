# Dockerfile para LUISA Backend
# Optimizado para VPS pequeños (512MB-1GB RAM)
FROM python:3.11-slim

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 luisa && \
    mkdir -p /app /app/data && \
    chown -R luisa:luisa /app

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Cambiar a usuario luisa
USER luisa
WORKDIR /app

# Agregar ~/.local/bin al PATH para pip install --user
ENV PATH="/home/luisa/.local/bin:${PATH}"

# Copiar requirements primero (para cache de layers)
COPY --chown=luisa:luisa backend/requirements.txt /app/requirements.txt

# Instalar dependencias Python (sin cache para reducir tamaño)
RUN pip install --user --no-cache-dir -r requirements.txt

# Copiar código de la aplicación (sin assets grandes)
COPY --chown=luisa:luisa backend/*.py /app/
COPY --chown=luisa:luisa backend/app/ /app/app/

# Copiar assets del catálogo (solo metadata JSON, no imágenes grandes)
COPY --chown=luisa:luisa backend/assets/catalog_index.json /app/assets/catalog_index.json
COPY --chown=luisa:luisa backend/assets/catalog/*/*.json /app/assets/catalog/

# Copiar .env.example como referencia
COPY --chown=luisa:luisa .env.example /app/.env.example

# Crear directorios necesarios
RUN mkdir -p /app/data /app/assets/cache /app/assets/catalog

# Exponer puerto
EXPOSE 8000

# Health check simple usando curl (más ligero que python)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Comando por defecto
CMD ["python", "main.py"]
