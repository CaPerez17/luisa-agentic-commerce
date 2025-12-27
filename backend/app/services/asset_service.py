"""
Servicio de gestión de assets y catálogo.
Mantiene compatibilidad con la estructura existente.
"""
import json
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from app.config import ASSETS_DIR, ASSETS_CATALOG_DIR
from app.rules.keywords import normalize_text
from app.logging_config import logger


# Cache global del catálogo
_CATALOG_CACHE: Dict[str, dict] = {}
_CATALOG_INDEX: Dict[str, dict] = {}


def load_catalog_index() -> Dict[str, dict]:
    """Carga el índice del catálogo desde catalog_index.json."""
    global _CATALOG_INDEX
    
    if _CATALOG_INDEX:
        return _CATALOG_INDEX
    
    index_path = ASSETS_DIR / "catalog_index.json"
    if not index_path.exists():
        logger.warning("catalog_index.json no encontrado")
        return {}
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
            for item in index_data.get("items", []):
                _CATALOG_INDEX[item["image_id"]] = item
            logger.info("Catálogo cargado", items=len(_CATALOG_INDEX))
            return _CATALOG_INDEX
    except Exception as e:
        logger.error("Error cargando catalog_index.json", error=str(e))
        return {}


def load_catalog_from_filesystem() -> Dict[str, dict]:
    """Carga catálogo completo desde archivos locales."""
    global _CATALOG_CACHE
    
    if _CATALOG_CACHE:
        return _CATALOG_CACHE
    
    if not ASSETS_CATALOG_DIR.exists():
        return {}
    
    # Cargar desde carpetas I*_*
    for catalog_folder in ASSETS_CATALOG_DIR.iterdir():
        if catalog_folder.is_dir() and catalog_folder.name.startswith("I"):
            meta_path = catalog_folder / "meta.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        image_id = meta.get("image_id")
                        if image_id:
                            _CATALOG_CACHE[image_id] = {
                                **meta,
                                "asset_provider": "local",
                                "local_path": str(catalog_folder)
                            }
                except Exception as e:
                    logger.error(f"Error cargando {meta_path}", error=str(e))
    
    logger.info("Catálogo filesystem cargado", items=len(_CATALOG_CACHE))
    return _CATALOG_CACHE


def get_catalog_item(image_id: str) -> Optional[dict]:
    """Obtiene un item del catálogo por image_id."""
    # Primero intentar desde cache
    catalog = load_catalog_from_filesystem()
    if image_id in catalog:
        return catalog[image_id]
    
    # Buscar en carpetas directamente
    for catalog_folder in ASSETS_CATALOG_DIR.iterdir():
        if catalog_folder.is_dir() and catalog_folder.name.startswith(f"{image_id}_"):
            meta_path = catalog_folder / "meta.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        return {
                            **meta,
                            "asset_provider": "local",
                            "local_path": str(catalog_folder)
                        }
                except:
                    pass
    
    return None


def find_local_asset_file(image_id: str) -> Optional[Path]:
    """Encuentra el archivo de asset local (image_1.* o video_1.mp4)."""
    item = get_catalog_item(image_id)
    if not item:
        # Buscar directamente en carpetas
        for catalog_folder in ASSETS_CATALOG_DIR.iterdir():
            if catalog_folder.is_dir() and catalog_folder.name.startswith(f"{image_id}_"):
                for ext in ["png", "jpg", "jpeg", "webp"]:
                    img_file = catalog_folder / f"image_1.{ext}"
                    if img_file.exists():
                        return img_file
                video_file = catalog_folder / "video_1.mp4"
                if video_file.exists():
                    return video_file
        return None
    
    if item.get("local_path"):
        catalog_path = Path(item["local_path"])
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
    """Determina el MIME type del archivo."""
    ext = file_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".mp4": "video/mp4"
    }
    return mime_types.get(ext, "application/octet-stream")


