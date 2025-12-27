from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import sqlite3
import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Importar subagente de análisis de intención
try:
    from intent_analyzer import intent_analyzer, IntentType
except ImportError:
    # Fallback si no se puede importar
    intent_analyzer = None
    IntentType = None
import hashlib

# Cargar variables de entorno
load_dotenv()

# ============================================================================
# INTEGRACIÓN CON NUEVA ESTRUCTURA MODULAR
# ============================================================================
# Intentar importar la nueva app modular para funcionalidades adicionales
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from app.config import (
        WHATSAPP_ENABLED,
        OPENAI_ENABLED,
        TEST_NOTIFY_NUMBER,
        CACHE_ENABLED,
        PRODUCTION_MODE
    )
    from app.models.database import init_db as init_new_db
    from app.services.trace_service import create_tracer
    from app.services.cache_service import get_cached_response, cache_response
    from app.rules.business_guardrails import is_business_related, is_cacheable_query
    from app.services.handoff_service import process_handoff, should_handoff as new_should_handoff
    from app.routers.whatsapp import router as whatsapp_router
    from app.logging_config import logger as structured_logger
    from app.services.rate_limit import allow as rl_allow, remaining as rl_remaining
    
    NEW_MODULES_AVAILABLE = True
    print("✅ Módulos nuevos cargados correctamente")
except ImportError as e:
    NEW_MODULES_AVAILABLE = False
    WHATSAPP_ENABLED = False
    OPENAI_ENABLED = False
    CACHE_ENABLED = False
    print(f"⚠️ Módulos nuevos no disponibles: {e}")
    print("   Continuando con funcionalidad legacy...")

app = FastAPI(
    title="LUISA - Asistente El Sastre",
    description="API del asistente comercial para Almacén y Taller El Sastre",
    version="2.0.0"
)

# CORS para permitir frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración
DB_PATH = "luisa.db"
OUTBOX_DIR = Path("../outbox")
OUTBOX_DIR.mkdir(exist_ok=True)
# Rutas de assets - buscar desde backend/
ASSETS_DIR = Path("assets")
if not ASSETS_DIR.exists():
    ASSETS_DIR = Path("../assets")
ASSETS_CATALOG_DIR = ASSETS_DIR / "catalog"
ASSETS_CACHE_DIR = ASSETS_DIR / "cache"
ASSETS_CACHE_DIR.mkdir(exist_ok=True, parents=True)
ASSETS_METADATA_DIR = ASSETS_DIR / "metadata"
ASSETS_IMAGES_DIR = ASSETS_DIR / "images"

# Configuración de assets
ASSET_PROVIDER = os.getenv("ASSET_PROVIDER", "local")  # local | drive
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "")
LUISA_API_KEY = os.getenv("LUISA_API_KEY", "demo-key-change-in-production")
N8N_HANDOFF_WEBHOOK_URL = os.getenv("N8N_HANDOFF_WEBHOOK_URL", "")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

# Modelos
class Message(BaseModel):
    conversation_id: str
    text: str
    sender: str  # "customer" o "luisa"

class Conversation(BaseModel):
    conversation_id: str
    customer_name: Optional[str] = None
    status: str = "active"  # active, escalated, closed

class HandoffPayload(BaseModel):
    conversation_id: str
    reason: str
    priority: str  # low, medium, high, urgent
    summary: str
    suggested_response: str
    customer_name: Optional[str] = None
    timestamp: str

