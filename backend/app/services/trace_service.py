"""
Servicio de trazabilidad para registrar todas las interacciones.
"""
import hashlib
import time
from typing import Optional
from dataclasses import dataclass, field
from contextlib import contextmanager

from app.models.database import save_trace
from app.logging_config import logger, generate_request_id


@dataclass
class InteractionTracer:
    """
    Rastreador de una interacción individual.
    Usado como context manager para medir latencia automáticamente.
    """
    request_id: str = field(default_factory=generate_request_id)
    conversation_id: str = ""
    channel: str = "api"
    customer_phone: Optional[str] = None
    raw_text: str = ""
    normalized_text: str = ""
    message_type: Optional[str] = None
    business_related: bool = True
    intent: Optional[str] = None
    routed_team: Optional[str] = None
    selected_asset_id: Optional[str] = None
    openai_called: bool = False
    prompt_version: Optional[str] = None
    cache_hit: bool = False
    response_text: str = ""
    decision_path: Optional[str] = None
    response_len_chars: int = field(default=0)
    error_message: Optional[str] = None
    whatsapp_send_success: Optional[int] = None
    whatsapp_send_latency_ms: Optional[float] = None
    whatsapp_send_error_code: Optional[str] = None
    classification: Optional[str] = None
    is_personal: Optional[int] = None
    classification_score: Optional[float] = None
    classification_reasons: Optional[str] = None
    classifier_version: Optional[str] = None
    openai_canary_allowed: Optional[int] = None
    openai_latency_ms: Optional[float] = None
    openai_error: Optional[str] = None
    openai_fallback_used: Optional[int] = None
    
    _start_time: float = field(default=0.0, repr=False)
    _latency_ms: float = field(default=0.0, repr=False)
    _latency_us: int = field(default=0, repr=False)
    
    def start(self) -> "InteractionTracer":
        """Inicia el timer con perf_counter para mayor precisión."""
        import time
        self._start_time = time.perf_counter()
        return self
    
    def stop(self) -> float:
        """Detiene el timer y retorna latencia en ms con 1 decimal."""
        import time
        if self._start_time > 0:
            elapsed_seconds = time.perf_counter() - self._start_time
            self._latency_us = int(elapsed_seconds * 1_000_000)  # Microsegundos
            self._latency_ms = round(elapsed_seconds * 1000, 1)  # Milisegundos con 1 decimal
        return self._latency_ms
    
    @property
    def latency_ms(self) -> float:
        """Retorna la latencia medida en ms con 1 decimal."""
        return self._latency_ms
    
    @property
    def latency_us(self) -> int:
        """Retorna la latencia medida en microsegundos."""
        return self._latency_us
    
    def _hash_phone(self) -> Optional[str]:
        """Genera un hash parcial del teléfono para privacidad."""
        if not self.customer_phone:
            return None
        # Guardar solo últimos 4 dígitos + hash
        phone_clean = self.customer_phone.replace("+", "").replace(" ", "")
        if len(phone_clean) >= 4:
            last_4 = phone_clean[-4:]
            hash_prefix = hashlib.sha256(phone_clean.encode()).hexdigest()[:8]
            return f"{hash_prefix}...{last_4}"
        return None
    
    def save(self) -> None:
        """Guarda la traza en la base de datos."""
        # Asegurar que el timer está detenido
        if self._latency_ms == 0.0:
            self.stop()

        try:
            save_trace(
                request_id=self.request_id,
                conversation_id=self.conversation_id,
                channel=self.channel,
                customer_phone_hash=self._hash_phone(),
                raw_text=self.raw_text,
                normalized_text=self.normalized_text,
                message_type=self.message_type,
                business_related=self.business_related,
                intent=self.intent,
                routed_team=self.routed_team,
                selected_asset_id=self.selected_asset_id,
                openai_called=self.openai_called,
                prompt_version=self.prompt_version,
                cache_hit=self.cache_hit,
                response_text=self.response_text[:500] if self.response_text else "",  # Limitar tamaño
                latency_ms=self._latency_ms,
                latency_us=self._latency_us,
                decision_path=self.decision_path,
                response_len_chars=self.response_len_chars,
                error_message=self.error_message,
                whatsapp_send_success=self.whatsapp_send_success,
                whatsapp_send_latency_ms=self.whatsapp_send_latency_ms,
                whatsapp_send_error_code=self.whatsapp_send_error_code,
                classification=self.classification,
                is_personal=self.is_personal,
                classification_score=self.classification_score,
                classification_reasons=self.classification_reasons,
                classifier_version=self.classifier_version,
                openai_canary_allowed=self.openai_canary_allowed,
                openai_latency_ms=self.openai_latency_ms,
                openai_error=self.openai_error,
                openai_fallback_used=self.openai_fallback_used
            )
        except Exception as e:
            # No fallar por errores de trazabilidad
            logger.error("Error guardando traza", error=str(e), request_id=self.request_id)
    
    def log(self) -> None:
        """Registra la interacción en los logs estructurados."""
        logger.interaction(
            request_id=self.request_id,
            conversation_id=self.conversation_id,
            channel=self.channel,
            business_related=self.business_related,
            intent=self.intent,
            routed_team=self.routed_team,
            asset_id=self.selected_asset_id,
            mode="AI_ACTIVE",  # TODO: obtener del contexto
            openai_called=self.openai_called,
            cache_hit=self.cache_hit,
            latency_ms=self._latency_ms,
            latency_us=self._latency_us,
            error_message=self.error_message
        )


@contextmanager
def trace_interaction(conversation_id: str, channel: str = "api", customer_phone: Optional[str] = None):
    """
    Context manager para rastrear una interacción.
    
    Uso:
        with trace_interaction("conv_123", "whatsapp") as tracer:
            tracer.raw_text = message
            # ... procesar ...
            tracer.response_text = response
    """
    tracer = InteractionTracer(
        conversation_id=conversation_id,
        channel=channel,
        customer_phone=customer_phone
    )
    tracer.start()
    
    try:
        yield tracer
    except Exception as e:
        tracer.error_message = str(e)
        raise
    finally:
        # Detener timer, loguear y guardar (todo incluido en la medición)
        tracer.stop()
        tracer.log()
        tracer.save()


def create_tracer(conversation_id: str, channel: str = "api", customer_phone: Optional[str] = None) -> InteractionTracer:
    """
    Crea un tracer para uso manual (sin context manager).
    
    Uso:
        tracer = create_tracer("conv_123")
        tracer.start()
        # ... procesar ...
        tracer.stop()
        tracer.save()
    """
    return InteractionTracer(
        conversation_id=conversation_id,
        channel=channel,
        customer_phone=customer_phone
    )
