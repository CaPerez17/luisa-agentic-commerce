"""
Rate limiting simple en memoria (por clave y ventana de 60s).
No requiere Redis; adecuado para entornos single-instance.
"""
import time
from typing import Dict, Tuple

# key -> (window_start_epoch, count)
_WINDOWS: Dict[str, Tuple[float, int]] = {}
WINDOW_SECONDS = 60.0


def allow(key: str, limit_per_minute: int) -> bool:
    """
    Retorna True si la solicitud está permitida.
    Reinicia la ventana cada 60 segundos.
    """
    now = time.monotonic()
    window_start, count = _WINDOWS.get(key, (now, 0))

    # Si la ventana expiró, reiniciar
    if now - window_start >= WINDOW_SECONDS:
        window_start, count = now, 0

    count += 1
    _WINDOWS[key] = (window_start, count)

    return count <= limit_per_minute


def remaining(key: str, limit_per_minute: int) -> int:
    """Devuelve el número de requests restantes en la ventana actual."""
    now = time.monotonic()
    window_start, count = _WINDOWS.get(key, (now, 0))
    if now - window_start >= WINDOW_SECONDS:
        return limit_per_minute
    return max(0, limit_per_minute - count)