# Inicializar DB
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            customer_name TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            text TEXT,
            sender TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            reason TEXT,
            priority TEXT,
            summary TEXT,
            suggested_response TEXT,
            customer_name TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalog_items (
            image_id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            brand TEXT,
            model TEXT,
            represents TEXT,
            conversation_role TEXT,
            priority INTEGER,
            send_when_customer_says TEXT,
            meta_json TEXT,
            drive_file_id TEXT,
            drive_mime_type TEXT,
            asset_provider TEXT DEFAULT 'local',
            file_name TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_metadata (
            cache_key TEXT PRIMARY KEY,
            file_path TEXT,
            drive_file_id TEXT,
            mime_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# Inicializar tablas nuevas si los módulos están disponibles
if NEW_MODULES_AVAILABLE:
    try:
        init_new_db()
        print("✅ Tablas adicionales inicializadas (trazas, notificaciones, modo sombra)")
    except Exception as e:
        print(f"⚠️ Error inicializando tablas nuevas: {e}")

# Montar router de WhatsApp si está habilitado
if NEW_MODULES_AVAILABLE and WHATSAPP_ENABLED:
    app.include_router(whatsapp_router)
    print("✅ WhatsApp webhook habilitado en /whatsapp/webhook")

# ============================================================================
# SISTEMA DE CATÁLOGO DE IMÁGENES
# ============================================================================

def load_catalog_from_filesystem() -> Dict[str, dict]:
    """Carga catálogo desde archivos locales (modo demo)"""
    catalog = {}
    if not ASSETS_CATALOG_DIR.exists():
        return catalog
    
    # Cargar desde catalog_index.json (buscar en backend/assets/)
    index_path = Path("assets") / "catalog_index.json"
    if not index_path.exists():
        index_path = ASSETS_DIR / "catalog_index.json"
    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
                for item in index_data.get("images", []):
                    image_id = item["image_id"]
                    # El path en el índice es relativo a catalog/
                    path_str = item.get("path", "").replace("catalog/", "")
                    catalog_path = ASSETS_CATALOG_DIR / path_str if path_str else None
                    
                    if catalog_path and catalog_path.exists():
                        meta_path = catalog_path / "meta.json"
                        if meta_path.exists():
                            with open(meta_path, "r", encoding="utf-8") as mf:
                                meta = json.load(mf)
                                catalog[image_id] = {
                                    **meta,
                                    "asset_provider": "local",
                                    "local_path": str(catalog_path)
                                }
        except Exception as e:
            print(f"Error cargando catálogo desde filesystem: {e}")
    
    # También buscar directamente en carpetas I*_* si no hay índice
    if not catalog:
        for catalog_folder in ASSETS_CATALOG_DIR.iterdir():
            if catalog_folder.is_dir() and catalog_folder.name.startswith("I"):
                meta_path = catalog_folder / "meta.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as mf:
                            meta = json.load(mf)
                            image_id = meta.get("image_id")
                            if image_id:
                                catalog[image_id] = {
                                    **meta,
                                    "asset_provider": "local",
                                    "local_path": str(catalog_folder)
                                }
                    except Exception as e:
                        print(f"Error cargando {meta_path}: {e}")
    
    return catalog

def load_catalog_from_db() -> Dict[str, dict]:
    """Carga catálogo desde base de datos"""
    catalog = {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT image_id, title, category, brand, model, represents,
               conversation_role, priority, send_when_customer_says,
               meta_json, drive_file_id, drive_mime_type, asset_provider, file_name
        FROM catalog_items
    """)
    
    for row in cursor.fetchall():
        meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
        catalog[row["image_id"]] = {
            "image_id": row["image_id"],
            "title": row["title"],
            "category": row["category"],
            "brand": row["brand"],
            "model": row["model"],
            "represents": row["represents"],
            "conversation_role": row["conversation_role"],
            "priority": row["priority"],
            "send_when_customer_says": json.loads(row["send_when_customer_says"]) if row["send_when_customer_says"] else [],
            **meta,
            "drive_file_id": row["drive_file_id"],
            "drive_mime_type": row["drive_mime_type"],
            "asset_provider": row["asset_provider"] or "local",
            "file_name": row["file_name"]
        }
    
    conn.close()
    return catalog

def get_catalog_item(image_id: str) -> Optional[dict]:
    """Obtiene un item del catálogo por image_id"""
    # Primero intentar desde DB (tiene prioridad si existe)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT image_id, title, category, brand, model, represents,
               conversation_role, priority, send_when_customer_says,
               meta_json, drive_file_id, drive_mime_type, asset_provider, file_name
        FROM catalog_items
        WHERE image_id = ?
    """, (image_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
        return {
            "image_id": row["image_id"],
            "title": row["title"],
            "category": row["category"],
            "brand": row["brand"],
            "model": row["model"],
            "represents": row["represents"],
            "conversation_role": row["conversation_role"],
            "priority": row["priority"],
            "send_when_customer_says": json.loads(row["send_when_customer_says"]) if row["send_when_customer_says"] else [],
            **meta,
            "drive_file_id": row["drive_file_id"],
            "drive_mime_type": row["drive_mime_type"],
            "asset_provider": row["asset_provider"] or "local",
            "file_name": row["file_name"]
        }
    
    # Si no está en DB, buscar en filesystem
    catalog = load_catalog_from_filesystem()
    return catalog.get(image_id)

def find_local_asset_file(image_id: str) -> Optional[Path]:
    """Encuentra el archivo de asset local (image_1.* o video_1.mp4)"""
    item = get_catalog_item(image_id)
    if not item:
        return None
    
    if item.get("asset_provider") == "local" and item.get("local_path"):
        catalog_path = Path(item["local_path"])
    else:
        # Buscar en estructura estándar
        for catalog_folder in ASSETS_CATALOG_DIR.iterdir():
            if catalog_folder.is_dir() and catalog_folder.name.startswith(image_id + "_"):
                catalog_path = catalog_folder
                break
        else:
            return None
    
    # Buscar image_1.* o video_1.mp4
    for ext in ["png", "jpg", "jpeg", "webp"]:
        img_file = catalog_path / f"image_1.{ext}"
        if img_file.exists():
            return img_file
    
    video_file = catalog_path / "video_1.mp4"
    if video_file.exists():
        return video_file
    
    return None

def get_asset_mime_type(file_path: Path) -> str:
    """Determina el MIME type del archivo"""
    ext = file_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".mp4": "video/mp4"
    }
    return mime_types.get(ext, "application/octet-stream")

def download_from_drive(file_id: str) -> Optional[bytes]:
    """Descarga un archivo desde Google Drive"""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io
        
        if not GOOGLE_SERVICE_ACCOUNT_JSON_PATH:
            return None
        
        # Autenticar
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON_PATH,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        
        service = build('drive', 'v3', credentials=credentials)
        
        # Descargar archivo
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        return file_content.getvalue()
    except Exception as e:
        print(f"Error descargando desde Drive: {e}")
        return None

def get_cached_file(drive_file_id: str) -> Optional[Path]:
    """Obtiene archivo desde cache si existe y no ha expirado"""
    cache_key = hashlib.md5(drive_file_id.encode()).hexdigest()
    cache_file = ASSETS_CACHE_DIR / f"{cache_key}"
    
    if not cache_file.exists():
        return None
    
    # Verificar expiración
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT expires_at FROM cache_metadata WHERE cache_key = ?
    """, (cache_key,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0]:
        expires_at = datetime.fromisoformat(row[0])
        if datetime.now() > expires_at:
            # Cache expirado, eliminar
            cache_file.unlink()
            return None
    
    return cache_file if cache_file.exists() else None

def save_to_cache(drive_file_id: str, content: bytes, mime_type: str) -> Path:
    """Guarda archivo en cache"""
    cache_key = hashlib.md5(drive_file_id.encode()).hexdigest()
    cache_file = ASSETS_CACHE_DIR / f"{cache_key}"
    
    cache_file.write_bytes(content)
    
    expires_at = datetime.now() + timedelta(hours=CACHE_TTL_HOURS)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO cache_metadata 
        (cache_key, file_path, drive_file_id, mime_type, expires_at)
        VALUES (?, ?, ?, ?, ?)
    """, (cache_key, str(cache_file), drive_file_id, mime_type, expires_at.isoformat()))
    conn.commit()
    conn.close()
    
    return cache_file

# Cargar catálogo inicial desde filesystem (modo demo)
CATALOG = load_catalog_from_filesystem()

# Cargar índice del catálogo
def load_catalog_index() -> Dict[str, dict]:
    """Carga el índice del catálogo desde catalog_index.json"""
    index_path = ASSETS_DIR / "catalog_index.json"
    if not index_path.exists():
        return {}
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
            # Convertir lista de items a dict por image_id para acceso rápido
            items_dict = {}
            for item in index_data.get("items", []):
                items_dict[item["image_id"]] = item
            return items_dict
    except Exception as e:
        print(f"Error cargando catalog_index.json: {e}")
        return {}

CATALOG_INDEX = load_catalog_index()

# Sistema de Assets (legacy - mantener compatibilidad)
def load_assets() -> Dict[str, dict]:
    """Carga todos los assets desde metadata"""
    assets = {}
    if ASSETS_METADATA_DIR.exists():
        for json_file in ASSETS_METADATA_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    asset_data = json.load(f)
                    assets[asset_data["post_id"]] = asset_data
            except Exception as e:
                print(f"Error cargando asset {json_file}: {e}")
    return assets

def find_matching_asset(text: str, context: dict, assets: Dict[str, dict]) -> Optional[dict]:
    """Encuentra el asset más relevante según el texto y contexto"""
    text_lower = text.lower()
    best_match = None
    best_score = 0
    
    for asset_id, asset in assets.items():
        score = 0
        
        # Match por palabras clave en send_when_customer_says
        for keyword in asset.get("send_when_customer_says", []):
            if keyword.lower() in text_lower:
                score += 10
        
        # Match por marca
        if asset.get("brand", "").lower() in text_lower:
            score += 15
        
        # Match por modelo
        if asset.get("model", "").lower() in text_lower:
            score += 15
        
        # Match por use_cases con contexto
        for use_case in asset.get("use_cases", []):
            if use_case in text_lower or (context.get("uso") and use_case == context["uso"]):
                score += 8
        
        # Match por best_for con contexto
        if context.get("volumen") == "alto":
            if "produccion_constante" in asset.get("use_cases", []):
                score += 5
        if context.get("tipo_maquina") == "industrial":
            if "emprendimiento" in asset.get("use_cases", []):
                score += 5
        
        # Prioridad del asset
        score += asset.get("priority", 0) / 10
        
        if score > best_score:
            best_score = score
            best_match = asset
    
    return best_match if best_score > 5 else None

# ============================================================================
# REGLA EXACTA DE MATCHING (INTENCIÓN → ASSET)
# ============================================================================

def select_catalog_asset(intent: str, context: dict) -> tuple[Optional[dict], bool]:
    """
    Selecciona el asset del catálogo según intención y contexto.
    Retorna: (catalog_item, handoff_required)
    
    Paso 0: Detectar máquinas específicas por nombre/modelo
    Paso 1: Determinar categoría primaria
    Paso 2: Filtrar por categoría usando catalog_index.json
    Paso 3: Seleccionar 1 asset por priority DESC, image_id ASC
    """
    text_lower = intent.lower()
    handoff_required = False
    
    # Paso 0: Detectar máquinas específicas por nombre/modelo
    specific_machine_matches = {
        "I007": ["6705c", "6705", "singer heavy duty 6705"],
        "I006": ["singer heavy duty"],
        "I001": ["ssgemsy", "sg8802e", "8802", "mecatronica"],
        "I002": ["union un300", "un300"],
        "I003": ["kansew", "ks653"],
        "I004": ["singer s0105", "s0105", "fileteadora singer"],
        "I005": ["kingter", "fileteadora kingter"],
    }
    
    # Buscar coincidencia específica (priorizar modelos más específicos primero)
    for image_id, keywords in specific_machine_matches.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Si encontramos una coincidencia específica, retornar esa máquina
                full_item = get_catalog_item(image_id)
                if full_item:
                    return full_item, False
    
    # Paso 1: Determinar categoría primaria
    category = None
    
    # Mapeo de intención a categoría (usar contexto también)
    # Priorizar contexto si existe
    if context.get("tipo_maquina") == "industrial":
        category = "recta_industrial_mecatronica"
    elif context.get("tipo_maquina") == "familiar":
        # Determinar si es fileteadora o familiar normal
        if any(word in text_lower for word in ["fileteadora", "filetear", "orillos", "terminar prendas"]):
            category = "fileteadora_familiar"
        else:
            category = "familiar"
    elif any(word in text_lower for word in ["fileteadora", "filetear", "orillos", "terminar prendas"]):
        category = "fileteadora_familiar"
    elif any(word in text_lower for word in ["empezar", "hogar", "uso personal", "casa", "doméstico", "domestico", "familiar"]):
        category = "familiar"
    elif any(word in text_lower for word in ["taller", "producción", "produccion", "industrial", "emprendimiento", "negocio"]):
        category = "recta_industrial_mecatronica"
    
    # Detectar conflictos de categoría
    has_familiar_intent = any(word in text_lower for word in ["familiar", "casa", "hogar", "doméstico"])
    has_industrial_intent = any(word in text_lower for word in ["industrial", "taller", "producción constante"])
    
    if has_familiar_intent and has_industrial_intent:
        handoff_required = True
        return None, True
    
    # Si no se puede determinar categoría, no retornar asset
    if not category:
        return None, False
    
    # Paso 2: Filtrar catálogo por categoría usando catalog_index.json
    matching_items = []
    for image_id, item in CATALOG_INDEX.items():
        if item.get("category") == category:
            # En demo, no requerir que el archivo exista físicamente
            # Solo verificar que el item está en el índice
            matching_items.append(item)
    
    if not matching_items:
        return None, False
    
    # Paso 3: Ordenar por priority DESC, luego image_id ASC
    matching_items.sort(key=lambda x: (-x.get("priority", 0), x.get("image_id", "")))
    
    # Seleccionar solo 1 asset (el primero después de ordenar)
    selected_item = matching_items[0]
    
    # Obtener metadata completa del item seleccionado
    full_item = get_catalog_item(selected_item["image_id"])
    if not full_item:
        return None, False
    
    return full_item, handoff_required

def find_matching_catalog_item(text: str, context: dict) -> Optional[dict]:
    """Wrapper legacy - usa select_catalog_asset internamente"""
    catalog_item, _ = select_catalog_asset(text, context)
    return catalog_item

# Cargar assets al inicio
ASSETS = load_assets()

# Motor de decisión
def analyze_message(text: str, conversation_history: List[dict]) -> dict:
    """Analiza el mensaje usando el subagente de intención y determina si necesita escalamiento"""
    # Usar el subagente de intención
    intent_result = intent_analyzer.analyze(text, conversation_history)
    
    text_lower = text.lower()
    
    # Palabras clave para escalamiento urgente
    urgent_keywords = [
        "urgente", "ya", "inmediato", "ahora mismo", "emergencia",
        "roto", "no funciona", "mal estado", "defectuoso",
        "reclamo", "demanda", "abogado", "legal"
    ]
    
    # Palabras clave para escalamiento alto
    high_keywords = [
        "problema", "error", "no llegó", "perdido", "equivocado",
        "devolución", "reembolso", "cancelar", "cancelación",
        "insatisfecho", "mal servicio", "defectuoso", "rota", "no funciona",
        "reclamo", "queja", "mal estado"
    ]
    
    # Palabras clave para consultas técnicas complejas (necesitan escalamiento)
    technical_complex_keywords = [
        "presupuesto", "cuál me recomiendas", "qué máquina", "asesoría",
        "emprendimiento", "qué necesito", "recomendación", "comparar"
    ]
    
    # Palabras clave para verificación de stock
    stock_keywords = [
        "tienen", "hay", "disponible", "stock", "inventario",
        "cuántas", "cuántos", "existe"
    ]
    
    # Palabras clave para horarios
    schedule_keywords = [
        "horario", "hora", "cuándo", "día", "abierto", "cierran",
        "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"
    ]
    
    # Palabras clave para pago
    payment_keywords = [
        "pago", "pagado", "transferencia", "depósito", "confirmación",
        "recibí", "cobro", "factura", "comprobante"
    ]
    
    # Palabras clave para envío
    shipping_keywords = [
        "envío", "enviado", "llegó", "entrega", "dirección",
        "tracking", "seguimiento", "dónde está"
    ]
    
    # Detectar urgencia
    is_urgent = any(keyword in text_lower for keyword in urgent_keywords)
    is_high = any(keyword in text_lower for keyword in high_keywords)
    is_technical_complex = any(keyword in text_lower for keyword in technical_complex_keywords)
    
    # Detectar solicitud explícita de persona
    wants_person = any(phrase in text_lower for phrase in [
        "quiero hablar con", "hablar con alguien", "hablar con una persona",
        "hablar con el dueño", "hablar con el jefe", "necesito hablar con",
        "puedo hablar con", "con quién puedo hablar"
    ])
    
    # Detectar consultas de compra avanzada (necesitan asesoría personalizada)
    is_purchase_intent = any(phrase in text_lower for phrase in [
        "quiero comprar", "me interesa", "quiero una", "necesito comprar",
        "cuánto cuesta", "precio de"
    ])
    
    # Extraer contexto para detectar si está listo para cerrar
    context = extract_context_from_history(conversation_history)
    context_ready = is_ready_for_close(context)
    
    # Detectar si estamos en flujo de captura de lead o dando valor (NO escalar automáticamente)
    en_flujo_captura_lead = False
    en_flujo_dar_valor = False
    
    if conversation_history:
        luisa_msgs = [m for m in conversation_history if m.get("sender") == "luisa"]
        if luisa_msgs:
            ultimo_luisa = luisa_msgs[-1].get("text", "").lower()
            
            # Flujo de captura de datos para cita/llamada
            flujo_captura_phrases = [
                "qué día", "que día", "qué numero", "que numero", "número de celular",
                "qué hora", "que hora", "en la mañana", "en la tarde", "contactemos",
                "te esperamos", "te llamaremos", "un asesor te contactará",
                "a qué correo", "a que correo", "qué máquina", "que maquina"
            ]
            if any(phrase in ultimo_luisa for phrase in flujo_captura_phrases):
                en_flujo_captura_lead = True
            
            # Flujo de "dar valor" - acabamos de dar info de precio/disponibilidad
            flujo_valor_phrases = [
                "promoción navideña", "promocion navideña", "$1.230.000", "$1.300.000",
                "están disponibles", "tenemos disponible", "formas de pago",
                "cuotas desde", "tiempo de entrega", "días hábiles",
                "¿cuál te interesa", "cual te interesa", "¿cuál prefieres", "cual prefieres"
            ]
            if any(phrase in ultimo_luisa for phrase in flujo_valor_phrases):
                en_flujo_dar_valor = True
    
    # También detectar si el mensaje actual es una respuesta a info de valor
    respuestas_a_valor = ["esa", "la primera", "la segunda", "la barata", "la cara",
                          "me interesa", "esa me gusta", "cuéntame más", "cuentame mas"]
    if any(phrase in text_lower for phrase in respuestas_a_valor):
        en_flujo_dar_valor = True
    
    # Detectar preguntas de tiempo de entrega (NO escalar, dar info primero)
    entrega_pregunta = any(phrase in text_lower for phrase in [
        "cuándo llega", "cuando llega", "tiempo de entrega", "cuánto tarda",
        "cuanto tarda", "demora", "días de entrega", "dias de entrega"
    ])
    if entrega_pregunta:
        en_flujo_dar_valor = True
    
    # Detectar momento de cierre (ciudad mencionada = listo para cerrar)
    ciudades = ["montería", "bogotá", "bogota", "medellín", "medellin", "cali", "barranquilla", "cartagena"]
    is_ready_to_close = any(ciudad in text_lower for ciudad in ciudades) or any(word in text_lower for word in ["envío", "envio", "enviar", "llegar", "ciudad"])
    
    # Determinar si necesita escalamiento
    needs_escalation = False
    reason = ""
    priority = "low"
    
    # Si estamos en flujo de captura de lead o dando valor, NO escalar automáticamente
    # (ya estamos capturando datos o dando información útil)
    if en_flujo_captura_lead or en_flujo_dar_valor:
        needs_escalation = False
    elif is_urgent:
        needs_escalation = True
        priority = "urgent"
        reason = "Cliente requiere atención inmediata"
    elif is_high:
        needs_escalation = True
        priority = "high"
        reason = "Problema o consulta compleja detectada"
    elif is_ready_to_close or context_ready:
        # MOMENTO DE CIERRE - Cliente listo para compra (prioridad alta)
        # Pero solo escalar si NO estamos en flujo de captura
        needs_escalation = True
        priority = "high"
        if context.get("ciudad"):
            reason = f"Cliente listo para cerrar venta - Ciudad: {context['ciudad']}, necesita coordinación de entrega y pago"
        else:
            reason = "Cliente listo para cerrar venta - necesita coordinación de entrega y pago"
    elif wants_person:
        needs_escalation = True
        priority = "medium"
        reason = "Cliente solicita hablar con persona"
    elif is_technical_complex and is_purchase_intent:
        # Si pregunta por recomendación técnica Y tiene intención de compra, escalar
        needs_escalation = True
        priority = "medium"
        reason = "Cliente necesita asesoría técnica personalizada para compra"
    
    # Generar respuesta automática
    response = generate_response(text, conversation_history, needs_escalation, intent_result)
    
    return {
        "needs_escalation": needs_escalation,
        "reason": reason,
        "priority": priority,
        "response": response,
        "intent": intent_result["intent"].value if intent_result["intent"] != IntentType.INDEFINIDO else None,
        "intent_confidence": intent_result["confidence"]
    }

# ============================================================================
# REGLAS DE HANDOFF OBLIGATORIO
# ============================================================================

def should_handoff(text: str, context: dict) -> tuple[bool, str, str]:
    """
    Determina si debe hacer handoff obligatorio según reglas de negocio.
    Retorna: (debe_hacer_handoff, razon, prioridad)
    """
    text_lower = text.lower()
    
    # 🔴 Handoff por impacto de negocio
    business_impact_keywords = [
        "montar negocio", "montar un negocio", "montar mi negocio",
        "emprendimiento", "emprender", "mi emprendimiento",
        "taller", "mi taller", "abrir taller",
        "producción", "produccion", "producción constante", "produccion constante",
        "mejorar mi negocio", "mejorar negocio", "hacer crecer",
        "crecer", "aumentar producción", "aumentar produccion",
        "escalar", "expandir"
    ]
    if any(keyword in text_lower for keyword in business_impact_keywords):
        return True, "Cliente requiere asesoría humana especializada para proyecto de negocio", "high"
    
    # 🔴 Handoff por servicio diferencial
    service_keywords = [
        "instalación", "instalacion", "instalar", "instalen",
        "visita", "visitar", "van a", "van al",
        "asesoría", "asesoria", "asesorar", "asesoramiento",
        "capacitación", "capacitacion", "capacitar", "enseñar",
        "envío + instalación", "envio + instalacion", "envío e instalación",
        "ir al municipio", "ir al pueblo", "ir a la vereda",
        "dejan funcionando", "dejen funcionando"
    ]
    if any(keyword in text_lower for keyword in service_keywords):
        return True, "Cliente requiere servicio diferencial (instalación/asesoría/visita) - plus competitivo de El Sastre", "high"
    
    # 🔴 Handoff geográfico
    ciudades_monteria = ["montería", "monteria"]
    ciudades_otras = ["bogotá", "bogota", "medellín", "medellin", "cali", "barranquilla", 
                      "cartagena", "santa marta", "manizales", "pereira", "armenia",
                      "ibagué", "ibague", "villavicencio", "bucaramanga", "pasto",
                      "municipio", "pueblo", "vereda", "corregimiento"]
    
    # Si menciona ciudad que NO es Montería
    if any(ciudad in text_lower for ciudad in ciudades_otras):
        ciudad_men = next((c for c in ciudades_otras if c in text_lower), "otra ciudad")
        return True, f"Cliente requiere coordinación logística para envío/instalación fuera de Montería - {ciudad_men}", "high"
    
    # Si menciona municipio/pueblo/vereda explícitamente
    if any(word in text_lower for word in ["municipio", "pueblo", "vereda", "corregimiento"]):
        return True, "Cliente menciona ubicación fuera de Montería - requiere coordinación logística humana", "high"
    
    # 🔴 Handoff por decisión de compra
    purchase_decision_keywords = [
        "precio", "cuánto cuesta", "cuanto cuesta", "cuánto vale", "cuanto vale",
        "formas de pago", "cómo pagar", "como pagar", "método de pago",
        "addi", "sistecrédito", "sistecrédito", "sistecredito", "crédito", "credito",
        "disponibilidad", "tienen disponible", "hay disponible",
        "envío inmediato", "envio inmediato", "entrega inmediata",
        "cuándo llega", "cuando llega", "tiempo de entrega"
    ]
    if any(keyword in text_lower for keyword in purchase_decision_keywords):
        return True, "Cliente en etapa de decisión de compra - requiere cierre comercial humano", "high"
    
    # 🔴 Handoff por ambigüedad crítica
    # Detectar múltiples necesidades técnicas conflictivas
    needs_detected = []
    if any(word in text_lower for word in ["ropa", "prendas", "camisas", "pantalones"]):
        needs_detected.append("ropa")
    if any(word in text_lower for word in ["gorras", "gorra"]):
        needs_detected.append("gorras")
    if any(word in text_lower for word in ["calzado", "zapatos", "tenis"]):
        needs_detected.append("calzado")
    if any(word in text_lower for word in ["producción constante", "produccion constante", "taller", "producción continua"]):
        needs_detected.append("produccion_constante")
    
    # Si tiene múltiples necesidades técnicas diferentes Y producción constante
    if len(needs_detected) >= 2 and "produccion_constante" in needs_detected:
        return True, f"Cliente con múltiples necesidades técnicas ({', '.join(needs_detected)}) + producción constante - requiere asesoría personalizada para evitar mala recomendación", "high"
    
    return False, "", "low"

def extract_context_from_history(history: List[dict]) -> dict:
    """
    Extrae contexto de la conversación para reducir opciones progresivamente.
    Sistema mejorado de tracking conversacional.
    """
    context = {
        "tipo_maquina": None,  # familiar, industrial
        "uso": None,  # ropa, gorras, calzado, etc
        "volumen": None,  # pocas unidades, producción constante
        "presupuesto": None,
        "ciudad": None,
        "marca_interes": None,
        "modelo_interes": None,
        "ultimo_tema": None,  # promocion, especificaciones, fotos, maquina_mostrada, precio, etc
        "esperando_confirmacion": False,  # si Luisa está esperando confirmación del usuario
        "ultimo_asset_mostrado": None,  # ID del último asset mostrado
        "referencia_pendiente": None,  # "esa", "la primera", "la que dijiste", etc
        "etapa_funnel": "exploracion",  # exploracion, consideracion, decision, cierre
        "turnos_conversacion": 0,
        "productos_mencionados": [],  # Lista de productos mencionados en la conversación
        "preguntas_respondidas": []  # Qué información ya dimos (precio, especificaciones, etc)
    }
    
    # Analizar historial completo (últimos 12 mensajes para contexto reciente)
    recent_history = history[-12:] if len(history) > 12 else history
    context["turnos_conversacion"] = len(recent_history)
    full_text = " ".join([msg["text"].lower() for msg in recent_history])
    
    # Detectar tipo de máquina (priorizar mensajes más recientes - últimos 6)
    recent_text = " ".join([msg["text"].lower() for msg in recent_history[-6:]])
    if any(word in recent_text for word in ["industrial", "industriales", "taller de producción", "taller producción"]):
        context["tipo_maquina"] = "industrial"
    elif any(word in recent_text for word in ["familiar", "familiares", "casa", "hogar", "personal", "doméstico", "domestico"]):
        context["tipo_maquina"] = "familiar"
    # Si no está en reciente, buscar en historial completo
    if not context["tipo_maquina"]:
        if any(word in full_text for word in ["industrial", "industriales"]):
            context["tipo_maquina"] = "industrial"
        elif any(word in full_text for word in ["familiar", "casa", "hogar", "personal"]):
            context["tipo_maquina"] = "familiar"
    
    # Detectar uso específico (priorizar mensajes más recientes)
    usos_detectados = []
    if any(word in full_text for word in ["gorras", "gorra", "cachuchas"]):
        usos_detectados.append("gorras")
    if any(word in full_text for word in ["ropa", "prendas", "camisas", "pantalones", "vestidos", "blusas", "confección", "confeccion"]):
        usos_detectados.append("ropa")
    if any(word in full_text for word in ["calzado", "zapatos", "zapatillas", "tenis", "botas"]):
        usos_detectados.append("calzado")
    if any(word in full_text for word in ["accesorios", "bolsos", "carteras", "morrales", "mochilas"]):
        usos_detectados.append("accesorios")
    if any(word in full_text for word in ["cortinas", "mantelería", "manteleria", "lencería hogar", "lenceria hogar"]):
        usos_detectados.append("hogar")
    if any(word in full_text for word in ["uniformes", "dotación", "dotacion"]):
        usos_detectados.append("uniformes")
    
    if usos_detectados:
        context["uso"] = usos_detectados[-1]  # El más reciente
        if len(usos_detectados) > 1:
            context["usos_multiples"] = usos_detectados
    
    # Detectar volumen (más específico)
    if any(word in full_text for word in ["pocas", "poca", "poco", "pocos", "ocasional", "casual", "hobby", "arreglos", "remiendos"]):
        context["volumen"] = "bajo"
    elif any(word in full_text for word in ["constante", "muchas", "muchos", "taller", "producción constante", "produccion constante", 
                                            "producción continua", "produccion continua", "negocio", "emprendimiento", "continua",
                                            "diario", "todos los días", "clientes", "pedidos", "encargos"]):
        context["volumen"] = "alto"
    
    # Detectar tipo industrial implícito en contexto de producción
    if context["volumen"] == "alto" and not context["tipo_maquina"]:
        context["tipo_maquina"] = "industrial"
    
    # Detectar ciudad (más ciudades colombianas)
    ciudades_map = {
        "montería": "montería", "monteria": "montería",
        "bogotá": "bogotá", "bogota": "bogotá",
        "medellín": "medellín", "medellin": "medellín",
        "cali": "cali",
        "barranquilla": "barranquilla",
        "cartagena": "cartagena",
        "bucaramanga": "bucaramanga",
        "pereira": "pereira",
        "manizales": "manizales",
        "ibagué": "ibagué", "ibague": "ibagué",
        "cúcuta": "cúcuta", "cucuta": "cúcuta",
        "villavicencio": "villavicencio",
        "santa marta": "santa marta",
        "pasto": "pasto",
        "neiva": "neiva",
        "armenia": "armenia",
        "sincelejo": "sincelejo",
        "valledupar": "valledupar",
        "popayán": "popayán", "popayan": "popayán"
    }
    for ciudad_key, ciudad_val in ciudades_map.items():
        if ciudad_key in full_text:
            context["ciudad"] = ciudad_val
            break
    
    # Detectar marca y modelo (incluyendo promociones)
    marcas_modelos = {
        "ssgemsy": ("SSGEMSY", "SG8802E"),
        "sg8802e": ("SSGEMSY", "SG8802E"),
        "union": ("UNION", "UN300"),
        "un300": ("UNION", "UN300"),
        "un350": ("UNION", "UN350"),
        "kansew": ("KANSEW", "KS653"),
        "ks653": ("KANSEW", "KS653"),
        "ks-8800": ("KANSEW", "KS-8800"),
        "ks8800": ("KANSEW", "KS-8800"),
        "singer": ("SINGER", None),
        "s0105": ("SINGER", "S0105"),
        "heavy duty": ("SINGER", "Heavy Duty"),
        "kingter": ("KINGTER", "KT-D3"),
        "kt-d3": ("KINGTER", "KT-D3"),
        "ktd3": ("KINGTER", "KT-D3")
    }
    
    productos_encontrados = []
    for keyword, (marca, modelo) in marcas_modelos.items():
        if keyword in full_text:
            if not context["marca_interes"]:
                context["marca_interes"] = marca
                if modelo:
                    context["modelo_interes"] = modelo
            producto = f"{marca} {modelo}" if modelo else marca
            if producto not in productos_encontrados:
                productos_encontrados.append(producto)
    context["productos_mencionados"] = productos_encontrados
    
    # Detectar último tema de conversación (análisis más profundo de mensajes de Luisa)
    luisa_messages = [msg for msg in recent_history if msg.get("sender") == "luisa"]
    if luisa_messages:
        last_luisa_msg = luisa_messages[-1].get("text", "").lower()
        
        # Promociones - múltiples patrones
        promo_patterns = [
            "promoción", "promocion", "ofertas disponibles", "promociones navideñas",
            "promociones:", "en promoción", "en promocion", "oferta especial",
            "descuento", "precio especial", "te muestro las ofertas"
        ]
        if any(pattern in last_luisa_msg for pattern in promo_patterns):
            context["ultimo_tema"] = "promocion"
            context["esperando_confirmacion"] = True
        
        # Especificaciones/Características
        elif any(word in last_luisa_msg for word in ["especificaciones", "características", "caracteristicas", "tiene estas características"]):
            context["ultimo_tema"] = "especificaciones"
        
        # Fotos/Imágenes
        elif any(word in last_luisa_msg for word in ["imagen", "foto", "aquí tienes", "te muestro"]):
            context["ultimo_tema"] = "fotos"
            context["esperando_confirmacion"] = True
        
        # Pregunta de diagnóstico (esperando respuesta)
        elif "?" in last_luisa_msg:
            # Detectar tipo de pregunta
            if any(word in last_luisa_msg for word in ["familiar o industrial", "qué tipo", "que tipo"]):
                context["ultimo_tema"] = "diagnostico_tipo"
                context["esperando_confirmacion"] = True
            elif any(word in last_luisa_msg for word in ["qué vas a fabricar", "que vas a fabricar", "qué harás", "que haras"]):
                context["ultimo_tema"] = "diagnostico_uso"
                context["esperando_confirmacion"] = True
            elif any(word in last_luisa_msg for word in ["producción constante", "produccion constante", "pocas unidades"]):
                context["ultimo_tema"] = "diagnostico_volumen"
                context["esperando_confirmacion"] = True
            elif any(word in last_luisa_msg for word in ["ciudad", "dónde", "donde", "ubicación", "ubicacion"]):
                context["ultimo_tema"] = "diagnostico_ciudad"
                context["esperando_confirmacion"] = True
            elif any(word in last_luisa_msg for word in ["presupuesto", "1.2", "1.3", "1.5", "millón", "millon"]):
                context["ultimo_tema"] = "diagnostico_presupuesto"
                context["esperando_confirmacion"] = True
            elif any(word in last_luisa_msg for word in ["te llamemos", "agendar", "visita", "pasar por"]):
                context["ultimo_tema"] = "cierre_handoff"
                context["esperando_confirmacion"] = True
    
    # Detectar referencias a productos anteriores en el mensaje actual del cliente
    if recent_history:
        last_customer_msg = ""
        for msg in reversed(recent_history):
            if msg.get("sender") == "customer":
                last_customer_msg = msg.get("text", "").lower()
                break
        
        if any(word in last_customer_msg for word in ["esa", "esa máquina", "esa maquina", "la que dijiste", "la que mencionaste"]):
            context["referencia_pendiente"] = "ultima_mencionada"
        elif any(word in last_customer_msg for word in ["la primera", "primera opción", "primera opcion"]):
            context["referencia_pendiente"] = "primera"
        elif any(word in last_customer_msg for word in ["la segunda", "segunda opción", "segunda opcion"]):
            context["referencia_pendiente"] = "segunda"
        elif any(word in last_customer_msg for word in ["la más barata", "la mas barata", "la económica", "la economica"]):
            context["referencia_pendiente"] = "mas_economica"
        elif any(word in last_customer_msg for word in ["la mejor", "la más cara", "la mas cara", "la premium"]):
            context["referencia_pendiente"] = "mejor"
    
    # Detectar presupuesto mencionado
    if any(word in full_text for word in ["1.2", "1.3", "1.4", "1.5", "millón", "millones", "presupuesto", "1200", "1300", "1400", "1500"]):
        context["presupuesto"] = True
    
    # Detectar qué información ya se dio
    preguntas_respondidas = []
    for msg in luisa_messages:
        msg_text = msg.get("text", "").lower()
        if "$" in msg_text or "precio" in msg_text or ".000" in msg_text:
            preguntas_respondidas.append("precio")
        if "características" in msg_text or "especificaciones" in msg_text:
            preguntas_respondidas.append("especificaciones")
        if "aquí" in msg_text and ("imagen" in msg_text or "foto" in msg_text):
            preguntas_respondidas.append("imagen")
        if "envío" in msg_text or "envio" in msg_text:
            preguntas_respondidas.append("envio")
    context["preguntas_respondidas"] = list(set(preguntas_respondidas))
    
    # Determinar etapa del funnel de ventas
    if context["ciudad"] or ("precio" in preguntas_respondidas and context["marca_interes"]):
        context["etapa_funnel"] = "cierre"
    elif context["marca_interes"] or context["modelo_interes"] or "precio" in preguntas_respondidas:
        context["etapa_funnel"] = "decision"
    elif context["tipo_maquina"] and context["uso"]:
        context["etapa_funnel"] = "consideracion"
    else:
        context["etapa_funnel"] = "exploracion"
    
    return context

# ============================================================================
# REGLAS DE HANDOFF OBLIGATORIO
# ============================================================================

def should_handoff(text: str, context: dict) -> tuple[bool, str, str]:
    """
    Determina si debe hacer handoff obligatorio según reglas de negocio.
    Retorna: (debe_hacer_handoff, razon, prioridad)
    """
    text_lower = text.lower()
    
    # 🔴 Handoff por impacto de negocio
    business_impact_keywords = [
        "montar negocio", "montar un negocio", "montar mi negocio",
        "emprendimiento", "emprender", "mi emprendimiento",
        "taller", "mi taller", "abrir taller",
        "producción", "produccion", "producción constante", "produccion constante",
        "mejorar mi negocio", "mejorar negocio", "hacer crecer",
        "crecer", "aumentar producción", "aumentar produccion",
        "escalar", "expandir"
    ]
    if any(keyword in text_lower for keyword in business_impact_keywords):
        return True, "Cliente requiere asesoría humana especializada para proyecto de negocio", "high"
    
    # 🔴 Handoff por servicio diferencial
    service_keywords = [
        "instalación", "instalacion", "instalar", "instalen",
        "visita", "visitar", "van a", "van al",
        "asesoría", "asesoria", "asesorar", "asesoramiento",
        "capacitación", "capacitacion", "capacitar", "enseñar",
        "envío + instalación", "envio + instalacion", "envío e instalación",
        "ir al municipio", "ir al pueblo", "ir a la vereda",
        "dejan funcionando", "dejen funcionando"
    ]
    if any(keyword in text_lower for keyword in service_keywords):
        return True, "Cliente requiere servicio diferencial (instalación/asesoría/visita) - plus competitivo de El Sastre", "high"
    
    # 🔴 Handoff geográfico
    ciudades_monteria = ["montería", "monteria"]
    ciudades_otras = ["bogotá", "bogota", "medellín", "medellin", "cali", "barranquilla", 
                      "cartagena", "santa marta", "manizales", "pereira", "armenia",
                      "ibagué", "ibague", "villavicencio", "bucaramanga", "pasto",
                      "municipio", "pueblo", "vereda", "corregimiento"]
    
    # Si menciona ciudad que NO es Montería
    if any(ciudad in text_lower for ciudad in ciudades_otras):
        ciudad_men = next((c for c in ciudades_otras if c in text_lower), "otra ciudad")
        return True, f"Cliente requiere coordinación logística para envío/instalación fuera de Montería - {ciudad_men}", "high"
    
    # Si menciona municipio/pueblo/vereda explícitamente
    if any(word in text_lower for word in ["municipio", "pueblo", "vereda", "corregimiento"]):
        return True, "Cliente menciona ubicación fuera de Montería - requiere coordinación logística humana", "high"
    
    # 🔴 Handoff por decisión de compra
    purchase_decision_keywords = [
        "precio", "cuánto cuesta", "cuanto cuesta", "cuánto vale", "cuanto vale",
        "formas de pago", "cómo pagar", "como pagar", "método de pago",
        "addi", "sistecrédito", "sistecrédito", "sistecredito", "crédito", "credito",
        "disponibilidad", "tienen disponible", "hay disponible",
        "envío inmediato", "envio inmediato", "entrega inmediata",
        "cuándo llega", "cuando llega", "tiempo de entrega"
    ]
    if any(keyword in text_lower for keyword in purchase_decision_keywords):
        return True, "Cliente en etapa de decisión de compra - requiere cierre comercial humano", "high"
    
    # 🔴 Handoff por ambigüedad crítica
    # Detectar múltiples necesidades técnicas conflictivas
    needs_detected = []
    if any(word in text_lower for word in ["ropa", "prendas", "camisas", "pantalones"]):
        needs_detected.append("ropa")
    if any(word in text_lower for word in ["gorras", "gorra"]):
        needs_detected.append("gorras")
    if any(word in text_lower for word in ["calzado", "zapatos", "tenis"]):
        needs_detected.append("calzado")
    if any(word in text_lower for word in ["producción constante", "produccion constante", "taller", "producción continua"]):
        needs_detected.append("produccion_constante")
    
    # Si tiene múltiples necesidades técnicas diferentes Y producción constante
    if len(needs_detected) >= 2 and "produccion_constante" in needs_detected:
        return True, f"Cliente con múltiples necesidades técnicas ({', '.join(needs_detected)}) + producción constante - requiere asesoría personalizada para evitar mala recomendación", "high"
    
    return False, "", "low"

def is_ready_for_close(context: dict) -> bool:
    """Detecta si la conversación está lista para cerrar (handoff)"""
    # Listo para cerrar si tiene:
    # 1. Ciudad mencionada (momento de cierre definitivo)
    if context["ciudad"]:
        return True
    
    # 2. Tipo industrial + uso claro + volumen (no solo marca)
    if context["tipo_maquina"] == "industrial" and context["uso"] and context["volumen"]:
        return True
    
    # 3. Presupuesto + uso claro
    if context["presupuesto"] and context["uso"]:
        return True
    
    return False

def generate_response(text: str, history: List[dict], needs_escalation: bool, intent_result: Dict = None) -> str:
    """
    Genera respuesta directiva y orientada a ventas - Luisa lidera la conversación.
    Sistema mejorado con manejo de contexto conversacional y escenarios anticipados.
    """
    text_lower = text.lower().strip()
    context = extract_context_from_history(history)
    
    # ============================================================================
    # PRIORIDAD 1: Manejar contexto conversacional (confirmaciones/negaciones)
    # ============================================================================
    
    # Detectar si es respuesta corta (confirmación/negación)
    is_short_response = len(text_lower.split()) <= 3
    confirmacion_keywords = ["si", "sí", "ok", "dale", "claro", "perfecto", "bueno", "vale", 
                             "quiero ver", "muestrame", "muéstrame", "ver", "a ver", "enséñame",
                             "manda", "envía", "envia", "pásame", "pasame", "dime", "cuáles", "cuales"]
    negacion_keywords = ["no", "nop", "nel", "otro", "otra", "diferente", "no gracias", "paso"]
    
    is_confirmation = any(word in text_lower for word in confirmacion_keywords) and is_short_response
    is_negation = any(word in text_lower for word in negacion_keywords) and is_short_response
    
    # Manejar contexto según último tema de conversación
    if context.get("esperando_confirmacion"):
        ultimo_tema = context.get("ultimo_tema")
        
        # CASO: Confirmación sobre promociones
        if ultimo_tema == "promocion" and is_confirmation:
            return "Perfecto, aquí están nuestras promociones navideñas:"
        
        # CASO: Negación sobre promociones
        if ultimo_tema == "promocion" and is_negation:
            return "Entendido. ¿Buscas máquina familiar o industrial?"
        
        # CASO: Confirmación sobre tipo de máquina
        if ultimo_tema == "diagnostico_tipo":
            if any(word in text_lower for word in ["industrial", "industriales", "taller"]):
                return "Perfecto, industrial. ¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
            elif any(word in text_lower for word in ["familiar", "familiares", "casa", "hogar"]):
                return "Perfecto, familiar. ¿Es para arreglos ocasionales o proyectos de costura regulares?"
        
        # CASO: Confirmación sobre uso
        if ultimo_tema == "diagnostico_uso":
            if any(word in text_lower for word in ["ropa", "prendas"]):
                context["uso"] = "ropa"
                return "Para ropa necesitas una recta industrial que maneje telas variadas.\n\n¿Producción constante o pocas unidades?"
            elif any(word in text_lower for word in ["gorras", "gorra"]):
                context["uso"] = "gorras"
                return "Para gorras necesitas una recta industrial que maneje telas gruesas.\n\n¿Producción constante o pocas unidades?"
            elif any(word in text_lower for word in ["calzado", "zapatos"]):
                context["uso"] = "calzado"
                return "Para calzado necesitas una recta industrial reforzada.\n\n¿Producción constante o pocas unidades?"
            elif any(word in text_lower for word in ["accesorios", "bolsos"]):
                context["uso"] = "accesorios"
                return "Para accesorios necesitas una recta industrial versátil.\n\n¿Producción constante o pocas unidades?"
        
        # CASO: Confirmación sobre volumen
        if ultimo_tema == "diagnostico_volumen":
            if any(word in text_lower for word in ["constante", "muchas", "mucho", "taller", "negocio", "alta"]):
                return "Para producción constante te recomiendo una recta industrial mecatrónica, estable y de bajo consumo.\n\n¿En qué ciudad te encuentras?"
            elif any(word in text_lower for word in ["pocas", "poco", "ocasional", "baja"]):
                return "Para producción ocasional una recta industrial básica funciona bien.\n\n¿Tu presupuesto está entre 1.2 y 1.5 millones?"
        
        # CASO: Confirmación sobre handoff (llamada/visita)
        if ultimo_tema == "cierre_handoff":
            if is_confirmation or any(word in text_lower for word in ["llamada", "llamen", "llámame", "llamame", "llamar"]):
                return "Perfecto, para agendarte con uno de nuestros asesores.\n\n¿A qué número de celular podemos llamarte?"
            elif any(word in text_lower for word in ["visita", "visiten", "vayan", "ir", "pasar"]):
                return "Perfecto, podemos agendar una visita a tu ubicación.\n\n¿En qué ciudad o municipio te encuentras?"
            elif any(word in text_lower for word in ["cita", "almacén", "almacen", "tienda", "local"]):
                return "¡Genial! Te esperamos en nuestro almacén en Calle 34 #1-30, Montería.\n\nHorario: Lunes a viernes 9am-6pm, sábados 9am-2pm.\n\n¿Qué día te queda mejor para pasar?"
    
    # ============================================================================
    # PRIORIDAD 2: Flujo de captura de leads (llamada/visita/cita)
    # ============================================================================
    
    # Detectar solicitud directa de llamada (sin contexto previo)
    llamada_keywords = ["llamada", "llamen", "llámenme", "llamenme", "llámame", "llamame", 
                        "me llaman", "pueden llamarme", "quiero que me llamen"]
    if any(keyword in text_lower for keyword in llamada_keywords):
        return "Perfecto, para agendarte con uno de nuestros asesores.\n\n¿A qué número de celular podemos llamarte?"
    
    # Detectar número de teléfono (colombiano: 10 dígitos, empieza con 3)
    import re
    telefono_pattern = r'\b3\d{9}\b'  # Números colombianos: 3XXXXXXXXX
    telefono_match = re.search(telefono_pattern, text_lower.replace(" ", "").replace("-", ""))
    
    if telefono_match:
        numero = telefono_match.group()
        # Formatear número
        numero_formateado = f"{numero[:3]} {numero[3:6]} {numero[6:]}"
        return f"Perfecto, te llamaremos al {numero_formateado}.\n\n¿A qué hora te queda mejor que te contactemos? (mañana, tarde o noche)"
    
    # ========== DETECCIÓN DE DÍA Y TURNO PARA CITA (PRIORIDAD ALTA) ==========
    # Verificar si el contexto indica que estamos agendando cita
    ultimo_luisa_msg = ""
    if history:
        luisa_msgs = [m for m in history if m.get("sender") == "luisa"]
        if luisa_msgs:
            ultimo_luisa_msg = luisa_msgs[-1].get("text", "").lower()
    
    # Detectar si Luisa preguntó por día o turno
    pregunto_por_dia = any(phrase in ultimo_luisa_msg for phrase in ["qué día", "que día", "que dia", "día te queda", "dia te queda"])
    pregunto_por_turno = any(phrase in ultimo_luisa_msg for phrase in ["mañana (9am", "tarde (2pm", "mañana o tarde", "en la mañana", "en la tarde"])
    
    # Detectar confirmación de día para cita presencial
    dias_semana = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo"]
    dia_detectado = next((dia for dia in dias_semana if dia in text_lower), None)
    
    if dia_detectado and pregunto_por_dia:
        dia_formateado = dia_detectado.replace("miercoles", "miércoles").replace("sabado", "sábado").title()
        if dia_detectado in ["domingo"]:
            return f"Los domingos estamos cerrados. ¿Te queda mejor el sábado (9am-2pm) o entre semana (9am-6pm)?"
        return f"¡Perfecto! Te esperamos el {dia_formateado} en Calle 34 #1-30, Montería.\n\n¿Vienes en la mañana (9am-12pm) o en la tarde (2pm-6pm)?"
    
    # Detectar confirmación de turno (mañana/tarde) para cita presencial
    if pregunto_por_turno:
        if any(word in text_lower for word in ["mañana", "manana", "temprano"]):
            return "¡Excelente! Te esperamos en la mañana. Pregunta por cualquiera de nuestros asesores.\n\n¿Tienes alguna pregunta mientras tanto?"
        elif any(word in text_lower for word in ["tarde"]):
            return "¡Excelente! Te esperamos en la tarde. Pregunta por cualquiera de nuestros asesores.\n\n¿Tienes alguna pregunta mientras tanto?"
    
    # ========== FIN DETECCIÓN DÍA/TURNO ==========
    
    # Detectar horario preferido para LLAMADA (no cita)
    # Solo si el contexto indica que estamos pidiendo hora para llamada telefónica
    pregunto_hora_llamada = any(phrase in ultimo_luisa_msg for phrase in ["qué hora", "que hora", "contactemos", "llamarte"])
    
    if pregunto_hora_llamada:
        if any(word in text_lower for word in ["mañana", "manana", "temprano"]):
            return "¡Listo! Un asesor te contactará en la mañana.\n\nMientras tanto, ¿tienes alguna pregunta sobre las máquinas o el servicio de instalación?"
        elif any(word in text_lower for word in ["tarde", "medio día", "mediodia"]):
            return "¡Listo! Un asesor te contactará en la tarde.\n\nMientras tanto, ¿tienes alguna pregunta sobre las máquinas o el servicio de instalación?"
        elif any(word in text_lower for word in ["noche"]):
            return "¡Listo! Un asesor te contactará en la noche.\n\nMientras tanto, ¿tienes alguna pregunta sobre las máquinas o el servicio de instalación?"
    
    # Detectar solicitud de visita directa
    visita_keywords = ["visita", "visiten", "vayan a", "ir a mi", "vengan", "pueden ir"]
    if any(keyword in text_lower for keyword in visita_keywords):
        if context.get("ciudad"):
            return f"Perfecto, podemos ir a {context['ciudad'].title()}.\n\n¿Cuál es tu dirección o barrio para coordinar la visita?"
        else:
            return "Perfecto, podemos agendar una visita a tu ubicación.\n\n¿En qué ciudad o municipio te encuentras?"
    
    # Detectar solicitud de ir al almacén/tienda
    almacen_keywords = ["ir al almacén", "ir al almacen", "pasar al almacén", "pasar al almacen",
                        "ir a la tienda", "pasar a la tienda", "quiero ir", "puedo ir", 
                        "voy a ir", "paso por", "pasaré por", "pasare por"]
    if any(keyword in text_lower for keyword in almacen_keywords):
        return "¡Genial! Te esperamos en nuestro almacén en Calle 34 #1-30, Montería.\n\nHorario: Lunes a viernes 9am-6pm, sábados 9am-2pm.\n\n¿Qué día te queda mejor para pasar?"
    
    # ============================================================================
    # PRIORIDAD 3: Escenarios anticipados basados en el negocio El Sastre
    # ============================================================================
    
    # ESCENARIO: Comparación de productos
    comparacion_keywords = ["cuál es mejor", "cual es mejor", "diferencia", "diferencias", "comparar", 
                            "versus", "vs", "entre estas", "cuál me conviene", "cual me conviene",
                            "ventajas", "mejor entre", "la mejor opción", "la mejor opcion"]
    if any(keyword in text_lower for keyword in comparacion_keywords):
        # Si hay productos mencionados en el contexto
        if context.get("productos_mencionados") and len(context["productos_mencionados"]) >= 2:
            productos = context["productos_mencionados"][:2]
            return f"Entre la {productos[0]} y la {productos[1]}, la diferencia principal está en el precio y algunas funciones.\n\nLa KINGTER KT-D3 ($1.230.000) tiene panel digital básico. La KANSEW KS-8800 ($1.300.000) tiene más opciones de puntadas.\n\nPara producción constante, ambas son excelentes. ¿Cuál se ajusta mejor a tu presupuesto?"
        else:
            return "Tenemos dos opciones en promoción:\n\n• KINGTER KT-D3 a $1.230.000 - Panel digital, bajo consumo\n• KANSEW KS-8800 a $1.300.000 - Más opciones de puntadas\n\n¿Cuál te interesa más?"
    
    # ESCENARIO: Referencia a producto anterior ("esa", "la primera", etc.)
    referencia_keywords = ["esa", "esa máquina", "esa maquina", "la que dijiste", "la que mencionaste",
                           "la primera", "la segunda", "la de la foto", "la de la imagen",
                           "la barata", "la más barata", "la más cara", "la mejor"]
    if any(keyword in text_lower for keyword in referencia_keywords):
        # Determinar qué producto referencia
        if "barata" in text_lower or "primera" in text_lower or "económica" in text_lower:
            return "La KINGTER KT-D3 está a $1.230.000 en promoción. Es recta industrial mecatrónica, ideal para producción constante.\n\n¿Qué vas a fabricar con ella?"
        elif "cara" in text_lower or "mejor" in text_lower or "segunda" in text_lower:
            return "La KANSEW KS-8800 está a $1.300.000 en promoción. Es recta industrial mecatrónica con más opciones de puntadas.\n\n¿Qué vas a fabricar con ella?"
        elif context.get("marca_interes"):
            marca = context["marca_interes"]
            return f"La {marca} es una excelente opción. ¿Quieres que te muestre las especificaciones o prefieres que coordinemos el envío?"
        else:
            return "¿Te refieres a la que te mostré? Cuéntame más sobre tu proyecto para confirmarte si es la indicada."
    
    # ESCENARIO: Consulta sobre garantía
    garantia_keywords = ["garantía", "garantia", "garantizado", "si se daña", "si se dana", 
                         "cobertura", "respaldo", "soporte", "servicio técnico", "servicio tecnico",
                         "postventa", "post venta", "si tiene problemas"]
    if any(keyword in text_lower for keyword in garantia_keywords):
        return "Todas nuestras máquinas tienen garantía y servicio técnico local.\n\nNuestro taller está en Montería y podemos ir a donde estés para reparaciones. No es solo la máquina, es el acompañamiento.\n\n¿Qué máquina te interesa?"
    
    # ESCENARIO: Consulta sobre capacitación/cursos
    capacitacion_keywords = ["capacitación", "capacitacion", "enseñan", "ensenan", "curso", "cursos",
                             "aprendo", "aprender", "clases", "tutorial", "cómo usar", "como usar",
                             "instrucciones", "me enseñan", "me ensenan"]
    if any(keyword in text_lower for keyword in capacitacion_keywords):
        return "Sí, cuando entregamos la máquina hacemos capacitación en sitio. Te enseñamos a usarla y dejamos funcionando.\n\nEs parte del servicio diferencial de El Sastre: no solo vendemos máquinas, acompañamos tu proyecto.\n\n¿Qué tipo de máquina necesitas?"
    
    # ESCENARIO: Problema con máquina propia (reparación)
    reparacion_keywords = ["se dañó", "se dano", "no funciona", "no prende", "no cose", "está mala",
                           "esta mala", "tiene problemas", "se trabó", "se trabo", "hace ruido",
                           "no avanza la tela", "rompe el hilo", "salta puntadas", "desajustada"]
    if any(keyword in text_lower for keyword in reparacion_keywords):
        return "Tenemos taller de reparación con técnicos especializados. Reparamos todas las marcas.\n\n¿Tu máquina es familiar o industrial? ¿Qué marca es?"
    
    # ESCENARIO: Repuestos específicos
    repuestos_especificos = {
        "aguja": "Tenemos agujas para todo tipo de máquinas: familiares e industriales, para telas gruesas y delgadas.\n\n¿Qué tipo de máquina tienes?",
        "agujas": "Tenemos agujas para todo tipo de máquinas: familiares e industriales, para telas gruesas y delgadas.\n\n¿Qué tipo de máquina tienes?",
        "hilo": "Manejamos hilos de todas las calidades para costura industrial y familiar.\n\n¿Para qué tipo de costura los necesitas?",
        "hilos": "Manejamos hilos de todas las calidades para costura industrial y familiar.\n\n¿Para qué tipo de costura los necesitas?",
        "pedal": "Tenemos pedales de repuesto para varias marcas. ¿Qué marca y modelo es tu máquina?",
        "bobina": "Tenemos bobinas y canillas para todas las máquinas. ¿Qué marca y modelo es tu máquina?",
        "canilla": "Tenemos bobinas y canillas para todas las máquinas. ¿Qué marca y modelo es tu máquina?",
        "pie": "Tenemos pies prensatela de todo tipo: para cremalleras, ojales, dobladillos y más.\n\n¿Qué tipo de pie necesitas?",
        "prensatela": "Tenemos pies prensatela de todo tipo: para cremalleras, ojales, dobladillos y más.\n\n¿Qué tipo de pie necesitas?"
    }
    for keyword, respuesta in repuestos_especificos.items():
        if keyword in text_lower:
            return respuesta
    
    # ============================================================================
    # ESCENARIOS DE "DAR VALOR ANTES DE ESCALAR" - Mantener lead caliente
    # ============================================================================
    
    # ESCENARIO: Precio - Dar rangos/promociones antes de escalar
    precio_keywords = ["precio", "cuánto cuesta", "cuanto cuesta", "cuánto vale", "cuanto vale",
                       "qué precio", "que precio", "a cómo", "a como", "qué valor", "que valor",
                       "cuánto es", "cuanto es", "sale a", "está a", "costo"]
    if any(keyword in text_lower for keyword in precio_keywords):
        # Si pregunta por máquina específica
        if any(word in text_lower for word in ["kingter", "kt-d3", "ktd3"]):
            return "La KINGTER KT-D3 está en promoción navideña a $1.230.000.\n\nIncluye: máquina completa, mesa industrial, motor ahorrador y capacitación en sitio.\n\n¿Es para producción de ropa, gorras o accesorios?"
        elif any(word in text_lower for word in ["kansew", "ks-8800", "ks8800"]):
            return "La KANSEW KS-8800 está en promoción navideña a $1.300.000.\n\nIncluye: máquina completa, mesa industrial, motor ahorrador y capacitación en sitio.\n\n¿Es para producción de ropa, gorras o accesorios?"
        elif any(word in text_lower for word in ["6705", "6705c"]):
            return "La Singer Heavy Duty 6705C es nuestra máquina familiar más completa.\n\nIncluye: 200 puntadas, pantalla LCD, 7 ojales automáticos y estructura metálica.\n\n¿La necesitas para uso personal o para un emprendimiento?"
        elif any(word in text_lower for word in ["singer", "heavy duty"]):
            return "Tenemos varias Singer Heavy Duty:\n\n• Heavy Duty 6705C - La más completa, con 200 puntadas y pantalla LCD\n• Heavy Duty básica - Para uso doméstico intensivo\n\n¿Cuál te interesa?"
        elif context.get("tipo_maquina") == "industrial" or any(word in text_lower for word in ["industrial", "industriales"]):
            return "Las máquinas industriales en promoción van desde $1.230.000 hasta $1.500.000.\n\nTenemos:\n• KINGTER KT-D3: $1.230.000\n• KANSEW KS-8800: $1.300.000\n\nAmbas incluyen mesa, motor ahorrador e instalación. ¿Cuál te interesa más?"
        elif context.get("tipo_maquina") == "familiar" or any(word in text_lower for word in ["familiar", "familiares", "casa"]):
            return "Las máquinas familiares van desde $400.000 hasta $900.000 dependiendo de las funciones.\n\n¿La necesitas para arreglos básicos o para proyectos de costura más elaborados?"
        else:
            # Pregunta genérica de precio - calificar primero
            return "Los precios varían según el tipo de máquina:\n\n• Familiares: desde $400.000\n• Industriales: desde $1.230.000 (con mesa e instalación incluida)\n\n¿Buscas máquina para casa o para producción/negocio?"
    
    # ESCENARIO: Disponibilidad/Stock - Confirmar antes de escalar
    disponibilidad_keywords = ["disponible", "disponibles", "tienen", "hay stock", "tienen stock",
                               "hay en", "tienen en", "existe", "manejan"]
    if any(keyword in text_lower for keyword in disponibilidad_keywords):
        if any(word in text_lower for word in ["6705", "6705c"]):
            return "¡Sí! Tenemos la Singer Heavy Duty 6705C disponible. Es una máquina semi-profesional con:\n\n• 200 puntadas incorporadas\n• Pantalla LCD\n• 1.100 puntadas por minuto\n• Estructura metálica reforzada\n\n¿La necesitas para uso personal intensivo o para un emprendimiento?"
        elif any(word in text_lower for word in ["kingter", "kt-d3"]):
            return "Sí, tenemos KINGTER KT-D3 disponible para entrega inmediata. Está en promoción a $1.230.000.\n\n¿A qué ciudad necesitas que te la enviemos?"
        elif any(word in text_lower for word in ["kansew", "ks-8800"]):
            return "Sí, tenemos KANSEW KS-8800 disponible para entrega inmediata. Está en promoción a $1.300.000.\n\n¿A qué ciudad necesitas que te la enviemos?"
        elif any(word in text_lower for word in ["singer", "heavy duty"]):
            return "Sí, tenemos Singer Heavy Duty disponibles:\n\n• Heavy Duty 6705C - Semi-profesional con 200 puntadas y pantalla LCD\n• Heavy Duty básica - Para uso doméstico intensivo\n\n¿Cuál te interesa?"
        elif any(word in text_lower for word in ["industrial", "industriales"]):
            return "Sí, tenemos máquinas industriales disponibles para entrega inmediata:\n\n• KINGTER KT-D3 - $1.230.000\n• KANSEW KS-8800 - $1.300.000\n\n¿Cuál te interesa?"
        elif any(word in text_lower for word in ["familiar", "familiares"]):
            return "Sí, tenemos máquinas familiares disponibles:\n\n• Singer Heavy Duty 6705C (semi-profesional)\n• UNION UN300\n• KANSEW KS653\n\n¿Cuál te interesa o te ayudo a elegir?"
        else:
            return "Sí, tenemos stock disponible. ¿Qué tipo de máquina buscas: familiar o industrial?"
    
    # ESCENARIO: Tiempo de entrega - Dar estimados antes de escalar
    entrega_keywords = ["cuándo llega", "cuando llega", "tiempo de entrega", "cuánto tarda",
                        "cuanto tarda", "demora", "días de entrega", "dias de entrega"]
    if any(keyword in text_lower for keyword in entrega_keywords):
        if context.get("ciudad"):
            ciudad = context["ciudad"].title()
            if ciudad.lower() in ["montería", "monteria"]:
                return f"En Montería la entrega es en 1-2 días hábiles. Incluye instalación y capacitación en sitio.\n\n¿Ya tienes definida la máquina que necesitas?"
            else:
                return f"Para {ciudad} el envío toma 3-5 días hábiles. Incluye instalación y capacitación cuando llegamos.\n\n¿Ya tienes definida la máquina que necesitas?"
        else:
            return "El tiempo de entrega depende de tu ubicación:\n\n• Montería: 1-2 días\n• Otras ciudades: 3-5 días\n• Municipios: 5-7 días\n\nTodas las entregas incluyen instalación. ¿A qué ciudad necesitas el envío?"
    
    # ESCENARIO: Formas de pago - Explicar opciones antes de escalar
    pago_keywords = ["cómo pago", "como pago", "formas de pago", "métodos de pago", "metodos de pago",
                     "puedo pagar", "aceptan", "reciben", "transferencia", "efectivo", "tarjeta"]
    if any(keyword in text_lower for keyword in pago_keywords):
        return "Aceptamos varias formas de pago:\n\n• Transferencia bancaria\n• Efectivo\n• Addi (cuotas sin tarjeta)\n• Sistecrédito (cuotas)\n• Tarjeta de crédito\n\n¿Cuál prefieres? Si quieres financiar, te puedo calcular las cuotas."
    
    # ESCENARIO: Financiación específica - Dar info completa
    financiacion_keywords = ["addi", "sistecrédito", "sistecredito", "cuotas", "financiación", 
                              "financiacion", "a plazos", "crédito", "credito"]
    if any(keyword in text_lower for keyword in financiacion_keywords):
        return "Trabajamos con Addi y Sistecrédito para facilitar tu compra:\n\n• Addi: Cuotas quincenales, aprobación en minutos\n• Sistecrédito: Cuotas mensuales, más plazo\n\nPor ejemplo, la KINGTER KT-D3 ($1.230.000) queda en cuotas desde $100.000/mes.\n\n¿Qué máquina te interesa para calcular las cuotas exactas?"
    
    # ESCENARIO: Cotización formal - Capturar datos antes de escalar
    cotizacion_keywords = ["cotización", "cotizacion", "cotizar", "cotizame", "proforma",
                           "presupuesto formal", "factura proforma"]
    if any(keyword in text_lower for keyword in cotizacion_keywords):
        return "Con gusto te preparo una cotización formal.\n\nPara enviártela necesito:\n1. ¿Qué máquina(s) te interesa(n)?\n2. ¿A qué correo te la envío?\n\nO si prefieres, te la podemos enviar por WhatsApp."
    
    # ESCENARIO: "Quiero comprar" - Calificar antes de escalar
    comprar_keywords = ["quiero comprar", "voy a comprar", "me interesa comprar", "quiero una",
                        "necesito comprar", "me la llevo", "la quiero"]
    if any(keyword in text_lower for keyword in comprar_keywords):
        if context.get("marca_interes"):
            marca = context["marca_interes"]
            return f"¡Excelente elección con la {marca}! Para coordinar la compra:\n\n¿Prefieres pago de contado o financiado? Y ¿a qué ciudad te la enviamos?"
        elif context.get("tipo_maquina"):
            return "¡Perfecto! Para coordinar tu compra:\n\n¿Ya tienes definida la máquina específica o te ayudo a elegir la mejor opción para tu proyecto?"
        else:
            return "¡Excelente! Para ayudarte con tu compra, primero cuéntame:\n\n¿Buscas máquina familiar (para casa) o industrial (para negocio/producción)?"
    
    # ESCENARIO: Preguntas de seguimiento después de ver precio
    # "Muy cara", "Muy costosa", "No me alcanza"
    objecion_precio_keywords = ["muy cara", "muy costosa", "no me alcanza", "no tengo", 
                                 "mucho dinero", "muy caro", "fuera de presupuesto"]
    if any(keyword in text_lower for keyword in objecion_precio_keywords):
        return "Entiendo. Tenemos opciones para diferentes presupuestos:\n\n• Financiación con Addi/Sistecrédito (cuotas desde $100.000/mes)\n• Máquinas familiares desde $400.000\n• Máquinas industriales usadas/reacondicionadas\n\n¿Cuál es tu presupuesto aproximado? Así te recomiendo la mejor opción."
    
    # ESCENARIO: "Lo voy a pensar" - Mantener enganchado
    pensar_keywords = ["lo voy a pensar", "voy a pensarlo", "déjame pensarlo", "dejame pensarlo",
                       "tengo que pensarlo", "me lo pienso", "luego te aviso", "después te confirmo"]
    if any(keyword in text_lower for keyword in pensar_keywords):
        return "¡Claro, tómate tu tiempo! Te recuerdo que la promoción navideña tiene cupos limitados.\n\nSi quieres, te puedo enviar la información por WhatsApp para que la revises con calma. ¿A qué número te la envío?"
    
    # ESCENARIO: "Estoy comparando" - Dar diferenciadores
    comparando_keywords = ["estoy comparando", "viendo opciones", "otras tiendas", "otro lado",
                           "más barato en", "mas barato en", "vi en otro", "encontré más barato"]
    if any(keyword in text_lower for keyword in comparando_keywords):
        return "¡Bien que compares! Nuestro diferencial es el servicio completo:\n\n✅ Instalación en tu ubicación (vamos hasta municipios)\n✅ Capacitación incluida\n✅ Servicio técnico local con garantía\n✅ Asesoría para emprendedores\n\nNo es solo la máquina, es el acompañamiento. ¿Qué máquina estás considerando?"
    
    # ESCENARIO: Preguntas vagas - Calificar mejor
    preguntas_vagas = ["información", "info", "más información", "detalles", "saber más",
                       "cuéntame", "cuentame", "explícame", "explicame"]
    if any(keyword in text_lower for keyword in preguntas_vagas) and len(text_lower.split()) <= 5:
        if context.get("marca_interes"):
            marca = context["marca_interes"]
            return f"Con gusto te cuento más sobre la {marca}. ¿Qué te interesa saber: especificaciones técnicas, precio, formas de pago o servicio de instalación?"
        else:
            return "Con gusto te ayudo. Para darte la información más útil:\n\n¿Qué tipo de máquina buscas: familiar (para casa) o industrial (para negocio)?"
    
    # ESCENARIO: Usuario envía correo electrónico - Capturar para cotización
    import re
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_match = re.search(email_pattern, text_lower)
    if email_match:
        email = email_match.group()
        return f"Perfecto, te enviaré la información a {email}.\n\n¿Qué máquina(s) incluyo en la cotización?"
    
    # ESCENARIO: Usuario confirma WhatsApp
    whatsapp_keywords = ["mi whatsapp", "por whatsapp", "al whatsapp", "número es", "numero es",
                         "este es mi número", "este es mi numero", "escríbeme al", "escribeme al"]
    if any(keyword in text_lower for keyword in whatsapp_keywords):
        return "¡Perfecto! Un asesor te escribirá al WhatsApp en breve.\n\nMientras tanto, ¿tienes alguna pregunta sobre las máquinas o el servicio?"
    
    # ESCENARIO: Horarios y ubicación
    ubicacion_keywords = ["horario", "horarios", "hora", "cuándo abren", "cuando abren", "dónde quedan",
                          "donde quedan", "ubicación", "ubicacion", "dirección", "direccion", "cómo llego",
                          "como llego", "están abiertos", "estan abiertos"]
    if any(keyword in text_lower for keyword in ubicacion_keywords):
        return "Estamos en Calle 34 #1-30, Montería, Córdoba.\n\nHorarios: Lunes a viernes 9am-6pm, sábados 9am-2pm.\n\n¿Quieres pasar por el almacén o prefieres que te enviemos a domicilio?"
    
    # ESCENARIO: Cliente emprendedor o con negocio existente
    # Detectar intención de negocio/emprendimiento (prioridad alta)
    negocio_keywords = ["mi negocio", "un negocio", "para negocio", "en mi negocio",
                        "montar un taller", "mi taller", "para mi taller",
                        "emprendimiento", "mi emprendimiento", "emprender",
                        "montar negocio", "abrir negocio", "iniciar negocio"]
    emprendedor_keywords = ["empezar un negocio", "iniciar un emprendimiento",
                            "quiero emprender", "no sé qué máquina", "no se que maquina", 
                            "cuál necesito", "cual necesito", "qué me sirve", "que me sirve",
                            "primera máquina", "primera maquina", "empezar desde cero",
                            "qué máquinas puedo usar", "que maquinas puedo usar",
                            "máquinas para mi negocio", "maquinas para mi negocio"]
    
    if any(keyword in text_lower for keyword in negocio_keywords + emprendedor_keywords):
        # Ofrecer servicio de acompañamiento (diferencial de El Sastre)
        return "¡Perfecto! Acompañamos a emprendedores y negocios desde cero.\n\nNo solo vendemos máquinas: te asesoramos según tu presupuesto, tipo de producción y ubicación. Instalamos y dejamos funcionando.\n\n¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
    
    # ESCENARIO: Consulta sobre envío a ciudades específicas
    envio_ciudades = ["envían a", "envian a", "hacen envío a", "hacen envio a", "llegan a", 
                      "mandan a", "despachan a"]
    if any(keyword in text_lower for keyword in envio_ciudades):
        return "Hacemos envíos a todo Colombia con instalación incluida.\n\nVamos hasta tu ciudad o municipio, instalamos y dejamos funcionando. Es nuestro diferencial.\n\n¿A qué ciudad necesitas el envío?"
    
    # Detectar pregunta sobre especificaciones/características (PRIORIDAD ALTA)
    specs_keywords = ["especificaciones", "especificacion", "características", "caracteristicas", "qué tiene", "que tiene", 
                      "incluye", "trae", "viene con", "detalles", "detalle técnico", "detalle tecnico", "info", "información", "informacion",
                      "datos técnicos", "datos tecnicos", "ficha técnica", "ficha tecnica", "specs", "especificacion tecnica"]
    if any(keyword in text_lower for keyword in specs_keywords):
        # Buscar máquina mencionada en el contexto o historial
        catalog_item = None
        
        # Intentar encontrar máquina mencionada
        if context.get("marca_interes") or context.get("modelo_interes"):
            # Buscar en catálogo por marca/modelo
            for image_id, item in CATALOG_INDEX.items():
                brand = item.get("brand", "").lower()
                model = item.get("model", "").lower()
                marca_buscada = context.get("marca_interes", "").lower()
                modelo_buscado = context.get("modelo_interes", "").lower()
                
                if marca_buscada and marca_buscada in brand:
                    catalog_item = get_catalog_item(image_id)
                    break
                elif modelo_buscado and modelo_buscado in model:
                    catalog_item = get_catalog_item(image_id)
                    break
        
        # Si no hay contexto, buscar en el historial reciente
        if not catalog_item:
            for msg in reversed(history[-5:]):
                msg_text = msg.get("text", "").lower()
                # Buscar menciones de marcas/modelos conocidos
                for image_id, item in CATALOG_INDEX.items():
                    brand = item.get("brand", "").lower()
                    model = item.get("model", "").lower()
                    if brand in msg_text or model in msg_text:
                        catalog_item = get_catalog_item(image_id)
                        break
                if catalog_item:
                    break
        
        # Si encontramos la máquina, dar especificaciones
        if catalog_item:
            brand = catalog_item.get("brand", "")
            model = catalog_item.get("model", "")
            key_features = catalog_item.get("key_features", [])
            
            if key_features:
                features_text = "\n".join([f"• {feat}" for feat in key_features[:5]])  # Máximo 5 características
                return f"La {brand} {model} tiene estas características principales:\n\n{features_text}\n\n¿Te interesa alguna en particular?"
            else:
                return f"La {brand} {model} es una máquina de calidad profesional. ¿Qué aspecto específico te interesa más?"
        else:
            # No se identificó máquina específica, pero hay imagen reciente
            if any(msg.get("asset") for msg in history[-3:]):
                return "Esa máquina tiene características técnicas profesionales. ¿Qué aspecto específico te interesa: motor, puntadas, consumo de energía?"
            else:
                return "Para darte las especificaciones exactas, ¿de qué máquina hablas? ¿Es industrial o familiar?"
    
    # Detectar pregunta sobre promociones (ANTES de otras detecciones)
    promo_keywords = ["promoción", "promocion", "promociones", "oferta", "descuento", "navidad", "navideña", "navidena"]
    if any(keyword in text_lower for keyword in promo_keywords):
        return "¡Sí! Tenemos promoción navideña especial. Te muestro las ofertas disponibles:"
    
    # Detectar solicitud explícita de fotos/imágenes
    foto_keywords = ["fotos", "foto", "imágenes", "imagenes", "imagen", "muéstrame", "muestrame", "ver", "quiero ver", "tienes fotos", "tiene fotos", "muestra", "fotografía", "fotografia"]
    if any(keyword in text_lower for keyword in foto_keywords):
        # Si hay contexto de máquina mencionada, mostrar esa
        if context.get("tipo_maquina") or context.get("uso") or any(word in text_lower for word in ["máquina", "maquina", "industrial", "familiar"]):
            # Retornar respuesta que incluirá asset (se maneja en el endpoint)
            return "Claro, aquí tienes una imagen de la máquina que te recomiendo:"
        else:
            return "Claro, puedo mostrarte imágenes. ¿Qué tipo de máquina te interesa: familiar o industrial?"
    
    # Saludos - directivos, reducen opciones inmediatamente
    # Solo si es mensaje corto (evitar falsos positivos)
    if len(text_lower.split()) <= 4 and any(word in text_lower for word in ["hola", "buenos días", "buenas tardes", "buenas noches"]):
        return "¡Hola! 👋 Soy Luisa. ¿Buscas máquina familiar o industrial?"
    
    # Despedidas - SOLO si es mensaje corto y NO contiene intención de compra/consulta
    despedida_keywords = ["chau", "adiós", "adios", "nos vemos", "hasta luego", "bye"]
    tiene_intencion_consulta = any(word in text_lower for word in [
        "máquina", "maquina", "negocio", "comprar", "precio", "necesito", "quiero", 
        "busco", "interesa", "usar", "sirve", "recomiendas", "promoción", "promocion"
    ])
    
    # "Gracias" solo es despedida si es mensaje corto Y no tiene otra intención
    if "gracias" in text_lower:
        if len(text_lower.split()) <= 3 and not tiene_intencion_consulta:
            return "¡De nada! Cualquier cosa, aquí estoy. ¡Que tengas un buen día! 😊"
        # Si tiene "gracias" pero también consulta, ignorar el gracias y procesar la consulta
    elif any(word in text_lower for word in despedida_keywords) and len(text_lower.split()) <= 4:
        return "¡De nada! Cualquier cosa, aquí estoy. ¡Que tengas un buen día! 😊"
    
    # MOMENTO DE CIERRE: Ciudad mencionada = listo para cerrar venta
    ciudades = ["montería", "bogotá", "bogota", "medellín", "medellin", "cali", "barranquilla", "cartagena"]
    if any(ciudad in text_lower for ciudad in ciudades) or any(word in text_lower for word in ["envío", "envio", "enviar", "llegar", "ciudad"]):
        ciudad_men = next((c for c in ciudades if c in text_lower), None)
        if ciudad_men:
            return f"Perfecto, hacemos envíos a {ciudad_men.title()}.\n\nDéjame conectarte con nuestro equipo para coordinar la entrega y el pago."
        else:
            return "Perfecto, hacemos envíos a todo el país.\n\nDéjame conectarte con nuestro equipo para coordinar la entrega y el pago."
    
    # CASO 1: Ropa - Flujo direccional completo
    if any(word in text_lower for word in ["ropa", "prendas", "camisas", "pantalones", "vestidos", "blusas"]):
        matching_asset = find_matching_asset(text, context, ASSETS)
        
        if context["tipo_maquina"] == "industrial" or "industrial" in text_lower:
            if not context["volumen"]:
                # Afirmación técnica + pregunta cerrada
                if matching_asset:
                    cta = matching_asset.get("cta", {})
                    return f"{cta.get('educational', 'Para ropa necesitas una recta industrial que maneje telas variadas y costura continua.')}\n\n¿Vas a producir pocas unidades al día o producción constante tipo taller?"
                return "Para ropa necesitas una recta industrial que maneje telas variadas y costura continua.\n\n¿Vas a producir pocas unidades al día o producción constante tipo taller?"
            elif context["volumen"] == "alto" or any(word in text_lower for word in ["constante", "muchas", "taller", "producción", "produccion"]):
                # MOMENTO DE CIERRE - ya tiene todo
                if matching_asset:
                    cta = matching_asset.get("cta", {})
                    brand_model = f"{matching_asset.get('brand', '')} {matching_asset.get('model', '')}".strip()
                    benefits = matching_asset.get("benefits", [])
                    benefit_text = ""
                    if "ahorro_energia_70" in benefits:
                        benefit_text = " con ahorro de energía del 70%"
                    return f"Para producción constante de ropa te recomiendo la {brand_model}, recta industrial mecatrónica estable{benefit_text}.\n\n¿En qué ciudad te encuentras?"
                return "Para producción constante de ropa te recomiendo una recta industrial mecatrónica, estable y de bajo consumo.\n\n¿En qué ciudad te encuentras?"
            else:
                # Producción baja - reducir a presupuesto
                return "Para producción ocasional de ropa, una recta industrial básica funciona bien.\n\n¿Tu presupuesto está entre 1.2 y 1.5 millones?"
        else:
            # Afirmar necesidad técnica + reducir opciones
            return "Para ropa necesitas máquina industrial.\n\n¿Es para producción constante o uso ocasional?"
    
    # CASO 2: Gorras - Flujo específico mencionado
    if any(word in text_lower for word in ["gorras", "gorra"]):
        matching_asset = find_matching_asset(text, context, ASSETS)
        
        if context["tipo_maquina"] == "industrial" or "industrial" in text_lower:
            if not context["volumen"]:
                # Afirmación técnica específica + pregunta cerrada
                return "Para gorras necesitas una recta industrial que maneje telas gruesas y costura continua.\n\n¿Vas a producir pocas unidades al día o producción constante tipo taller?"
            elif context["volumen"] == "alto" or any(word in text_lower for word in ["constante", "muchas", "taller"]):
                # MOMENTO DE CIERRE
                if matching_asset:
                    brand_model = f"{matching_asset.get('brand', '')} {matching_asset.get('model', '')}".strip()
                    return f"Para producción constante de gorras te recomiendo la {brand_model}, recta industrial mecatrónica estable y de bajo consumo.\n\nAcompañamos a emprendedores desde cero. No es solo la máquina, es que funcione para tu proyecto. Instalamos y dejamos funcionando.\n\n¿En qué ciudad te encuentras?"
                return "Para producción constante de gorras te recomiendo una recta industrial mecatrónica, estable y de bajo consumo.\n\nAcompañamos a emprendedores desde cero. No es solo la máquina, es que funcione para tu proyecto. Instalamos y dejamos funcionando.\n\n¿En qué ciudad te encuentras?"
            else:
                return "Para producción ocasional de gorras, una recta industrial básica funciona bien.\n\n¿Tu presupuesto está entre 1.2 y 1.5 millones?"
        else:
            return "Para gorras necesitas máquina industrial.\n\n¿Es para producción constante o uso ocasional?"
    
    # CASO 3: Cliente indeciso / Emprendimiento - Reducir opciones rápido
    if any(word in text_lower for word in ["emprendimiento", "emprendedor", "negocio", "recomiendas", "qué máquina", "qué maquina", "necesito"]):
        if not context["tipo_maquina"]:
            # Afirmar + reducir a 2 opciones
            return "Para emprendimiento necesitas máquina industrial.\n\n¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        elif not context["uso"]:
            # Ya tiene tipo, reducir uso
            return "Perfecto, industrial.\n\n¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        elif context["uso"] == "ropa":
            if not context["volumen"]:
                return "Para ropa necesitas una recta industrial que maneje telas variadas.\n\n¿Producción constante o pocas unidades?"
            else:
                # MOMENTO DE CIERRE
                return "Para producción constante de ropa te recomiendo una recta industrial mecatrónica.\n\n¿En qué ciudad te encuentras?"
        elif context["uso"] == "gorras":
            if not context["volumen"]:
                return "Para gorras necesitas una recta industrial que maneje telas gruesas.\n\n¿Producción constante o pocas unidades?"
            else:
                # MOMENTO DE CIERRE
                return "Para producción constante de gorras te recomiendo una recta industrial mecatrónica.\n\n¿En qué ciudad te encuentras?"
        else:
            # Otro uso - reducir a volumen
            return "Para ese tipo de trabajo necesitas una recta industrial.\n\n¿Producción constante o pocas unidades?"
    
    # Consultas sobre máquinas industriales - Direccionar
    if any(word in text_lower for word in ["industrial", "industriales"]):
        if not context["uso"]:
            # Reducir a 4 opciones concretas
            return "Perfecto, industrial.\n\n¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
        elif context["uso"] and not context["volumen"]:
            # Ya tiene uso, reducir a volumen
            return f"Para {context['uso']} necesitas una recta industrial.\n\n¿Producción constante o pocas unidades?"
        elif is_ready_for_close(context):
            # MOMENTO DE CIERRE
            return "Para ese trabajo te recomiendo una recta industrial mecatrónica, estable y de bajo consumo.\n\n¿En qué ciudad te encuentras?"
        else:
            # Tiene uso y volumen bajo - reducir a presupuesto
            return "Para producción constante necesitas una recta industrial mecatrónica.\n\n¿Tu presupuesto está entre 1.2 y 1.5 millones?"
    
    # Consultas sobre máquinas familiares - Reducir opciones
    if any(word in text_lower for word in ["familiar", "casa", "hogar", "personal"]):
        return "Para casa una máquina familiar funciona bien.\n\n¿Qué tipo de costura haces: arreglos, proyectos pequeños o costura creativa?"
    
    # Consultas sobre marcas específicas - Conducir a cierre
    if any(word in text_lower for word in ["kingter", "kt-d3"]):
        if is_ready_for_close(context) or context["marca_interes"] == "kingter":
            return "La KINGTER KT-D3 está en promoción a $1.230.000. Es recta industrial mecatrónica, ideal para producción constante.\n\n¿En qué ciudad te encuentras?"
        else:
            # Reducir a uso
            return "La KINGTER KT-D3 está en promoción a $1.230.000. Es recta industrial mecatrónica.\n\n¿Qué vas a fabricar con ella?"
    
    if any(word in text_lower for word in ["kansew", "ks-8800"]):
        if is_ready_for_close(context) or context["marca_interes"] == "kansew":
            return "La KANSEW KS-8800 está en promoción a $1.300.000. Es recta industrial mecatrónica, ideal para producción constante.\n\n¿En qué ciudad te encuentras?"
        else:
            return "La KANSEW KS-8800 está en promoción a $1.300.000. Es recta industrial mecatrónica.\n\n¿Qué vas a fabricar con ella?"
    
    # Consultas sobre Wilcox - Manejo específico
    if any(word in text_lower for word in ["willcox", "wilcox"]):
        if is_ready_for_close(context):
            return "Tenemos WILLCOX disponible. Es recta industrial de alta calidad, ideal para producción constante.\n\n¿En qué ciudad te encuentras?"
        elif context["uso"] and context["volumen"]:
            return f"Para producción constante de {context['uso']} tenemos WILLCOX disponible. Es recta industrial de alta calidad.\n\n¿En qué ciudad te encuentras?"
        elif context["uso"]:
            return f"Para {context['uso']} tenemos WILLCOX disponible. Es recta industrial de alta calidad.\n\n¿Producción constante o pocas unidades?"
        else:
            return "Tenemos WILLCOX disponible. Es recta industrial de alta calidad.\n\n¿Qué vas a fabricar con ella?"
    
    # Consultas sobre precios - Reducir a 2 opciones
    if any(word in text_lower for word in ["precio", "precios", "cuánto", "cuanto", "cuesta", "vale"]):
        # Si menciona marca específica, dar precio de esa marca
        if "willcox" in text_lower or "wilcox" in text_lower:
            return "Tenemos WILLCOX disponible. Precio varía según modelo.\n\n¿Qué vas a fabricar con ella?"
        elif "kingter" in text_lower or "kt-d3" in text_lower:
            return "La KINGTER KT-D3 está en promoción a $1.230.000. Es recta industrial mecatrónica.\n\n¿Qué vas a fabricar con ella?"
        elif "kansew" in text_lower or "ks-8800" in text_lower:
            return "La KANSEW KS-8800 está en promoción a $1.300.000. Es recta industrial mecatrónica.\n\n¿Qué vas a fabricar con ella?"
        elif context["tipo_maquina"] == "industrial":
            return "Para industrial tenemos promociones: KINGTER KT-D3 a $1.230.000 y KANSEW KS-8800 a $1.300.000.\n\n¿Cuál se ajusta mejor a tu presupuesto?"
        else:
            # Reducir a tipo
            return "Para industrial tenemos promociones desde $1.230.000.\n\n¿Qué vas a fabricar?"
    
    if any(word in text_lower for word in ["barata", "barato", "económica", "económico"]):
        return "La más económica en promoción es la KINGTER KT-D3 a $1.230.000.\n\n¿Qué vas a fabricar con ella?"
    
    # Consultas sobre promociones - Reducir a uso
    if any(word in text_lower for word in ["promo", "promoción", "promocion", "descuento", "oferta"]):
        return "Tenemos promoción: KINGTER KT-D3 a $1.230.000 y KANSEW KS-8800 a $1.300.000. Ambas son rectas industriales mecatrónicas.\n\n¿Qué vas a fabricar?"
    
    # Detectar respuestas sobre volumen/producción - Conducir a cierre
    if any(word in text_lower for word in ["constante", "muchas", "muchos", "taller", "producción", "produccion", "producción continua", "produccion continua", "continua", "negocio"]):
        matching_asset = find_matching_asset(text, context, ASSETS)
        
        if context["uso"]:
            # MOMENTO DE CIERRE
            if matching_asset:
                brand_model = f"{matching_asset.get('brand', '')} {matching_asset.get('model', '')}".strip()
                benefits = matching_asset.get("benefits", [])
                benefit_text = ""
                if "ahorro_energia_70" in benefits:
                    benefit_text = " con ahorro de energía del 70%"
                return f"Para producción constante de {context['uso']} te recomiendo la {brand_model}, recta industrial mecatrónica estable{benefit_text}.\n\nAcompañamos a emprendedores desde cero con asesoría según tu presupuesto y tipo de producción. Instalamos y dejamos funcionando.\n\n¿En qué ciudad te encuentras?"
            return f"Para producción constante de {context['uso']} te recomiendo una recta industrial mecatrónica, estable y de bajo consumo.\n\nAcompañamos a emprendedores desde cero con asesoría según tu presupuesto y tipo de producción. Instalamos y dejamos funcionando.\n\n¿En qué ciudad te encuentras?"
        elif context["tipo_maquina"] == "industrial":
            # Ya tiene tipo industrial y volumen alto, solo falta uso
            return "Para producción constante necesitas una recta industrial mecatrónica.\n\n¿Qué vas a fabricar?"
        else:
            # Reducir a uso
            return "Para producción constante necesitas una recta industrial mecatrónica.\n\n¿Qué vas a fabricar?"
    
    if any(word in text_lower for word in ["pocas", "poca", "poco", "pocos", "ocasional", "casual"]):
        if context["uso"]:
            return f"Para producción ocasional de {context['uso']} una recta industrial básica funciona bien.\n\n¿Tu presupuesto está entre 1.2 y 1.5 millones?"
        else:
            return "Para producción ocasional una recta industrial básica funciona bien.\n\n¿Qué vas a fabricar?"
    
    # Detectar presupuesto - Conducir a cierre
    if any(word in text_lower for word in ["1.2", "1.3", "1.4", "1.5", "millón", "millones", "presupuesto"]):
        if context["uso"]:
            return f"Para {context['uso']} con ese presupuesto te recomiendo la KINGTER KT-D3 a $1.230.000.\n\n¿En qué ciudad te encuentras?"
        else:
            return "Con ese presupuesto te recomiendo la KINGTER KT-D3 a $1.230.000.\n\n¿Qué vas a fabricar?"
    
    # Consultas sobre reparación - Reducir a tipo
    if any(word in text_lower for word in ["reparar", "reparación", "reparacion", "arreglar", "arreglo", "taller", "no funciona", "rota"]):
        return "Tenemos taller de reparación con técnicos especializados.\n\n¿Tu máquina es familiar o industrial?"
    
    # Consultas sobre repuestos - Reducir a 3 opciones
    if any(word in text_lower for word in ["repuesto", "repuestos", "accesorio", "accesorios", "aguja", "agujas", "hilo", "hilos"]):
        return "Tenemos repuestos y accesorios para todas las marcas.\n\n¿Qué necesitas: agujas, hilos o pies especiales?"
    
    # Stock - Conducir a cierre si tiene marca
    if any(word in text_lower for word in ["tienen", "hay", "disponible", "stock"]):
        if context["marca_interes"]:
            if context["marca_interes"] == "kingter":
                marca = "KINGTER KT-D3"
            elif context["marca_interes"] == "kansew":
                marca = "KANSEW KS-8800"
            elif context["marca_interes"] == "willcox":
                marca = "WILLCOX"
            else:
                marca = "máquinas"
            
            if is_ready_for_close(context):
                return f"Sí, tenemos {marca} disponible.\n\n¿En qué ciudad te encuentras?"
            else:
                return f"Sí, tenemos {marca} disponible.\n\n¿Qué vas a fabricar con ella?"
        else:
            return "Sí, tenemos stock de máquinas industriales en promoción.\n\n¿Qué vas a fabricar?"
    
    # Horarios y ubicación - Reducir a 2 opciones
    if any(word in text_lower for word in ["horario", "hora", "cuándo", "abierto", "dónde", "donde", "ubicación"]):
        return "Estamos en Calle 34 # 1-30, Montería. Lunes a viernes 9am-6pm, sábados 9am-2pm.\n\n¿Quieres pasar o prefieres envío?"
    
    # Pago - Pregunta cerrada con afirmación técnica
    if any(word in text_lower for word in ["pago", "pagado", "transferencia", "depósito", "deposito"]):
        if "ya" in text_lower or "hice" in text_lower or "hice el pago" in text_lower:
            return "Perfecto, déjame verificar el estado de tu pago en el sistema.\n\n¿Me pasas el número de referencia de la transferencia o el monto?"
        else:
            return "Aceptamos transferencia bancaria para todas nuestras máquinas.\n\n¿Me pasas el número de referencia o el monto para verificar?"
    
    # Envío - Reducir a ciudad
    if any(word in text_lower for word in ["envío", "envio", "enviado", "llegó", "entrega"]):
        return "Hacemos envíos a todo el país.\n\n¿A qué ciudad necesitas que te enviemos?"
    
    # Garantía - Reducir a tipo de máquina
    if any(word in text_lower for word in ["garantía", "garantia", "garantizado"]):
        return "Todas nuestras máquinas tienen servicio técnico con garantía.\n\n¿Qué máquina te interesa: familiar o industrial?"
    
    # Problemas - necesita escalamiento pero mantiene conversación
    if needs_escalation:
        # El mensaje de handoff se genera en generate_handoff_message() según el tipo específico
        # Este es un fallback genérico
        return "En este punto lo mejor es que uno de nuestros asesores te acompañe directamente para elegir la mejor opción según tu proyecto.\n\n¿Prefieres que te llamemos para agendar una cita?"
    
    # Respuesta genérica reducida (último recurso) - Siempre reducir opciones
    if not context["tipo_maquina"]:
        return "¿Buscas máquina familiar o industrial?"
    elif not context["uso"]:
        return "¿Qué vas a fabricar: ropa, gorras, calzado o accesorios?"
    else:
        return "¿Producción constante o pocas unidades?"

def create_handoff_payload(conversation_id: str, reason: str, priority: str, 
                          summary: str, suggested_response: str, customer_name: Optional[str]) -> HandoffPayload:
    """Crea el payload de handoff"""
    return HandoffPayload(
        conversation_id=conversation_id,
        reason=reason,
        priority=priority,
        summary=summary,
        suggested_response=suggested_response,
        customer_name=customer_name,
        timestamp=datetime.now().isoformat()
    )

def save_handoff(handoff: HandoffPayload):
    """Guarda handoff en DB y outbox"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO handoffs 
            (conversation_id, reason, priority, summary, suggested_response, customer_name, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            handoff.conversation_id,
            handoff.reason,
            handoff.priority,
            handoff.summary,
            handoff.suggested_response,
            handoff.customer_name,
            handoff.timestamp
        ))
        
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"Error guardando handoff en DB: {e}")
        # Continuar aunque falle la DB, al menos guardar en outbox
    finally:
        if conn:
            conn.close()
    
    # Guardar en outbox
    outbox_file = OUTBOX_DIR / f"handoff_{handoff.conversation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outbox_file, "w", encoding="utf-8") as f:
        json.dump(handoff.dict(), f, indent=2, ensure_ascii=False)
    
    # Imprimir para demo
    print("\n" + "="*60)
    print("📱 NOTIFICACIÓN WHATSAPP PARA LUISA")
    print("="*60)
    print(json.dumps(handoff.dict(), indent=2, ensure_ascii=False))
    print("="*60 + "\n")

def notify_whatsapp(handoff: HandoffPayload):
    """Simula notificación WhatsApp (en producción usaría API real)"""
    save_handoff(handoff)
    # En modo real, aquí iría la integración con WhatsApp Cloud API o Twilio

def get_conversation_history(conversation_id: str) -> List[dict]:
    """Obtiene historial de conversación"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT text, sender, timestamp 
        FROM messages 
        WHERE conversation_id = ? 
        ORDER BY timestamp ASC
    """, (conversation_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"text": row[0], "sender": row[1], "timestamp": row[2]}
        for row in rows
    ]

# Endpoints
@app.post("/api/chat")
async def chat(message: Message):
    """Endpoint principal de chat - USA PIPELINE NUEVO"""
    try:
        # Rate limit por conversation_id (ventana 60s)
        if NEW_MODULES_AVAILABLE:
            rate_key = f"chat:{message.conversation_id}"
            if not rl_allow(rate_key, limit_per_minute=30):
                structured_logger.warning(
                    "Rate limit chat",
                    conversation_id=message.conversation_id,
                    remaining=rl_remaining(rate_key, 30)
                )
                raise HTTPException(status_code=429, detail="rate_limited")

        # Usar el pipeline nuevo como principal
        if NEW_MODULES_AVAILABLE:
            from app.services.response_service import build_response

            result = build_response(
                text=message.text,
                conversation_id=message.conversation_id,
                channel="api",
                customer_number=None
            )

            # Convertir formato del pipeline nuevo al formato legacy para compatibilidad
            return {
                "response": result["text"],
                "sender": "luisa",
                "needs_escalation": result["routed_notification"] is not None,
                "asset": result["asset"]
            }

        else:
            # Fallback al legacy si módulos nuevos no están disponibles
            return await _chat_legacy(message)

    except Exception as e:
        logger.error(f"Error en chat endpoint: {str(e)}")
        # Retornar respuesta básica aunque falle
        return {
            "response": "Lo siento, hubo un error técnico. ¿Puedes repetir tu consulta?",
            "sender": "luisa",
            "needs_escalation": False
        }


async def _chat_legacy(message: Message):
    """Endpoint principal de chat"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        # Crear conversación si no existe
        cursor.execute("""
            INSERT OR IGNORE INTO conversations (conversation_id, status)
            VALUES (?, 'active')
        """, (message.conversation_id,))
        
        # Guardar mensaje del cliente
        cursor.execute("""
            INSERT INTO messages (conversation_id, text, sender)
            VALUES (?, ?, ?)
        """, (message.conversation_id, message.text, message.sender))
        
        # Obtener historial (cerrar conexión antes para evitar bloqueos)
        conn.commit()
        conn.close()
        conn = None
        
        # Obtener historial con nueva conexión
        history = get_conversation_history(message.conversation_id)
        
        # Analizar mensaje
        analysis = analyze_message(message.text, history)
        
        # Generar respuesta
        # Si necesita handoff, usar mensaje específico de handoff
        if analysis["needs_escalation"]:
            context_for_response = extract_context_from_history(history)
            ciudad_men = context_for_response.get("ciudad") or next((c for c in ["montería", "monteria", "bogotá", "bogota", "medellín", "medellin"] if c in message.text.lower()), None)
            response_text = generate_handoff_message(message.text, analysis["reason"], analysis["priority"], ciudad_men)
        else:
            response_text = analysis["response"]
        
        # Abrir nueva conexión para guardar respuesta y handoff
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        # Guardar respuesta de Luisa
        cursor.execute("""
            INSERT INTO messages (conversation_id, text, sender)
            VALUES (?, ?, 'luisa')
        """, (message.conversation_id, response_text))
        
        # Si necesita escalamiento, crear handoff
        if analysis["needs_escalation"]:
            # Obtener nombre del cliente si existe
            cursor.execute("""
                SELECT customer_name FROM conversations WHERE conversation_id = ?
            """, (message.conversation_id,))
            row = cursor.fetchone()
            customer_name = row[0] if row else None
            
            # Crear resumen de la conversación más detallado
            recent_messages = history[-6:] if len(history) > 6 else history
            summary = f"📋 RESUMEN DE CONVERSACIÓN\n\n"
            summary += f"Último mensaje del cliente: {message.text}\n\n"
            summary += f"Historial reciente:\n"
            for msg in recent_messages:
                sender_label = "👤 Cliente" if msg["sender"] == "customer" else "💬 Luisa"
                summary += f"{sender_label}: {msg['text']}\n"
            
            # Agregar contexto del negocio si aplica
            if any(word in message.text.lower() for word in ["máquina", "maquina", "comprar", "precio"]):
                summary += "\n💡 CONTEXTO: Cliente interesado en compra de máquina"
            elif any(word in message.text.lower() for word in ["reparar", "arreglar", "taller"]):
                summary += "\n💡 CONTEXTO: Cliente necesita servicio de reparación"
            elif any(word in message.text.lower() for word in ["emprendimiento", "negocio", "proyecto"]):
                summary += "\n💡 CONTEXTO: Cliente emprendedor buscando asesoría"
            
            # Generar respuesta sugerida según tipo de handoff
            # Extraer ciudad del contexto o texto
            context_for_handoff = extract_context_from_history(history)
            ciudad_men = context_for_handoff.get("ciudad") or next((c for c in ["montería", "monteria", "bogotá", "bogota", "medellín", "medellin"] if c in message.text.lower()), None)
            suggested_response = generate_handoff_message(message.text, analysis["reason"], analysis["priority"], ciudad_men)
            
            # Crear handoff
            handoff = create_handoff_payload(
                conversation_id=message.conversation_id,
                reason=analysis["reason"],
                priority=analysis["priority"],
                summary=summary,
                suggested_response=suggested_response,
                customer_name=customer_name
            )
            
            # Actualizar estado de conversación antes de cerrar
            cursor.execute("""
                UPDATE conversations SET status = 'escalated', updated_at = CURRENT_TIMESTAMP
                WHERE conversation_id = ?
            """, (message.conversation_id,))
            
            conn.commit()
            conn.close()
            conn = None
            
            # Notificar después de cerrar la conexión principal
            notify_whatsapp(handoff)
        else:
            conn.commit()
            conn.close()
            conn = None
        
        # Buscar asset del catálogo usando regla exacta de matching
        context = extract_context_from_history(history)
        
        # Usar análisis de intención para determinar si solicita foto o promoción
        intent_result_chat = None
        solicita_foto = False
        pregunta_promocion = False
        pregunta_promocion_por_contexto = False  # Flag para no sobrescribir
        
        # Verificar contexto conversacional primero - PRIORIDAD ALTA
        # Si Luisa propuso mostrar promociones y el usuario confirma
        if context.get("esperando_confirmacion") and context.get("ultimo_tema") == "promocion":
            text_lower_msg = message.text.lower()
            # Detectar confirmaciones explícitas o implícitas
            confirmacion_keywords = ["si", "sí", "ok", "dale", "claro", "perfecto", "bueno", "vale", 
                                      "quiero ver", "muestrame", "muéstrame", "ver", "a ver", "enséñame",
                                      "manda", "envía", "envia", "pásame", "pasame", "dime", "cuáles", "cuales"]
            if any(word in text_lower_msg for word in confirmacion_keywords):
                pregunta_promocion = True
                pregunta_promocion_por_contexto = True
                print(f"DEBUG: Promoción detectada por CONTEXTO (confirmación de usuario)")
        
        # También detectar directamente en el mensaje (palabras explícitas de promoción)
        if not pregunta_promocion:
            promo_keywords_direct = ["promoción", "promocion", "promociones", "oferta", "ofertas", 
                                      "descuento", "descuentos", "navidad", "navideña", "navidena",
                                      "especial", "rebaja", "ganga", "barato"]
            if any(keyword in message.text.lower() for keyword in promo_keywords_direct):
                pregunta_promocion = True
                pregunta_promocion_por_contexto = True
                print(f"DEBUG: Promoción detectada por KEYWORDS DIRECTOS")
        
        if intent_analyzer:
            try:
                intent_result_chat = intent_analyzer.analyze(message.text, history)
                solicita_foto = intent_result_chat.get("requires_asset", False) or (IntentType and intent_result_chat.get("intent") == IntentType.SOLICITAR_FOTOS)
                
                # IMPORTANTE: Solo actualizar pregunta_promocion desde intent_analyzer si NO fue detectado por contexto
                if not pregunta_promocion_por_contexto:
                    intent_es_promocion = (IntentType and intent_result_chat.get("intent") == IntentType.PREGUNTAR_PROMOCIONES)
                    if intent_es_promocion:
                        pregunta_promocion = True
                        print(f"DEBUG: Promoción detectada por INTENT_ANALYZER")
                
                # Combinar contexto del historial con contexto de intención
                if intent_result_chat.get("context"):
                    context = {**context, **intent_result_chat["context"]}
            except Exception as e:
                print(f"Error en análisis de intención en chat: {e}")
                # Fallback: detección tradicional (solo si no se detectó por contexto)
                if not pregunta_promocion_por_contexto:
                    foto_keywords = ["fotos", "foto", "imágenes", "imagenes", "imagen", "muéstrame", "muestrame", "ver", "quiero ver", "tienes fotos", "tiene fotos", "muestra", "fotografía", "fotografia"]
                    solicita_foto = any(keyword in message.text.lower() for keyword in foto_keywords)
                    promo_keywords = ["promoción", "promocion", "promociones", "oferta", "descuento", "navidad"]
                    pregunta_promocion = any(keyword in message.text.lower() for keyword in promo_keywords)
        else:
            # Fallback: detección tradicional (solo si no se detectó por contexto)
            if not pregunta_promocion_por_contexto:
                foto_keywords = ["fotos", "foto", "imágenes", "imagenes", "imagen", "muéstrame", "muestrame", "ver", "quiero ver", "tienes fotos", "tiene fotos", "muestra", "fotografía", "fotografia"]
                solicita_foto = any(keyword in message.text.lower() for keyword in foto_keywords)
                promo_keywords = ["promoción", "promocion", "promociones", "oferta", "descuento", "navidad"]
                pregunta_promocion = any(keyword in message.text.lower() for keyword in promo_keywords)
        
        print(f"DEBUG: pregunta_promocion={pregunta_promocion}, pregunta_promocion_por_contexto={pregunta_promocion_por_contexto}")
        
        # Siempre preparar la ruta de la imagen de promoción
        # Se usará si pregunta_promocion es True
        promo_path = Path("assets/catalog/promociones/promocion_navidad_2024.png")
        if not promo_path.exists():
            promo_path = Path("backend/assets/catalog/promociones/promocion_navidad_2024.png")
        promo_image_path = promo_path if promo_path.exists() else None
        
        if pregunta_promocion:
            print(f"DEBUG: Promoción detectada. Imagen path: {promo_image_path}, exists: {promo_image_path.exists() if promo_image_path else 'N/A'}")
        
        catalog_item, handoff_from_asset = select_catalog_asset(message.text, context)
        
        # NO mostrar imágenes durante flujo de captura de lead (handoff)
        # Detectar si estamos en flujo de captura de datos
        en_flujo_captura_lead = False
        flujo_keywords = ["llamada", "llamen", "número", "numero", "celular", "teléfono", "telefono",
                         "hora", "mañana", "tarde", "noche", "visita", "cita", "día", "dia",
                         "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
        if any(keyword in message.text.lower() for keyword in flujo_keywords):
            en_flujo_captura_lead = True
        if context.get("ultimo_tema") in ["cierre_handoff", "diagnostico_ciudad"]:
            en_flujo_captura_lead = True
        if analysis["needs_escalation"]:
            en_flujo_captura_lead = True
            
        # Si estamos en flujo de captura, no enviar asset
        if en_flujo_captura_lead:
            catalog_item = None
        
        # Si solicita foto explícitamente y no hay asset del matching normal, buscar cualquier asset relevante
        if solicita_foto and not catalog_item:
            # Detectar intención del texto directamente
            text_lower = message.text.lower()
            categoria_buscada = None
            
            # Detectar categoría desde el texto
            if any(word in text_lower for word in ["familiar", "familiares", "casa", "doméstico", "domestico", "hogar"]):
                categoria_buscada = "familiar"
            elif any(word in text_lower for word in ["fileteadora", "fileteadoras", "filetear"]):
                categoria_buscada = "fileteadora_familiar"
            elif any(word in text_lower for word in ["industrial", "industriales", "taller", "producción", "produccion"]):
                categoria_buscada = "recta_industrial_mecatronica"
            elif context.get("tipo_maquina") == "industrial":
                categoria_buscada = "recta_industrial_mecatronica"
            elif context.get("tipo_maquina") == "familiar":
                categoria_buscada = "familiar"
            
            # Buscar asset según categoría detectada
            if categoria_buscada:
                # Buscar assets de esa categoría ordenados por prioridad
                matching_items = []
                for image_id, item in CATALOG_INDEX.items():
                    if item.get("category") == categoria_buscada:
                        matching_items.append((image_id, item))
                
                if matching_items:
                    # Ordenar por prioridad DESC, luego image_id ASC
                    matching_items.sort(key=lambda x: (-x[1].get("priority", 0), x[0]))
                    catalog_item = get_catalog_item(matching_items[0][0])
            
            # Si aún no hay asset, usar el de mayor prioridad general
            if not catalog_item:
                sorted_items = sorted(CATALOG_INDEX.items(), key=lambda x: (-x[1].get("priority", 0), x[0]))
                if sorted_items:
                    catalog_item = get_catalog_item(sorted_items[0][0])
        
        asset_info = None
        
        # Si pregunta por promociones, usar imagen de promoción
        if pregunta_promocion and promo_image_path and promo_image_path.exists():
            try:
                with open(promo_image_path, 'rb') as f:
                    header = f.read(8)
                    is_valid = (
                        header.startswith(b'\x89PNG') or
                        header.startswith(b'\xff\xd8\xff') or
                        (header.startswith(b'RIFF') and len(header) >= 8 and b'WEBP' in header[:12])
                    )
                    if is_valid:
                        asset_info = {
                            "image_id": "PROMO_NAVIDAD",
                            "asset_url": "/api/assets/promo_navidad",
                            "type": "image"
                        }
            except Exception as e:
                print(f"Error verificando imagen de promoción: {e}")
        
        # Solo incluir asset si no requiere handoff y no hay asset de promoción ya asignado
        if catalog_item and not handoff_from_asset and not asset_info:
            asset_file = find_local_asset_file(catalog_item["image_id"])
            if asset_file and asset_file.exists():
                # Si se solicita foto explícitamente, incluir asset incluso si es placeholder
                # (el frontend manejará el error 404)
                if solicita_foto:
                    mime_type = get_asset_mime_type(asset_file)
                    asset_type = "video" if mime_type.startswith("video/") else "image"
                    asset_info = {
                        "image_id": catalog_item["image_id"],
                        "asset_url": f"/api/assets/{catalog_item['image_id']}",
                        "type": asset_type
                    }
                else:
                    # Para matching automático, validar que sea imagen válida (no placeholder)
                    try:
                        with open(asset_file, 'rb') as f:
                            header = f.read(8)
                            is_valid = (
                                header.startswith(b'\x89PNG') or
                                header.startswith(b'\xff\xd8\xff') or
                                (header.startswith(b'RIFF') and len(header) >= 8 and b'WEBP' in header[:12])
                            )
                            if is_valid:
                                mime_type = get_asset_mime_type(asset_file)
                                asset_type = "video" if mime_type.startswith("video/") else "image"
                                asset_info = {
                                    "image_id": catalog_item["image_id"],
                                    "asset_url": f"/api/assets/{catalog_item['image_id']}",
                                    "type": asset_type
                                }
                    except Exception:
                        pass  # Si hay error, no incluir asset
        
        return {
            "response": response_text,
            "sender": "luisa",
            "needs_escalation": analysis["needs_escalation"],
            "asset": asset_info
        }
    except sqlite3.OperationalError as e:
        print(f"Error de base de datos: {e}")
        # Retornar respuesta básica aunque falle la DB
        try:
            history = get_conversation_history(message.conversation_id)
            analysis = analyze_message(message.text, history)
            return {
                "response": analysis["response"],
                "sender": "luisa",
                "needs_escalation": analysis["needs_escalation"],
                "asset": None
            }
        except:
            return {
                "response": "Disculpa, hubo un problema técnico. ¿Puedes intentar de nuevo?",
                "sender": "luisa",
                "needs_escalation": False,
                "asset": None
            }
    except Exception as e:
        print(f"Error inesperado en chat: {e}")
        import traceback
        traceback.print_exc()
        return {
            "response": "Disculpa, hubo un problema técnico. ¿Puedes intentar de nuevo?",
            "sender": "luisa",
            "needs_escalation": False,
            "asset": None
        }
    finally:
        if conn:
            conn.close()

def generate_handoff_message(text: str, reason: str, priority: str, ciudad: Optional[str] = None) -> str:
    """Genera mensaje de handoff específico según el tipo de necesidad"""
    text_lower = text.lower()
    
    # Detectar si está en Montería
    ciudades_monteria = ["montería", "monteria"]
    esta_en_monteria = False
    if ciudad:
        esta_en_monteria = ciudad.lower() in ciudades_monteria
    if not esta_en_monteria:
        esta_en_monteria = any(c in text_lower for c in ciudades_monteria)
    
    # Handoff por impacto de negocio o servicio diferencial
    if ("proyecto de negocio" in reason.lower() or "servicio diferencial" in reason.lower() or 
        "asesoría humana especializada" in reason.lower() or "instalación" in text_lower or 
        "asesoría" in text_lower or "visita" in text_lower or "montar" in text_lower and "negocio" in text_lower):
        if esta_en_monteria:
            return "En este punto lo mejor es que uno de nuestros asesores te acompañe directamente para elegir la mejor opción según tu proyecto.\n\n¿Prefieres que te llamemos para agendar una cita con el asesor o agendamos una visita del equipo a tu taller?"
        else:
            return "En este punto lo mejor es que uno de nuestros asesores te acompañe directamente para elegir la mejor opción según tu proyecto.\n\n¿Prefieres que te llamemos para agendar una cita con el asesor?"
    
    # Handoff geográfico
    if ("coordinación logística" in reason.lower() or "fuera de Montería" in reason.lower() or 
        ("ciudad" in reason.lower() and "montería" not in reason.lower())):
        return "Para coordinar el envío e instalación a tu ubicación, lo mejor es que uno de nuestros asesores te contacte directamente.\n\n¿Prefieres que te llamemos para agendar la entrega e instalación?"
    
    # Handoff por decisión de compra (incluye cuando menciona ciudad)
    if ("decisión de compra" in reason.lower() or "cierre comercial" in reason.lower() or 
        ("ciudad" in reason.lower() and "coordinación" in reason.lower())):
        if esta_en_monteria:
            return "Para coordinar el pago y la entrega, lo mejor es que uno de nuestros asesores te acompañe.\n\n¿Prefieres que te llamemos para agendar la entrega o prefieres pasar por el almacén?"
        else:
            return "Para coordinar el pago y el envío, lo mejor es que uno de nuestros asesores te contacte directamente.\n\n¿Prefieres que te llamemos para agendar el envío?"
    
    # Handoff por ambigüedad crítica
    if "múltiples necesidades técnicas" in reason.lower():
        if esta_en_monteria:
            return "Para asegurar la mejor recomendación según tus necesidades específicas, lo mejor es que uno de nuestros asesores técnicos te acompañe.\n\n¿Prefieres que te llamemos para agendar una cita o agendamos una visita del equipo?"
        else:
            return "Para asegurar la mejor recomendación según tus necesidades específicas, lo mejor es que uno de nuestros asesores técnicos te contacte.\n\n¿Prefieres que te llamemos para agendar una consulta?"
    
    # Handoff urgente o genérico
    if priority == "urgent":
        return "Esto requiere atención inmediata. Estoy conectándote con nuestro equipo especializado.\n\n¿Prefieres que te llamemos ahora mismo?"
    elif priority == "high":
        return "En este punto lo mejor es que uno de nuestros asesores te acompañe directamente.\n\n¿Prefieres que te llamemos para agendar una cita?"
    else:
        return "Perfecto, lo estoy revisando con nuestro equipo y te respondo en breve."

def generate_bridge_message(priority: str) -> str:
    """Genera mensaje puente mientras se procesa el escalamiento"""
    if priority == "urgent":
        urgent_bridges = [
            "Entendido, esto es urgente. Estoy consultando con nuestro técnico especializado y te respondo en los próximos minutos.",
            "Perfecto, lo estoy revisando con máxima prioridad con el equipo técnico. Te respondo enseguida.",
            "Claro, esto requiere atención inmediata. Estoy consultando con nuestros especialistas y te respondo ahora mismo."
        ]
        return random.choice(urgent_bridges)
    elif priority == "high":
        high_bridges = [
            "Perfecto, estoy consultando con el equipo técnico para darte la mejor solución. Un momento por favor.",
            "Déjame revisar esto con nuestros especialistas en reparación y máquinas. Te respondo en breve.",
            "Claro, estoy verificando esto con el equipo para darte una respuesta precisa sobre tu consulta. Un momento."
        ]
        return random.choice(high_bridges)
    else:
        medium_bridges = [
            "Perfecto, déjame consultar con nuestros especialistas para darte la mejor recomendación según tu proyecto y presupuesto. Te respondo en breve.",
            "Claro, estoy revisando las opciones disponibles para ti. Te aviso pronto con las mejores alternativas.",
            "Entendido, déjame consultar esto con el equipo para darte una respuesta personalizada. Un momento."
        ]
        return random.choice(medium_bridges)

@app.get("/api/handoffs")
async def get_handoffs():
    """Obtiene todos los handoffs (para vista interna)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT conversation_id, reason, priority, summary, suggested_response, 
               customer_name, timestamp
        FROM handoffs
        ORDER BY timestamp DESC
        LIMIT 50
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "conversation_id": row[0],
            "reason": row[1],
            "priority": row[2],
            "summary": row[3],
            "suggested_response": row[4],
            "customer_name": row[5],
            "timestamp": row[6]
        }
        for row in rows
    ]

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Obtiene una conversación completa"""
    history = get_conversation_history(conversation_id)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT customer_name, status FROM conversations WHERE conversation_id = ?
    """, (conversation_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "conversation_id": conversation_id,
        "customer_name": row[0] if row else None,
        "status": row[1] if row else "active",
        "messages": history
    }

# ============================================================================
# ENDPOINTS DE CATÁLOGO DE IMÁGENES
# ============================================================================

@app.get("/api/catalog/items")
async def get_catalog_items():
    """Devuelve lista de items del catálogo con asset_url"""
    # Combinar catálogo de DB y filesystem
    db_catalog = load_catalog_from_db()
    fs_catalog = load_catalog_from_filesystem()
    
    # DB tiene prioridad sobre filesystem
    combined_catalog = {**fs_catalog, **db_catalog}
    
    items = []
    for image_id, item in combined_catalog.items():
        items.append({
            "image_id": item.get("image_id"),
            "title": item.get("title"),
            "category": item.get("category"),
            "brand": item.get("brand"),
            "model": item.get("model"),
            "represents": item.get("represents"),
            "conversation_role": item.get("conversation_role"),
            "priority": item.get("priority", 0),
            "send_when_customer_says": item.get("send_when_customer_says", []),
            "asset_url": f"/api/assets/{image_id}"
        })
    
    return {"items": items, "count": len(items)}

@app.get("/api/assets/{image_id}")
async def serve_asset(image_id: str, request: Request):
    """Sirve el archivo binario (imagen o video) del catálogo"""
    # Manejar imagen de promoción navideña
    if image_id == "promo_navidad":
        promo_path = Path("assets/catalog/promociones/promocion_navidad_2024.png")
        if promo_path.exists():
            return FileResponse(
                promo_path,
                media_type="image/png",
                filename="promocion_navidad_2024.png"
            )
        else:
            raise HTTPException(status_code=404, detail="Imagen de promoción no encontrada")
    
    item = get_catalog_item(image_id)
    
    if not item:
        raise HTTPException(status_code=404, detail=f"Asset {image_id} no encontrado")
    
    asset_provider = item.get("asset_provider", ASSET_PROVIDER)
    
    # Modo local
    if asset_provider == "local":
        asset_file = find_local_asset_file(image_id)
        if not asset_file or not asset_file.exists():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado para {image_id}")
        
        # Verificar que el archivo sea una imagen/video válida (no un placeholder de texto)
        try:
            with open(asset_file, 'rb') as f:
                header = f.read(8)
                # Verificar headers de imágenes/videos comunes
                is_valid_image = (
                    header.startswith(b'\x89PNG') or  # PNG
                    header.startswith(b'\xff\xd8\xff') or  # JPEG
                    (header.startswith(b'RIFF') and len(header) >= 8 and b'WEBP' in header[:12]) or  # WEBP
                    header.startswith(b'\x00\x00\x01\x00')  # ICO
                )
                is_valid_video = header.startswith(b'\x00\x00\x00') and b'ftyp' in header[:12]  # MP4
                
                if not (is_valid_image or is_valid_video):
                    # Es un placeholder de texto, retornar 404
                    raise HTTPException(status_code=404, detail=f"Imagen placeholder detectada - agregar imagen real para {image_id}")
        except HTTPException:
            raise
        except Exception:
            pass  # Continuar si hay error leyendo el archivo
        
        mime_type = get_asset_mime_type(asset_file)
        
        # Para videos, usar StreamingResponse
        if mime_type.startswith("video/"):
            return StreamingResponse(
                open(asset_file, "rb"),
                media_type=mime_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(asset_file.stat().st_size)
                }
            )
        
        return FileResponse(
            asset_file,
            media_type=mime_type,
            filename=asset_file.name
        )
    
    # Modo Drive
    elif asset_provider == "drive":
        drive_file_id = item.get("drive_file_id")
        if not drive_file_id:
            raise HTTPException(status_code=404, detail=f"Drive file_id no encontrado para {image_id}")
        
        mime_type = item.get("drive_mime_type", "application/octet-stream")
        
        # Verificar cache primero
        cached_file = get_cached_file(drive_file_id)
        if cached_file:
            if mime_type.startswith("video/"):
                return StreamingResponse(
                    open(cached_file, "rb"),
                    media_type=mime_type,
                    headers={
                        "Accept-Ranges": "bytes",
                        "Content-Length": str(cached_file.stat().st_size)
                    }
                )
            return FileResponse(cached_file, media_type=mime_type)
        
        # Descargar desde Drive
        content = download_from_drive(drive_file_id)
        if not content:
            raise HTTPException(status_code=500, detail="Error descargando desde Drive")
        
        # Guardar en cache
        cached_file = save_to_cache(drive_file_id, content, mime_type)
        
        if mime_type.startswith("video/"):
            return StreamingResponse(
                open(cached_file, "rb"),
                media_type=mime_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(len(content))
                }
            )
        
        return FileResponse(cached_file, media_type=mime_type)
    
    else:
        raise HTTPException(status_code=500, detail=f"Asset provider desconocido: {asset_provider}")

class CatalogSyncPayload(BaseModel):
    image_id: str
    meta: dict
    asset: Optional[dict] = None

@app.post("/api/catalog/sync")
async def sync_catalog_item(
    payload: CatalogSyncPayload,
    x_luisa_api_key: Optional[str] = Header(None, alias="X-LUISA-API-KEY")
):
    """Endpoint para sincronizar items del catálogo desde n8n/Drive"""
    # Validar API key
    if x_luisa_api_key != LUISA_API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")
    
    # Validar payload
    if not payload.image_id or not payload.meta:
        raise HTTPException(status_code=400, detail="Payload inválido: image_id y meta son requeridos")
    
    # Extraer datos del asset
    asset_info = payload.asset or {}
    drive_file_id = asset_info.get("drive_file_id")
    drive_mime_type = asset_info.get("mime_type", "")
    file_name = asset_info.get("file_name", "")
    
    # Preparar datos para DB
    meta_json = json.dumps(payload.meta, ensure_ascii=False)
    send_when = json.dumps(payload.meta.get("send_when_customer_says", []), ensure_ascii=False)
    
    # Upsert en DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO catalog_items 
        (image_id, title, category, brand, model, represents, conversation_role,
         priority, send_when_customer_says, meta_json, drive_file_id, 
         drive_mime_type, asset_provider, file_name, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        payload.image_id,
        payload.meta.get("title", ""),
        payload.meta.get("category", ""),
        payload.meta.get("brand", ""),
        payload.meta.get("model", ""),
        payload.meta.get("represents", ""),
        payload.meta.get("conversation_role", ""),
        payload.meta.get("priority", 0),
        send_when,
        meta_json,
        drive_file_id,
        drive_mime_type,
        "drive" if drive_file_id else "local",
        file_name
    ))
    
    conn.commit()
    conn.close()
    
    return {"ok": True, "image_id": payload.image_id}


# ============================================================================
# ENDPOINTS ADICIONALES
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check con información de módulos."""
    return {
        "status": "healthy",
        "service": "luisa",
        "version": "2.0.0",
        "modules": {
            "new_modules": NEW_MODULES_AVAILABLE,
            "whatsapp": WHATSAPP_ENABLED if NEW_MODULES_AVAILABLE else False,
            "openai": OPENAI_ENABLED if NEW_MODULES_AVAILABLE else False,
            "cache": CACHE_ENABLED if NEW_MODULES_AVAILABLE else False
        },
        "catalog_items": len(CATALOG_INDEX)
    }


@app.get("/api/cache/stats")
async def get_cache_stats():
    """Estadísticas del cache."""
    if NEW_MODULES_AVAILABLE and CACHE_ENABLED:
        from app.services.cache_service import get_cache_stats
        return get_cache_stats()
    return {"enabled": False, "message": "Cache no disponible"}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("🚀 Iniciando LUISA - Asistente El Sastre")
    print("=" * 60)
    print(f"📦 Módulos nuevos: {'✅' if NEW_MODULES_AVAILABLE else '❌'}")
    if NEW_MODULES_AVAILABLE:
        print(f"📱 WhatsApp: {'✅ Habilitado' if WHATSAPP_ENABLED else '❌ Deshabilitado'}")
        print(f"🤖 OpenAI: {'✅ Habilitado' if OPENAI_ENABLED else '❌ Deshabilitado'}")
        print(f"💾 Cache: {'✅ Habilitado' if CACHE_ENABLED else '❌ Deshabilitado'}")
    print(f"📋 Items en catálogo: {len(CATALOG_INDEX)}")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)

