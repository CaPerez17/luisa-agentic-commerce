"""
Tests básicos para el rate limiter in-memory.
"""
import time

from app.services import rate_limit
from app.services.rate_limit import allow, remaining, WINDOW_SECONDS


def test_rate_limit_allows_within_limit():
    key = "test:rl:ok"
    # Reset state by advancing window
    allow(key, limit_per_minute=1)  # consume one
    time.sleep(0.01)
    assert allow(key, limit_per_minute=5)  # nueva ventana o aún bajo límite


def test_rate_limit_blocks_after_limit():
    key = "test:rl:block"
    limit = 2
    assert allow(key, limit) is True
    assert allow(key, limit) is True
    assert allow(key, limit) is False  # tercera llamada bloqueada


def test_rate_limit_resets_after_window():
    key = "test:rl:reset"
    limit = 1
    assert allow(key, limit) is True
    assert allow(key, limit) is False
    # Forzar ventana expirada manipulando el timestamp interno
    rate_limit._WINDOWS[key] = (time.monotonic() - WINDOW_SECONDS - 1, 0)
    assert allow(key, limit) is True  # después de la ventana permite de nuevo
    assert remaining(key, limit) >= 0

