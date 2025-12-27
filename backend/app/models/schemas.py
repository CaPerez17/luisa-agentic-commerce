"""
Schemas Pydantic para validación de datos.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ConversationMode(str, Enum):
    """Modos de conversación para modo sombra."""
    AI_ACTIVE = "AI_ACTIVE"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"


class Channel(str, Enum):
    """Canales de comunicación."""
    API = "api"
    WHATSAPP = "whatsapp"


class Team(str, Enum):
    """Equipos de destino para handoff."""
    COMERCIAL = "comercial"
    TECNICA = "tecnica"


class Priority(str, Enum):
    """Niveles de prioridad."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class ChatMessage(BaseModel):
    """Mensaje de chat entrante."""
    conversation_id: str
    text: str
    sender: str = "customer"


class WhatsAppWebhookVerify(BaseModel):
    """Verificación de webhook de WhatsApp."""
    hub_mode: Optional[str] = Field(None, alias="hub.mode")
    hub_verify_token: Optional[str] = Field(None, alias="hub.verify_token")
    hub_challenge: Optional[str] = Field(None, alias="hub.challenge")


class CatalogSyncPayload(BaseModel):
    """Payload para sincronización de catálogo desde n8n."""
    image_id: str
    meta: Dict[str, Any]
    asset: Optional[Dict[str, Any]] = None


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class AssetInfo(BaseModel):
    """Información de asset para respuesta."""
    image_id: str
    asset_url: str
    type: str = "image"


class ChatResponse(BaseModel):
    """Respuesta de chat."""
    response: str
    sender: str = "luisa"
    needs_escalation: bool = False
    asset: Optional[AssetInfo] = None


class CatalogItem(BaseModel):
    """Item del catálogo."""
    image_id: str
    slug: Optional[str] = None
    path: Optional[str] = None
    category: str
    brand: str
    model: str
    represents: str
    conversation_role: str
    priority: int
    send_when_customer_says: List[str] = []
    asset_url: Optional[str] = None


class CatalogResponse(BaseModel):
    """Respuesta de listado de catálogo."""
    count: int
    items: List[CatalogItem]


class HandoffResponse(BaseModel):
    """Respuesta de handoff."""
    conversation_id: str
    reason: str
    priority: str
    summary: str
    suggested_response: str
    customer_name: Optional[str] = None
    routed_team: Optional[str] = None
    timestamp: str


# ============================================================================
# INTERNAL SCHEMAS (para servicios)
# ============================================================================

class ConversationContext(BaseModel):
    """Contexto extraído de la conversación."""
    tipo_maquina: Optional[str] = None
    uso: Optional[str] = None
    volumen: Optional[str] = None
    ciudad: Optional[str] = None
    presupuesto: Optional[bool] = None
    marca_interes: Optional[str] = None
    modelo_interes: Optional[str] = None
    ultimo_tema: Optional[str] = None
    esperando_confirmacion: bool = False
    etapa_funnel: str = "exploracion"
    productos_mencionados: List[str] = []
    preguntas_respondidas: List[str] = []


class IntentResult(BaseModel):
    """Resultado del análisis de intención."""
    intent: str
    confidence: float
    context: Dict[str, Any] = {}
    requires_asset: bool = False
    requires_handoff: bool = False
    is_confirmation: bool = False
    is_negation: bool = False
    last_luisa_topic: Optional[str] = None


class HandoffDecision(BaseModel):
    """Decisión de handoff."""
    should_handoff: bool
    team: Optional[Team] = None
    reason: str = ""
    priority: Priority = Priority.LOW


class InternalNotification(BaseModel):
    """Notificación interna para humanos."""
    team: Team
    customer_name: Optional[str] = None
    customer_phone: str
    motivo: str
    resumen_bullets: List[str]
    siguiente_paso: str


class InteractionTrace(BaseModel):
    """Traza de una interacción."""
    request_id: str
    conversation_id: str
    channel: Channel
    customer_phone_hash: Optional[str] = None
    raw_text: str
    normalized_text: str
    business_related: bool
    intent: Optional[str] = None
    routed_team: Optional[str] = None
    selected_asset_id: Optional[str] = None
    openai_called: bool = False
    prompt_version: Optional[str] = None
    cache_hit: bool = False
    response_text: str
    latency_ms: int
    error: Optional[str] = None
