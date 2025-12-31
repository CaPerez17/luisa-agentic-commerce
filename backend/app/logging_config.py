"""
Configuración de logging estructurado para LUISA.
Soporta formato JSON para producción y texto para desarrollo.
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from app.config import LOG_LEVEL, LOG_FORMAT


class StructuredLogger:
    """Logger que produce output estructurado JSON o texto."""
    
    def __init__(self, name: str = "luisa"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
        
        # Evitar duplicación de handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
            
            if LOG_FORMAT == "json":
                handler.setFormatter(JsonFormatter())
            else:
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
            
            self.logger.addHandler(handler)
    
    def _format_extra(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Formatea datos extra para el log."""
        base = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "luisa"
        }
        if extra:
            base.update(extra)
        return base

    def info(self, message: str, **kwargs):
        """Log nivel INFO con datos estructurados."""
        extra = self._format_extra(kwargs)
        if LOG_FORMAT == "json":
            self.logger.info(json.dumps({"level": "INFO", "message": message, **extra}))
        else:
            self.logger.info(f"{message} | {extra}")
    
    def warning(self, message: str, **kwargs):
        """Log nivel WARNING con datos estructurados."""
        extra = self._format_extra(kwargs)
        if LOG_FORMAT == "json":
            self.logger.warning(json.dumps({"level": "WARNING", "message": message, **extra}))
        else:
            self.logger.warning(f"{message} | {extra}")
    
    def error(self, message: str, **kwargs):
        """Log nivel ERROR con datos estructurados."""
        extra = self._format_extra(kwargs)
        if LOG_FORMAT == "json":
            self.logger.error(json.dumps({"level": "ERROR", "message": message, **extra}))
        else:
            self.logger.error(f"{message} | {extra}")
    
    def debug(self, message: str, **kwargs):
        """Log nivel DEBUG con datos estructurados."""
        extra = self._format_extra(kwargs)
        if LOG_FORMAT == "json":
            self.logger.debug(json.dumps({"level": "DEBUG", "message": message, **extra}))
        else:
            self.logger.debug(f"{message} | {extra}")
    
    def interaction(
        self,
        request_id: str,
        conversation_id: str,
        channel: str,
        business_related: bool,
        intent: Optional[str],
        routed_team: Optional[str],
        asset_id: Optional[str],
        mode: str,
        openai_called: bool,
        cache_hit: bool,
        latency_ms: float,
        latency_us: int,
        error: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Log específico para interacciones conversacionales."""
        data = {
            "type": "interaction",
            "request_id": request_id,
            "conversation_id": conversation_id,
            "channel": channel,
            "business_related": business_related,
            "intent": intent,
            "routed_team": routed_team,
            "asset_id": asset_id,
            "mode": mode,
            "openai_called": openai_called,
            "cache_hit": cache_hit,
            "latency_ms": latency_ms,
            "latency_us": latency_us
        }
        if error:
            data["error"] = error
        if error_message:
            data["error_message"] = error_message
        
        if LOG_FORMAT == "json":
            self.logger.info(json.dumps(data))
        else:
            self.logger.info(f"INTERACTION | {data}")


class JsonFormatter(logging.Formatter):
    """Formatter que produce JSON."""
    
    def format(self, record):
        # Si el mensaje ya es JSON, retornarlo directamente
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, TypeError):
            return json.dumps({
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name
            })


def generate_request_id() -> str:
    """Genera un ID único para cada request."""
    return str(uuid.uuid4())[:8]


# Instancia global del logger
logger = StructuredLogger()
