"""
SalesBrain v1: Orquestador DECIDE → PLAN → SPEAK.
Convierte LUISA en asesor comercial inteligente usando OpenAI estratégicamente.
"""
import hashlib
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from app.config import (
    SALESBRAIN_ENABLED,
    SALESBRAIN_PLANNER_ENABLED,
    SALESBRAIN_CLASSIFIER_ENABLED,
    SALESBRAIN_MAX_CALLS_PER_CONVERSATION,
    SALESBRAIN_CACHE_TTL_SECONDS
)
from app.services.triage_service import classify_triage_intent
from app.services.openai_classifier import classify_ambiguous_message
from app.services.openai_planner import plan_sales_conversation
from app.services.humanizer import humanize_response_sync
from app.services.sales_playbook import craft_reply, pick_one_question, handle_objection
from app.logging_config import logger


# Cache simple in-memory para evitar llamadas repetidas
_salesbrain_cache: Dict[str, Tuple[Any, float]] = {}


def _get_cache_key(phone_from: str, last_messages: List[str]) -> str:
    """Genera clave de cache basada en phone + hash de últimos 2 mensajes."""
    messages_str = "|".join(last_messages[-2:])
    messages_hash = hashlib.md5(messages_str.encode()).hexdigest()[:8]
    return f"sb:{phone_from}:{messages_hash}"


def _get_cached(key: str) -> Optional[Any]:
    """Obtiene valor del cache si no expiró."""
    if key not in _salesbrain_cache:
        return None
    
    value, timestamp = _salesbrain_cache[key]
    if time.time() - timestamp > SALESBRAIN_CACHE_TTL_SECONDS:
        del _salesbrain_cache[key]
        return None
    
    return value


def _set_cached(key: str, value: Any) -> None:
    """Guarda valor en cache."""
    _salesbrain_cache[key] = (value, time.time())


def _count_openai_calls(state: dict) -> int:
    """Cuenta llamadas a OpenAI en esta conversación."""
    return state.get("openai_calls_count", 0)


def _increment_openai_calls(state: dict) -> dict:
    """Incrementa contador de llamadas OpenAI."""
    state["openai_calls_count"] = state.get("openai_calls_count", 0) + 1
    state["last_openai_call_at"] = datetime.utcnow().isoformat()
    return state


def should_use_salesbrain(
    text: str,
    intent: str,
    state: dict,
    is_ambiguous: bool
) -> Tuple[bool, str]:
    """
    Decide si usar SalesBrain (OpenAI).
    
    Returns:
        Tuple[should_use, reason]
    """
    if not SALESBRAIN_ENABLED:
        return False, "salesbrain_disabled"
    
    # Verificar límite de llamadas
    if _count_openai_calls(state) >= SALESBRAIN_MAX_CALLS_PER_CONVERSATION:
        return False, "max_calls_reached"
    
    text_lower = text.lower()
    
    # Casos donde OpenAI aporta valor
    if is_ambiguous:
        return True, "ambiguous_message"
    
    if any(kw in text_lower for kw in ["no sé", "no se", "cual", "cuál", "recomiéndame", "recomiendame", "indeciso"]):
        return True, "user_indecisive"
    
    if any(kw in text_lower for kw in ["muy caro", "caro", "costoso", "no tengo", "no alcanza", "otro lado", "más barato"]):
        return True, "objection_price"
    
    if any(kw in text_lower for kw in ["solo averiguando", "solo estoy viendo", "información", "informacion"]):
        return True, "objection_browsing"
    
    if intent == "tech_support" and any(kw in text_lower for kw in ["se revienta", "ruido", "no prende", "falla", "problema"]):
        return True, "tech_support_complex"
    
    return False, "rules_sufficient"


def decide_intent(
    text: str,
    state: dict,
    history: List[Dict[str, Any]]
) -> Tuple[str, float, bool, Optional[Any]]:
    """
    DECIDE: Determina intent base (determinístico primero, OpenAI si ambiguo).
    
    Returns:
        Tuple[intent, confidence, is_ambiguous, classifier_output]
    """
    # Intentar reglas determinísticas primero
    triage_intent, triage_confidence, is_ambiguous = classify_triage_intent(text)
    
    # Si no es ambiguo y confianza alta, usar reglas
    if not is_ambiguous and triage_confidence >= 0.5:
        return triage_intent, triage_confidence, False, None
    
    # Si es ambiguo y classifier está habilitado, usar OpenAI
    if is_ambiguous and SALESBRAIN_CLASSIFIER_ENABLED:
        classifier_output = classify_ambiguous_message(text, history)
        if classifier_output:
            return classifier_output.intent, classifier_output.confidence, classifier_output.is_ambiguous, classifier_output
    
    # Fallback a triage
    return triage_intent, triage_confidence, is_ambiguous, None


