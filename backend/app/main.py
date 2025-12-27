"""
Módulo principal de la aplicación LUISA.
Crea la aplicación FastAPI y monta los routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import validate_config, WHATSAPP_ENABLED
from app.models.database import init_db
from app.routers import api, whatsapp
from app.logging_config import logger


def create_app() -> FastAPI:
    """
    Crea y configura la aplicación FastAPI.
    
    Returns:
        FastAPI app configurada
    """
    # Validar configuración
    warnings = validate_config()
    for warning in warnings:
        logger.warning(warning)
    
    # Crear app
    app = FastAPI(
        title="LUISA - Asistente El Sastre",
        description="API del asistente comercial para Almacén y Taller El Sastre",
        version="2.0.0"
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Inicializar base de datos
    init_db()
    
    # Montar routers
    app.include_router(api.router)
    
    if WHATSAPP_ENABLED:
        app.include_router(whatsapp.router)
        logger.info("WhatsApp webhook habilitado")
    
    # Health check
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "luisa",
            "version": "2.0.0",
            "whatsapp_enabled": WHATSAPP_ENABLED
        }
    
    logger.info("Aplicación LUISA iniciada", version="2.0.0")
    
    return app


# Para importar desde otros módulos
app = create_app()
