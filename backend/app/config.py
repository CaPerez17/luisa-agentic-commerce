"""
Configuración centralizada del sistema LUISA.
Todas las variables de entorno con defaults seguros.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env si existe
load_dotenv()

# ============================================================================
# PATHS
# ============================================================================
BASE_DIR = Path(__file__).parent.parent  # backend/
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_CATALOG_DIR = ASSETS_DIR / "catalog"
ASSETS_CACHE_DIR = ASSETS_DIR / "cache"
OUTBOX_DIR = BASE_DIR.parent / "outbox"

# Crear directorios si no existen
ASSETS_CACHE_DIR.mkdir(exist_ok=True, parents=True)
OUTBOX_DIR.mkdir(exist_ok=True)

# ============================================================================
# DATABASE
# ============================================================================
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "luisa.db"))

# ============================================================================
# API SECURITY
# ============================================================================
LUISA_API_KEY = os.getenv("LUISA_API_KEY", "demo-key-change-in-production")

# ============================================================================
# OPENAI CONFIGURATION
# ============================================================================
OPENAI_ENABLED = os.getenv("OPENAI_ENABLED", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Modelo económico y rápido
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "180"))
OPENAI_MAX_INPUT_CHARS = int(os.getenv("OPENAI_MAX_INPUT_CHARS", "1200"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.4"))
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "8"))
# Límites de uso por conversación
OPENAI_MAX_CALLS_PER_CONVERSATION = int(os.getenv("OPENAI_MAX_CALLS_PER_CONVERSATION", "4"))
OPENAI_CONVERSATION_TTL_HOURS = int(os.getenv("OPENAI_CONVERSATION_TTL_HOURS", "24"))  # Reset contador después de TTL
OPENAI_MAX_TOKENS_PER_CALL = int(os.getenv("OPENAI_MAX_TOKENS_PER_CALL", str(OPENAI_MAX_OUTPUT_TOKENS)))  # Límite por llamada
OPENAI_CACHEABLE_INTENTS = os.getenv(
    "OPENAI_CACHEABLE_INTENTS", 
    "horario,direccion,envios,pagos,catalogo"
).split(",")

# ============================================================================
# SALESBRAIN CONFIGURATION
# ============================================================================
SALESBRAIN_ENABLED = os.getenv("SALESBRAIN_ENABLED", "false").lower() == "true"
SALESBRAIN_PLANNER_ENABLED = os.getenv("SALESBRAIN_PLANNER_ENABLED", "true").lower() == "true"
SALESBRAIN_CLASSIFIER_ENABLED = os.getenv("SALESBRAIN_CLASSIFIER_ENABLED", "true").lower() == "true"
SALESBRAIN_MAX_CALLS_PER_CONVERSATION = int(os.getenv("SALESBRAIN_MAX_CALLS_PER_CONVERSATION", "4"))
SALESBRAIN_CACHE_TTL_SECONDS = int(os.getenv("SALESBRAIN_CACHE_TTL_SECONDS", "300"))

OPENAI_MODEL_CLASSIFIER = os.getenv("OPENAI_MODEL_CLASSIFIER", "gpt-4o-mini")
OPENAI_MODEL_PLANNER = os.getenv("OPENAI_MODEL_PLANNER", "gpt-4o-mini")

# ============================================================================
# WHATSAPP CLOUD API
# ============================================================================
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "luisa-verify-token-2024")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v18.0")

# Números para notificaciones internas (solo notificaciones, no conversaciones)
# LUISA humana recibe notificaciones comerciales
LUISA_HUMAN_NOTIFY_NUMBER = os.getenv("LUISA_HUMAN_NOTIFY_NUMBER", os.getenv("TEST_NOTIFY_NUMBER", "+573142156486"))
# Técnico recibe notificaciones técnicas
TECNICO_NOTIFY_NUMBER = os.getenv("TECNICO_NOTIFY_NUMBER", "")

# DEPRECATED: usar LUISA_HUMAN_NOTIFY_NUMBER
TEST_NOTIFY_NUMBER = LUISA_HUMAN_NOTIFY_NUMBER

# ============================================================================
# MODO SOMBRA (Shadow Mode)
# ============================================================================
# Tiempo en horas que LUISA permanece silenciada después de intervención humana
HUMAN_TTL_HOURS = int(os.getenv("HUMAN_TTL_HOURS", "12"))
# Tiempo en minutos que LUISA espera después de enviar notificación antes de silenciarse
HANDOFF_COOLDOWN_MINUTES = int(os.getenv("HANDOFF_COOLDOWN_MINUTES", "30"))

# ============================================================================
# CACHE IN-MEMORY
# ============================================================================
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "200"))
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "12"))

# ============================================================================
# LOGGING
# ============================================================================
PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" o "text"

# Forzar configuración segura en producción
if PRODUCTION_MODE:
    LOG_FORMAT = "json"
    # Evitar verbosidad en producción
    if LOG_LEVEL.upper() == "DEBUG":
        LOG_LEVEL = "INFO"

# ============================================================================
# BUSINESS CONFIGURATION
# ============================================================================
BUSINESS_NAME = "Almacén y Taller El Sastre"
BUSINESS_LOCATION = "Calle 34 #1-30, Montería, Córdoba, Colombia"
BUSINESS_HOURS = "Lunes a viernes 9am-6pm, sábados 9am-2pm"
BUSINESS_PHONE = "+573142156486"

# ============================================================================
# N8N INTEGRATION (opcional, para webhooks externos)
# ============================================================================
N8N_HANDOFF_WEBHOOK_URL = os.getenv("N8N_HANDOFF_WEBHOOK_URL", "")

# ============================================================================
# GOOGLE DRIVE (modo producción, no implementado aún)
# ============================================================================
ASSET_PROVIDER = os.getenv("ASSET_PROVIDER", "local")  # "local" | "drive"
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "")


def validate_config():
    """Valida configuración crítica al inicio."""
    warnings = []
    
    if OPENAI_ENABLED and not OPENAI_API_KEY:
        warnings.append("OPENAI_ENABLED=true pero OPENAI_API_KEY está vacío")
    
    if WHATSAPP_ENABLED:
        if not WHATSAPP_ACCESS_TOKEN:
            warnings.append("WHATSAPP_ENABLED=true pero WHATSAPP_ACCESS_TOKEN está vacío")
        if not WHATSAPP_PHONE_NUMBER_ID:
            warnings.append("WHATSAPP_ENABLED=true pero WHATSAPP_PHONE_NUMBER_ID está vacío")
    
    return warnings
