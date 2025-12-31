"""
Humanizer: re-escribe respuestas base para hacerlas más humanas y comerciales.
Usa OpenAI solo para reescritura, no para decisiones.
"""
import time
import httpx
from typing import Optional, Tuple
import json

from app.config import (
    OPENAI_ENABLED,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS
)
from app.logging_config import logger


# Configuración del humanizer
HUMANIZE_ENABLED = False  # Se activa con env var
HUMANIZE_MODEL = "gpt-4o-mini"  # Modelo barato
HUMANIZE_MAX_TOKENS = 120
HUMANIZE_TEMPERATURE = 0.4
HUMANIZE_TIMEOUT = 8


def humanize_response(base_reply: str, context: dict = None) -> Tuple[str, dict]:
    """
    Humaniza una respuesta base usando OpenAI (opcional).
    
    Args:
        base_reply: Respuesta base generada por reglas
        context: Contexto opcional (slots, stage, etc.)
    
    Returns:
        Tuple[respuesta_humanizada, metadata]
        metadata incluye: humanized, openai_called, elapsed_ms, error
    """
    metadata = {
        "humanized": False,
        "openai_called": False,
        "elapsed_ms": 0,
        "error": None
    }
    
    # Verificar si está habilitado
    try:
        import os
        humanize_enabled = os.getenv("HUMANIZE_ENABLED", "false").lower() == "true"
    except:
        humanize_enabled = False
    
    if not humanize_enabled or not OPENAI_ENABLED or not OPENAI_API_KEY:
        return base_reply, metadata
    
    start_time = time.perf_counter()
    
    # Prompt de reescritura
    system_prompt = """Eres Luisa, vendedora de Almacén y Taller El Sastre en Montería, Colombia.

REGLAS ESTRICTAS:
1. NO inventes precios ni promociones
2. NO cambies dirección ni horarios
3. Máximo 2-3 líneas
4. 1 emoji máximo
5. 1 pregunta máxima
6. Español colombiano natural y cálido
7. Tono vendedor pero no agresivo
8. Mantén datos exactos (precios, direcciones, horarios)

Solo reescribe para hacerlo más humano y comercial, sin cambiar información."""

    user_prompt = f"Reescribe esta respuesta de forma más humana y comercial:\n\n{base_reply}"
    
    # Regla especial para triage: NO cambiar números/opciones
    is_triage = "1)" in base_reply and "2)" in base_reply
    if is_triage:
        user_prompt += "\n\nIMPORTANTE: Mantén las opciones numeradas (1), 2), 3), 4)) exactamente como están. Solo mejora el tono."

    try:
        # Llamada síncrona con httpx
        with httpx.Client(timeout=HUMANIZE_TIMEOUT) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": HUMANIZE_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": HUMANIZE_MAX_TOKENS,
                    "temperature": HUMANIZE_TEMPERATURE
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                humanized = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Error desconocido")
                logger.warning("Error en humanizer OpenAI", status_code=response.status_code, error=error_msg)
                humanized = None
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metadata["elapsed_ms"] = round(elapsed_ms, 1)
        
        if humanized and len(humanized) > 10:  # Validar que no sea vacío
            metadata["humanized"] = True
            metadata["openai_called"] = True
            logger.info(
                "Respuesta humanizada",
                original_len=len(base_reply),
                humanized_len=len(humanized),
                elapsed_ms=round(elapsed_ms, 1)
            )
            return humanized, metadata
        else:
            metadata["error"] = "Respuesta vacía o inválida"
            return base_reply, metadata
            
    except httpx.TimeoutException:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metadata["elapsed_ms"] = round(elapsed_ms, 1)
        metadata["error"] = "Timeout"
        logger.warning("Timeout en humanizer", elapsed_ms=round(elapsed_ms, 1))
        return base_reply, metadata
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metadata["elapsed_ms"] = round(elapsed_ms, 1)
        metadata["error"] = str(e)
        logger.error("Error en humanizer", error=str(e))
        return base_reply, metadata


def humanize_response_sync(base_reply: str, context: dict = None) -> Tuple[str, dict]:
    """
    Versión síncrona del humanizer (para compatibilidad).
    """
    return humanize_response(base_reply, context)