def plan_conversation(
    text: str,
    intent: str,
    state: dict,
    history: List[Dict[str, Any]],
    should_use: bool,
    reason: str
) -> Optional[Any]:
    """
    PLAN: Genera plan de venta estructurado (OpenAI si aporta valor).
    
    Returns:
        PlannerOutput o None
    """
    if not should_use or not SALESBRAIN_PLANNER_ENABLED:
        return None
    
    # Verificar cache
    phone_from = state.get("phone_from", "unknown")
    last_messages = [m.get("text", "") for m in history[-2:]] if history else [text]
    cache_key = _get_cache_key(phone_from, last_messages)
    cached = _get_cached(cache_key)
    if cached:
        logger.info("SalesBrain cache hit", reason=reason)
        return cached
    
    # Llamar planner
    planner_output = plan_sales_conversation(text, intent, state, history)
    
    if planner_output:
        _set_cached(cache_key, planner_output)
        state = _increment_openai_calls(state)
    
    return planner_output


def speak_final(
    planner_output: Optional[Any],
    playbook_result: Optional[Dict[str, Any]],
    state: dict
) -> Dict[str, Any]:
    """
    SPEAK: Genera respuesta final (playbook + planner + humanizer).
    
    Returns:
        {
            "reply_text": str,
            "reply_assets": List[dict] o None,
            "state_updates": dict,
            "decision_path": str
        }
    """
    # Si hay planner output, usarlo como base
    if planner_output:
        reply_base = planner_output.recommended_reply_base
        next_question = planner_output.next_best_question
        
        # Construir respuesta final
        if next_question:
            reply_text = f"{reply_base}\n\n{next_question}"
        else:
            reply_text = reply_base
        
        # Actualizar slots del planner (solo si confidence alto)
        slot_updates = {}
        if planner_output.confidence >= 0.7:
            slot_updates = planner_output.slots
        
        # Humanizer (sales polish)
        if state.get("humanize_enabled", False):
            humanized, humanize_meta = humanize_response_sync(reply_text, state)
            if humanize_meta.get("humanized"):
                reply_text = humanized
        
        return {
            "reply_text": reply_text,
            "reply_assets": None,
            "state_updates": {
                "stage": state.get("stage", "discovery"),
                **slot_updates,
                "last_question": next_question if next_question else None
            },
            "decision_path": f"salesbrain_planner->humanized" if state.get("humanize_enabled") else "salesbrain_planner"
        }
    
    # Si no hay planner, usar playbook
    if playbook_result:
        reply_text = playbook_result.get("reply_text", "")
        
        # Humanizer opcional
        if state.get("humanize_enabled", False):
            humanized, humanize_meta = humanize_response_sync(reply_text, state)
            if humanize_meta.get("humanized"):
                reply_text = humanized
        
        return {
            "reply_text": reply_text,
            "reply_assets": playbook_result.get("reply_assets"),
            "state_updates": {
                "stage": playbook_result.get("stage_update", state.get("stage")),
                **playbook_result.get("slot_updates", {})
            },
            "decision_path": "playbook->humanized" if state.get("humanize_enabled") else "playbook"
        }
    
    # Fallback
    return {
        "reply_text": "¿Buscas máquina familiar (para casa) o industrial (para producción)?",
        "reply_assets": None,
        "state_updates": {"stage": "discovery"},
        "decision_path": "fallback"
    }


def process_with_salesbrain(
    text: str,
    state: dict,
    history: List[Dict[str, Any]],
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Procesa mensaje con SalesBrain (DECIDE → PLAN → SPEAK).
    
    Returns:
        {
            "reply_text": str,
            "reply_assets": List[dict] o None,
            "state_updates": dict,
            "decision_path": str
        }
    """
    if not SALESBRAIN_ENABLED:
        # Fallback a playbook normal
        playbook_result = craft_reply("buy_machine", state, text, context)
        return speak_final(None, playbook_result, state)
    
    # DECIDE: Determinar intent
    intent, confidence, is_ambiguous, classifier_output = decide_intent(text, state, history)
    
    # Verificar si debe usar OpenAI
    should_use, reason = should_use_salesbrain(text, intent, state, is_ambiguous)
    
    # Verificar objeciones primero (playbook)
    objection_response = handle_objection(text.lower(), state)
    if objection_response:
        return speak_final(None, objection_response, state)
    
    # PLAN: Generar plan de venta
    planner_output = plan_conversation(text, intent, state, history, should_use, reason)
    
    # Si no hay planner, usar playbook
    playbook_result = None
    if not planner_output:
        playbook_result = craft_reply(intent, state, text, context)
    
    # SPEAK: Generar respuesta final
    result = speak_final(planner_output, playbook_result, state)
    
    # Agregar metadata de trazabilidad
    result["decision_path"] = f"{result.get('decision_path', 'unknown')}->openai_called={should_use}->reason={reason}"
    
    return result

