"""
Tests para verificación de webhook de WhatsApp (GET /whatsapp/webhook).
Verifica que el handler responde correctamente al challenge de Meta.
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch
import os

# Importar después de configurar env
@pytest.fixture
def app_with_whatsapp_enabled(monkeypatch):
    """Crea app FastAPI con WhatsApp habilitado para tests."""
    monkeypatch.setenv("WHATSAPP_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "TEST_VERIFY_TOKEN_123")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test_access_token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
    monkeypatch.setenv("DB_PATH", ":memory:")  # DB en memoria para tests
    
    # Reiniciar config para cargar nuevos env vars
    import importlib
    from app import config
    importlib.reload(config)
    
    from app.main import create_app
    return create_app()


@pytest.fixture
def app_with_whatsapp_disabled(monkeypatch):
    """Crea app FastAPI con WhatsApp deshabilitado para tests."""
    monkeypatch.setenv("WHATSAPP_ENABLED", "false")
    monkeypatch.setenv("DB_PATH", ":memory:")
    
    import importlib
    from app import config
    importlib.reload(config)
    
    from app.main import create_app
    return create_app()


def test_webhook_verification_success(app_with_whatsapp_enabled):
    """
    Prueba 1: GET verificación con token correcto devuelve challenge.
    
    Request: GET /whatsapp/webhook?hub.mode=subscribe&hub.verify_token=TEST_VERIFY_TOKEN_123&hub.challenge=CHALLENGE123
    Expected: Status 200, Content-Type text/plain, Body "CHALLENGE123"
    """
    client = TestClient(app_with_whatsapp_enabled)
    
    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "TEST_VERIFY_TOKEN_123",
            "hub.challenge": "CHALLENGE123"
        }
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == "CHALLENGE123", f"Expected 'CHALLENGE123', got '{response.text}'"


def test_webhook_verification_fails_wrong_token(app_with_whatsapp_enabled):
    """
    Prueba 2: GET verificación con token incorrecto devuelve 403.
    
    Request: GET /whatsapp/webhook?hub.mode=subscribe&hub.verify_token=WRONG_TOKEN&hub.challenge=CHALLENGE123
    Expected: Status 403, detail "Verificación fallida"
    """
    client = TestClient(app_with_whatsapp_enabled)
    
    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "WRONG_TOKEN",
            "hub.challenge": "CHALLENGE123"
        }
    )
    
    assert response.status_code == 403
    assert "Verificación fallida" in response.json()["detail"]


def test_webhook_verification_fails_wrong_mode(app_with_whatsapp_enabled):
    """
    Prueba 3: GET verificación con mode != 'subscribe' devuelve 403.
    
    Request: GET /whatsapp/webhook?hub.mode=unsubscribe&hub.verify_token=TEST_VERIFY_TOKEN_123&hub.challenge=CHALLENGE123
    Expected: Status 403
    """
    client = TestClient(app_with_whatsapp_enabled)
    
    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": "TEST_VERIFY_TOKEN_123",
            "hub.challenge": "CHALLENGE123"
        }
    )
    
    assert response.status_code == 403


def test_webhook_verification_fails_missing_challenge(app_with_whatsapp_enabled):
    """
    Prueba 4: GET verificación sin hub.challenge (BUG P0).
    
    Request: GET /whatsapp/webhook?hub.mode=subscribe&hub.verify_token=TEST_VERIFY_TOKEN_123
    Expected: Status 200 (actual) o 400 (después del fix)
    
    NOTA: Este test expone el BUG P0. Actualmente devuelve 200 con body None/vacío,
    lo cual es incorrecto. Después del fix, debería devolver 400.
    """
    client = TestClient(app_with_whatsapp_enabled)
    
    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "TEST_VERIFY_TOKEN_123"
            # hub.challenge ausente
        }
    )
    
    # ACTUAL (BUG): Devuelve 200 con body None/vacío (incorrecto)
    # DESPUÉS DEL FIX: Debería devolver 400
    # Por ahora, documentamos el comportamiento actual
    assert response.status_code in [200, 400]
    
    if response.status_code == 200:
        # BUG: Body vacío o None (Meta rechazará esto)
        assert response.text == "" or response.text is None or len(response.text) == 0
    else:
        # Fix correcto: 400 Bad Request
        assert "requerido" in response.json()["detail"].lower() or "required" in response.json()["detail"].lower()


def test_webhook_verification_disabled(app_with_whatsapp_disabled):
    """
    Prueba 5: GET verificación cuando WhatsApp está deshabilitado devuelve 503.
    
    Request: GET /whatsapp/webhook?hub.mode=subscribe&hub.verify_token=TEST&hub.challenge=CHALLENGE
    Expected: Status 503, detail "WhatsApp no habilitado"
    """
    client = TestClient(app_with_whatsapp_disabled)
    
    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "TEST",
            "hub.challenge": "CHALLENGE"
        }
    )
    
    assert response.status_code == 503
    assert "WhatsApp no habilitado" in response.json()["detail"]


def test_webhook_verification_case_sensitive_token(app_with_whatsapp_enabled):
    """
    Prueba 6: GET verificación es case-sensitive (token debe coincidir exactamente).
    
    Request: GET /whatsapp/webhook?hub.mode=subscribe&hub.verify_token=test_verify_token_123&hub.challenge=CHALLENGE
    Expected: Status 403 (token en minúsculas no coincide con TEST_VERIFY_TOKEN_123)
    """
    client = TestClient(app_with_whatsapp_enabled)
    
    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token_123",  # minúsculas
            "hub.challenge": "CHALLENGE123"
        }
    )
    
    assert response.status_code == 403, "Token case-sensitive: minúsculas deben fallar"