def select_catalog_asset(text: str, context: dict) -> Tuple[Optional[dict], bool]:
    """
    Selecciona el asset del catálogo según texto y contexto.
    
    Returns:
        Tuple[catalog_item, handoff_required]
    """
    text_lower = normalize_text(text)
    catalog_index = load_catalog_index()
    handoff_required = False
    
    # Paso 0: Detectar máquinas específicas por nombre/modelo
    specific_matches = {
        "I007": ["6705c", "6705", "singer heavy duty 6705"],
        "I006": ["singer heavy duty"],
        "I001": ["ssgemsy", "sg8802e", "8802", "mecatronica"],
        "I002": ["union un300", "un300"],
        "I003": ["kansew", "ks653"],
        "I004": ["singer s0105", "s0105", "fileteadora singer"],
        "I005": ["kingter", "fileteadora kingter"],
    }
    
    for image_id, keywords in specific_matches.items():
        for keyword in keywords:
            if keyword in text_lower:
                full_item = get_catalog_item(image_id)
                if full_item:
                    return full_item, False
    
    # Paso 1: Determinar categoría primaria
    category = None
    
    if context.get("tipo_maquina") == "industrial":
        category = "recta_industrial_mecatronica"
    elif context.get("tipo_maquina") == "familiar":
        if any(word in text_lower for word in ["fileteadora", "filetear", "orillos"]):
            category = "fileteadora_familiar"
        else:
            category = "familiar"
    elif any(word in text_lower for word in ["fileteadora", "filetear", "orillos"]):
        category = "fileteadora_familiar"
    elif any(word in text_lower for word in ["empezar", "hogar", "uso personal", "casa", "familiar"]):
        category = "familiar"
    elif any(word in text_lower for word in ["taller", "producción", "produccion", "industrial", "negocio"]):
        category = "recta_industrial_mecatronica"
    
    # Detectar conflicto
    has_familiar = any(word in text_lower for word in ["familiar", "casa", "hogar"])
    has_industrial = any(word in text_lower for word in ["industrial", "taller", "producción constante"])
    
    if has_familiar and has_industrial:
        return None, True
    
    if not category:
        return None, False
    
    # Paso 2: Filtrar por categoría
    matching_items = []
    for image_id, item in catalog_index.items():
        if item.get("category") == category:
            matching_items.append(item)
    
    if not matching_items:
        return None, False
    
    # Paso 3: Ordenar por priority DESC
    matching_items.sort(key=lambda x: (-x.get("priority", 0), x.get("image_id", "")))
    
    selected_item = matching_items[0]
    full_item = get_catalog_item(selected_item["image_id"])
    
    return full_item, handoff_required


def get_all_catalog_items() -> List[dict]:
    """Obtiene todos los items del catálogo para el endpoint."""
    catalog_index = load_catalog_index()
    items = []
    
    for image_id, item in catalog_index.items():
        items.append({
            "image_id": image_id,
            "slug": item.get("slug"),
            "path": item.get("path"),
            "category": item.get("category"),
            "brand": item.get("brand"),
            "model": item.get("model"),
            "represents": item.get("represents"),
            "conversation_role": item.get("conversation_role"),
            "priority": item.get("priority"),
            "send_when_customer_says": item.get("send_when_customer_says", []),
            "asset_url": f"/api/assets/{image_id}"
        })
    
    return items


def get_promo_image_path() -> Optional[Path]:
    """Obtiene la ruta de la imagen de promoción navideña."""
    promo_path = ASSETS_CATALOG_DIR / "promociones" / "promocion_navidad_2024.png"
    if promo_path.exists():
        return promo_path
    return None


def validate_image_file(file_path: Path) -> bool:
    """Valida que un archivo sea una imagen válida."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
            return (
                header.startswith(b'\x89PNG') or
                header.startswith(b'\xff\xd8\xff') or
                (header.startswith(b'RIFF') and len(header) >= 8 and b'WEBP' in header[:12])
            )
    except:
        return False


# Cargar catálogo al importar
load_catalog_index()
load_catalog_from_filesystem()
