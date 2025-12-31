"""
Schemas Pydantic para SalesBrain.
Estructuras de datos para OpenAI planner y classifier.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    """Recomendación de producto."""
    name: str = Field(..., description="Nombre del producto")
    why: str = Field(..., description="Por qué recomendar este producto")
    price: Optional[int] = Field(None, description="Precio (solo si está en facts)")
    conditions: Optional[str] = Field(None, description="Condiciones o incluye")


class PlannerOutput(BaseModel):
    """Salida del planner de OpenAI."""
    intent: str = Field(..., description="Intent detectado")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confianza 0-1")
    slots: Dict[str, Any] = Field(default_factory=dict, description="Slots extraídos")
    user_goal: str = Field(..., description="Objetivo del usuario (corto)")
    assistant_goal: str = Field(..., description="Objetivo del asistente (cierre deseado)")
    next_best_question: Optional[str] = Field(None, description="UNA pregunta o null")
    recommended_reply_base: str = Field(..., description="Respuesta base segura SIN inventar facts")
    recommendations: List[Recommendation] = Field(default_factory=list, description="Recomendaciones de productos")
    should_offer_visit: bool = Field(default=False, description="Ofrecer visita")
    should_offer_shipping: bool = Field(default=False, description="Ofrecer envío")
    handoff_needed: bool = Field(default=False, description="Requiere escalamiento humano")
    handoff_reason: Optional[str] = Field(None, description="Razón del handoff")


class ClassifierOutput(BaseModel):
    """Salida del classifier de OpenAI."""
    intent: str = Field(..., description="Intent clasificado")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confianza 0-1")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Entidades extraídas")
    is_ambiguous: bool = Field(default=False, description="Mensaje ambiguo")
    needs_clarification: bool = Field(default=False, description="Necesita aclaración")

