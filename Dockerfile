# Dockerfile para LUISA Backend
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
    && rm -rf /var/lib/apt/lists/*

# Cambiar a usuario luisa
USER luisa
WORKDIR /app

# Copiar requirements primero (para cache de layers)
COPY --chown=luisa:luisa backend/requirements.txt /app/requirements.txt

# Instalar dependencias Python
RUN pip install --user --no-cache-dir -r requirements.txt

# Agregar ~/.local/bin al PATH para pip install --user
ENV PATH="/home/luisa/.local/bin:${PATH}"

# Copiar código de la aplicación
COPY --chown=luisa:luisa backend/ /app/
COPY --chown=luisa:luisa .env.example /app/.env.example

# Crear directorio de datos si no existe
RUN mkdir -p /app/data /app/assets/cache

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Comando por defecto
CMD ["python", "main.py"]

