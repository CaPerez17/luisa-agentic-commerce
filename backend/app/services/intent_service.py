"""
Servicio de análisis de intención.
Wrapper sobre intent_analyzer.py existente para mantener compatibilidad.
"""
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Agregar backend/ al path para importar intent_analyzer
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from intent_analyzer import intent_analyzer as legacy_analyzer, IntentType
    LEGACY_AVAILABLE = True
except ImportError:
    LEGACY_AVAILABLE = False
    legacy_analyzer = None
    IntentType = None

from app.rules.keywords import (
    normalize_text,
    contains_any,
    CONFIRMACIONES,
    NEGACIONES,
    SALUDOS,
    DESPEDIDAS,
    PRECIO,
    DISPONIBILIDAD,
    COMPRAR,
    FOTOS,
    PROMOCIONES,
    MAQUINA_FAMILIAR,
    MAQUINA_INDUSTRIAL,
    FILETEADORA,
    REPUESTOS,
    REPARACION,
    INSTALACION,
    ENVIO,
    FORMAS_PAGO
)
from app.logging_config import logger


class IntentService:
    """
    Servicio de análisis de intención que usa el analizador legacy
    y extiende con capacidades adicionales.
    """
    
    def __init__(self):
        self.use_legacy = LEGACY_AVAILABLE
        if not self.use_legacy:
            logger.warning("intent_analyzer legacy no disponible, usando fallback")
    
    def analyze(
        self,
        text: str,
        conversation_history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analiza el mensaje y determina la intención primaria.
        
        Returns:
            Dict con intent, confidence, context, requires_asset, requires_handoff, etc.
        """
        text_lower = normalize_text(text)
        conversation_history = conversation_history or []
        
        # Intentar usar el analizador legacy
        if self.use_legacy and legacy_analyzer:
            try:
                result = legacy_analyzer.analyze(text, conversation_history)
                return {
                    "intent": result["intent"].value if hasattr(result["intent"], "value") else str(result["intent"]),
                    "confidence": result.get("confidence", 0.5),
                    "context": result.get("context", {}),
                    "requires_asset": result.get("requires_asset", False),
                    "requires_handoff": result.get("requires_handoff", False),
                    "is_confirmation": result.get("is_confirmation", False),
                    "is_negation": result.get("is_negation", False),
                    "last_luisa_topic": result.get("last_luisa_topic")
                }
            except Exception as e:
                logger.error("Error en intent_analyzer legacy", error=str(e))
        
        # Fallback: análisis básico
        return self._analyze_fallback(text_lower, conversation_history)
    
    def _analyze_fallback(
        self,
        text_lower: str,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Análisis de intención básico como fallback."""
        
        result = {
            "intent": "indefinido",
            "confidence": 0.3,
            "context": {},
            "requires_asset": False,
            "requires_handoff": False,
            "is_confirmation": False,
            "is_negation": False,
            "last_luisa_topic": None
        }
        
        # Detectar confirmación/negación
        words = text_lower.split()
        if len(words) <= 3:
            if contains_any(text_lower, CONFIRMACIONES):
                result["is_confirmation"] = True
                result["intent"] = "confirmar"
                result["confidence"] = 0.7
            elif contains_any(text_lower, NEGACIONES):
                result["is_negation"] = True
                result["intent"] = "negar"
                result["confidence"] = 0.7
        
        # Detectar intención principal
        intent_map = [
            (SALUDOS, "saludo", False, False),
            (DESPEDIDAS, "despedida", False, False),
            (PRECIO, "preguntar_precio", False, True),
            (DISPONIBILIDAD, "preguntar_disponibilidad", False, True),
            (COMPRAR, "confirmar_compra", False, True),
            (FOTOS, "solicitar_fotos", True, False),
            (PROMOCIONES, "preguntar_promociones", True, False),
            (MAQUINA_FAMILIAR, "buscar_maquina_familiar", True, False),
            (MAQUINA_INDUSTRIAL, "buscar_maquina_industrial", True, False),
            (FILETEADORA, "buscar_fileteadora", True, False),
            (REPUESTOS, "buscar_repuestos", False, False),
            (REPARACION, "solicitar_servicio", False, True),
            (INSTALACION, "solicitar_instalacion", False, True),
            (ENVIO, "solicitar_envio", False, True),
            (FORMAS_PAGO, "preguntar_forma_pago", False, True)
        ]
        
        for keywords, intent, requires_asset, requires_handoff in intent_map:
            if contains_any(text_lower, keywords):
                result["intent"] = intent
                result["requires_asset"] = requires_asset
                result["requires_handoff"] = requires_handoff
                result["confidence"] = 0.6
                break
        
        # Detectar último tema de Luisa
        if history:
            luisa_msgs = [m for m in history if m.get("sender") == "luisa"]
            if luisa_msgs:
                last_luisa = luisa_msgs[-1].get("text", "").lower()
                if contains_any(last_luisa, PROMOCIONES):
                    result["last_luisa_topic"] = "promocion"
                    if result["is_confirmation"]:
                        result["requires_asset"] = True
        
        return result
    
    def get_intent_type(self, intent_str: str):
        """Obtiene el IntentType del analizador legacy si está disponible."""
        if self.use_legacy and IntentType:
            try:
                return IntentType(intent_str)
            except:
                return None
        return None


# Instancia global
intent_service = IntentService()


def analyze_intent(text: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Función de conveniencia para analizar intención."""
    return intent_service.analyze(text, history)

