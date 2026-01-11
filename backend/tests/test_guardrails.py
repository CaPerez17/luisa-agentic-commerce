"""
Tests para guardrails de negocio.
Verifica que preguntas fuera del negocio no llamen OpenAI.
"""
import pytest
import sys
from pathlib import Path

# Agregar backend/ al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rules.business_guardrails import (
    is_business_related,
    get_off_topic_response,
    is_cacheable_query,
    is_sensitive_query
)


class TestIsBusinessRelated:
    """Tests para la función is_business_related."""
    
    def test_mensaje_vacio(self):
        """Mensaje vacío se considera del negocio (no bloquear)."""
        result, _ = is_business_related("")
        assert result is True
    
    def test_saludo_simple(self):
        """Saludos simples son del negocio."""
        result, _ = is_business_related("hola")
        assert result is True
    
    def test_pregunta_maquina(self):
        """Preguntas sobre máquinas son del negocio."""
        result, _ = is_business_related("¿Cuánto cuesta una máquina de coser?")
        assert result is True
    
    def test_pregunta_precio(self):
        """Preguntas de precio son del negocio."""
        result, _ = is_business_related("precio de singer heavy duty")
        assert result is True
    
    def test_pregunta_programacion(self):
        """Preguntas de programación NO son del negocio."""
        result, reason = is_business_related("¿cómo hago un código en python para ordenar una lista?")
        assert result is False
        assert reason == "non_business"
    
    def test_pregunta_javascript(self):
        """Preguntas de JavaScript NO son del negocio."""
        result, _ = is_business_related("ayúdame con este bug de javascript")
        assert result is False
    
    def test_pregunta_medica(self):
        """Preguntas médicas NO son del negocio."""
        result, _ = is_business_related("tengo dolor de cabeza, ¿qué medicina tomo?")
        assert result is False
    
    def test_confirmacion_corta(self):
        """Confirmaciones cortas son del negocio (clasificadas como empty_or_gibberish)."""
        result, reason = is_business_related("sí")
        assert result is True  # empty_or_gibberish se considera del negocio pero se trata diferente
        assert reason == "empty_or_gibberish"
    
    def test_pregunta_mixta_favorece_negocio(self):
        """Si menciona máquina aunque tenga otras palabras, es del negocio."""
        result, _ = is_business_related("necesito una máquina de coser para mi negocio")
        assert result is True
    
    def test_promocion(self):
        """Preguntas sobre promociones son del negocio."""
        result, _ = is_business_related("¿tienen promociones de navidad?")
        assert result is True
    
    def test_reparacion(self):
        """Consultas de reparación son del negocio."""
        result, _ = is_business_related("mi máquina no funciona, la pueden arreglar?")
        assert result is True


class TestIsCacheableQuery:
    """Tests para is_cacheable_query."""
    
    def test_horario_es_cacheable(self):
        """Consultas de horario son cacheables."""
        assert is_cacheable_query("¿cuál es el horario de atención?") is True
    
    def test_direccion_es_cacheable(self):
        """Consultas de dirección son cacheables."""
        assert is_cacheable_query("¿dónde quedan ubicados?") is True
    
    def test_pago_personal_no_cacheable(self):
        """Consultas de pago personal NO son cacheables."""
        assert is_cacheable_query("ya pagué $500.000") is False
    
    def test_telefono_no_cacheable(self):
        """Mensajes con teléfono NO son cacheables."""
        assert is_cacheable_query("mi número es 3142156486") is False


class TestIsSensitiveQuery:
    """Tests para is_sensitive_query."""
    
    def test_telefono_es_sensible(self):
        """Números de teléfono son sensibles."""
        assert is_sensitive_query("llámame al 3142156486") is True
    
    def test_email_es_sensible(self):
        """Emails son sensibles."""
        assert is_sensitive_query("mi correo es test@email.com") is True
    
    def test_pago_es_sensible(self):
        """Menciones de pago son sensibles."""
        assert is_sensitive_query("ya pagué la transferencia") is True
    
    def test_pregunta_general_no_sensible(self):
        """Preguntas generales no son sensibles."""
        assert is_sensitive_query("¿tienen máquinas singer?") is False


class TestOffTopicResponse:
    """Tests para la respuesta fuera de tema."""
    
    def test_response_no_vacio(self):
        """La respuesta no debe estar vacía."""
        response = get_off_topic_response()
        assert len(response) > 0
    
    def test_response_menciona_maquinas(self):
        """La respuesta debe mencionar el negocio."""
        response = get_off_topic_response()
        assert "máquina" in response.lower() or "sastre" in response.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
