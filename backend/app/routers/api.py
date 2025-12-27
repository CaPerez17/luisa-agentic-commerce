"""
Router principal de la API.
Mantiene compatibilidad con endpoints existentes:
- POST /api/chat
- GET /api/assets/{image_id}
- GET /api/catalog/items
- POST /api/catalog/sync
- GET /api/handoffs
"""
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional
import io

from app.models.schemas import (
    ChatMessage,
    ChatResponse,
    CatalogResponse,
    CatalogSyncPayload,
    AssetInfo
)
from app.models.database import (
    get_handoffs,
    create_or_update_conversation,
    save_message,
    get_conversation_history,
    get_conversation_mode
)
from app.services.asset_service import (
    get_all_catalog_items,
    find_local_asset_file,
    get_asset_mime_type,
    get_promo_image_path,
    validate_image_file,
    select_catalog_asset,
    get_catalog_item
)
from app.services.context_service import extract_context_from_history
from app.services.intent_service import analyze_intent
from app.services.handoff_service import should_handoff, generate_handoff_message
from app.services.trace_service import create_tracer
from app.services.cache_service import get_cache_stats
from app.rules.business_guardrails import is_business_related, get_off_topic_response
from app.rules.keywords import normalize_text, contains_any, PROMOCIONES, CONFIRMACIONES
from app.config import LUISA_API_KEY
from app.logging_config import logger


router = APIRouter(prefix="/api", tags=["api"])


@router.get("/catalog/items")
async def get_catalog_items():
    """Obtiene todos los items del catálogo."""
    items = get_all_catalog_items()
    return CatalogResponse(count=len(items), items=items)


@router.get("/assets/{image_id}")
async def get_asset(image_id: str):
    """Sirve un asset (imagen o video) del catálogo."""
    # Caso especial: promoción navideña
    if image_id == "promo_navidad":
        promo_path = get_promo_image_path()
        if promo_path and promo_path.exists():
            return FileResponse(
                promo_path,
                media_type="image/png",
                filename="promocion_navidad_2024.png"
            )
        raise HTTPException(status_code=404, detail="Promoción no encontrada")
    
    # Buscar archivo local
    asset_file = find_local_asset_file(image_id)
    
    if not asset_file or not asset_file.exists():
        raise HTTPException(status_code=404, detail=f"Asset {image_id} no encontrado")
    
    mime_type = get_asset_mime_type(asset_file)
    
    return FileResponse(
        asset_file,
        media_type=mime_type,
        filename=asset_file.name
    )


@router.get("/handoffs")
async def list_handoffs():
    """Obtiene todos los handoffs (para vista interna)."""
    handoffs = get_handoffs(limit=50)
    return handoffs


@router.get("/cache/stats")
async def cache_stats():
    """Obtiene estadísticas del cache."""
    return get_cache_stats()


@router.post("/catalog/sync")
async def sync_catalog_item(
    payload: CatalogSyncPayload,
    x_luisa_api_key: Optional[str] = Header(None)
):
    """
    Sincroniza un item del catálogo desde n8n.
    Requiere API key.
    """
    if x_luisa_api_key != LUISA_API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")
    
    # TODO: Implementar sincronización completa
    logger.info("Sync request recibido", image_id=payload.image_id)
    return {"status": "ok", "image_id": payload.image_id}


# ============================================================================
# NOTA: El endpoint /api/chat se maneja en el main.py legacy por ahora
# para mantener compatibilidad con toda la lógica existente de generate_response.
# Una vez que la migración esté completa, se puede mover aquí.
# ============================================================================
