"""
Configuración de pytest para tests de LUISA.
"""
import pytest
import sys
import os
from pathlib import Path

# Agregar directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Configurar variables de entorno para tests
os.environ.setdefault("OPENAI_ENABLED", "false")
os.environ.setdefault("WHATSAPP_ENABLED", "false")
os.environ.setdefault("CACHE_ENABLED", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "text")


@pytest.fixture(scope="session")
def backend_dir():
    """Retorna el directorio del backend."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def assets_dir(backend_dir):
    """Retorna el directorio de assets."""
    return backend_dir / "assets"


@pytest.fixture
def test_conversation_id():
    """Genera un ID de conversación único para tests."""
    import uuid
    return f"test_{uuid.uuid4().hex[:8]}"

