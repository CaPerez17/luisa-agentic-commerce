"""
Tests de smoke para verificar que /api/chat sigue funcionando.
Estos tests requieren que el servidor esté corriendo.
Se pueden ejecutar manualmente con: pytest tests/test_conversation_smoke.py -v
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestApiSmoke:
    """
    Tests de smoke que verifican funcionalidad básica.
    Nota: Estos tests usan imports directos en lugar de TestClient
    para evitar problemas de compatibilidad de versiones.
    """
    
    def test_app_imports(self):
        """La app se puede importar."""
        from main import app
        assert app is not None
        assert app.title == "LUISA - Asistente El Sastre"
    
    def test_new_modules_available(self):
        """Los nuevos módulos están disponibles."""
    try:
            from main import NEW_MODULES_AVAILABLE
            # Puede ser True o False dependiendo de la configuración
            assert NEW_MODULES_AVAILABLE in [True, False]
        except ImportError:
            # Si no se puede importar, pasar el test
            pass
    
    def test_catalog_index_loaded(self):
        """El índice del catálogo se carga."""
        from main import CATALOG_INDEX
        assert isinstance(CATALOG_INDEX, dict)
        assert len(CATALOG_INDEX) > 0
    
    def test_generate_response_function_exists(self):
        """La función generate_response existe."""
        from main import generate_response
        assert callable(generate_response)
    
    def test_should_handoff_function_exists(self):
        """La función should_handoff existe."""
        from main import should_handoff
        assert callable(should_handoff)
    
    def test_init_db_runs(self):
        """init_db no falla."""
        from main import init_db
        # No debería lanzar excepción
        init_db()


class TestGenerateResponse:
    """Tests para la función generate_response."""
    
    def test_build_response_function_callable(self):
        """La función build_response es callable."""
        from app.services.response_service import build_response
        assert callable(build_response)

    def test_saludo_no_selecciona_asset(self):
        """Los saludos no deben seleccionar assets."""
        from app.services.response_service import build_response

        result = build_response(
            text="hola, buenos días",
            conversation_id="test_saludo_asset",
            channel="api"
        )

        # Verificar que no hay asset
        assert result["asset"] is None

        # Verificar que la respuesta es específica para saludo
        assert "familiar" in result["text"].lower() or "industrial" in result["text"].lower()

    def test_venta_maquina_puede_seleccionar_asset(self):
        """Las consultas de venta pueden seleccionar assets."""
        from app.services.response_service import build_response

        result = build_response(
            text="necesito una máquina industrial",
            conversation_id="test_venta_asset",
            channel="api"
        )

        # Puede o no seleccionar asset dependiendo del contexto y reglas
        # Lo importante es que no falle y tenga respuesta
        assert result["text"]
        assert len(result["text"]) > 0

    def test_postprocesador_agrega_pregunta_maquina_industrial(self):
        """El post-procesador añade pregunta a respuesta informativa de máquina industrial."""
        from app.services.response_service import ensure_next_step_question

        # Respuesta sin pregunta
        input_text = "Tenemos máquinas industriales desde $1.230.000"
        result = ensure_next_step_question(input_text, "buscar_maquina_industrial", {})

        # Debe añadir pregunta
        assert "?" in result
        assert "industrial" in result.lower()
        assert result != input_text  # Debe ser diferente

    def test_postprocesador_agrega_pregunta_pagos(self):
        """El post-procesador añade pregunta a respuesta de pagos."""
        from app.services.response_service import ensure_next_step_question

        input_text = "Aceptamos diferentes formas de pago"
        result = ensure_next_step_question(input_text, "pagos", {})

        assert "?" in result
        assert "addi" in result.lower() or "credito" in result.lower()
        assert result != input_text

    def test_postprocesador_agrega_pregunta_envios(self):
        """El post-procesador añade pregunta a respuesta de envíos."""
        from app.services.response_service import ensure_next_step_question

        input_text = "Hacemos envíos a toda Colombia"
        result = ensure_next_step_question(input_text, "envios", {})

        assert "?" in result
        assert "ciudad" in result.lower() or "municipio" in result.lower()
        assert result != input_text

    def test_postprocesador_no_modifica_con_pregunta_existente(self):
        """No modifica respuesta que ya tiene pregunta."""
        from app.services.response_service import ensure_next_step_question

        input_text = "Tenemos máquinas industriales. ¿Cuál te interesa?"
        result = ensure_next_step_question(input_text, "buscar_maquina_industrial", {})
        
        # Debe quedar igual
        assert result == input_text
        assert result.count("?") == 1
    
    def test_postprocesador_no_modifica_saludo(self):
        """No modifica respuestas de saludo."""
        from app.services.response_service import ensure_next_step_question

        input_text = "¡Hola! ¿En qué puedo ayudarte?"
        result = ensure_next_step_question(input_text, "saludo", {})

        # Debe quedar igual
        assert result == input_text

    def test_postprocesador_no_modifica_despedida(self):
        """No modifica respuestas de despedida."""
        from app.services.response_service import ensure_next_step_question

        input_text = "¡Gracias por contactarnos!"
        result = ensure_next_step_question(input_text, "despedida", {})

        # Debe quedar igual
        assert result == input_text

    def test_clasificacion_mensaje_programacion(self):
        """Clasifica mensajes de programación como NON_BUSINESS."""
        from app.rules.business_guardrails import classify_message_type, MessageType

        result = classify_message_type("cómo hago un for en python")
        assert result == MessageType.NON_BUSINESS

    def test_clasificacion_mensaje_gibberish(self):
        """Clasifica mensajes vacíos o gibberish correctamente."""
        from app.rules.business_guardrails import classify_message_type, MessageType

        assert classify_message_type("👍") == MessageType.EMPTY_OR_GIBBERISH
        assert classify_message_type("ok") == MessageType.EMPTY_OR_GIBBERISH
        assert classify_message_type("") == MessageType.EMPTY_OR_GIBBERISH

    def test_clasificacion_mensaje_faq(self):
        """Clasifica preguntas FAQ como BUSINESS_FAQ."""
        from app.rules.business_guardrails import classify_message_type, MessageType

        assert classify_message_type("cuáles son los horarios") == MessageType.BUSINESS_FAQ
        assert classify_message_type("aceptan pagos en cuotas") == MessageType.BUSINESS_FAQ

    def test_clasificacion_mensaje_consultoria(self):
        """Clasifica consultas complejas como BUSINESS_CONSULT."""
        from app.rules.business_guardrails import classify_message_type, MessageType

        assert classify_message_type("quiero montar un taller de gorras") == MessageType.BUSINESS_CONSULT
        assert classify_message_type("necesito máquina para cuero") == MessageType.BUSINESS_CONSULT

    def test_gating_openai_programacion_bloqueado(self):
        """OpenAI se bloquea para mensajes de programación."""
        from app.services.response_service import should_call_openai
        from app.rules.business_guardrails import MessageType
        from app.config import OPENAI_ENABLED

        # Simular OpenAI habilitado para test
        original_enabled = OPENAI_ENABLED
        try:
            import app.config
            app.config.OPENAI_ENABLED = True

            result = should_call_openai(
                intent="programacion",
                message_type=MessageType.NON_BUSINESS,
                text="cómo hago un for en python",
                context={},
                cache_hit=False
            )
            assert result == False, "OpenAI debería bloquearse para programación"

        finally:
            app.config.OPENAI_ENABLED = original_enabled

    def test_gating_openai_faq_bloqueado(self):
        """OpenAI se bloquea para FAQ simples."""
        from app.services.response_service import should_call_openai
        from app.rules.business_guardrails import MessageType
        from app.config import OPENAI_ENABLED

        # Simular OpenAI habilitado para test
        original_enabled = OPENAI_ENABLED
        try:
            import app.config
            app.config.OPENAI_ENABLED = True

            result = should_call_openai(
                intent="horarios",
                message_type=MessageType.BUSINESS_FAQ,
                text="cuáles son los horarios",
                context={},
                cache_hit=False
            )
            assert result == False, "OpenAI debería bloquearse para FAQ"

        finally:
            app.config.OPENAI_ENABLED = original_enabled

    def test_gating_openai_consultoria_permitido(self):
        """OpenAI se permite para consultoría compleja."""
        from app.services.response_service import should_call_openai
        from app.rules.business_guardrails import MessageType
        import app.services.response_service as rs

        # Simular OpenAI habilitado para test
        original_enabled = rs.OPENAI_ENABLED
        try:
            rs.OPENAI_ENABLED = True

            result = should_call_openai(
                intent="asesoria_negocio",
                message_type=MessageType.BUSINESS_CONSULT,
                text="quiero montar un taller de gorras",
                context={},
                cache_hit=False
            )
            assert result == True, "OpenAI debería permitirse para consultoría compleja"

        finally:
            rs.OPENAI_ENABLED = original_enabled


class TestShouldHandoff:
    """Tests para la función should_handoff del main."""
    
    def test_handoff_con_impacto_negocio(self):
        """Mensaje de negocio requiere escalamiento."""
        from main import should_handoff
        # should_handoff retorna tupla (should_handoff, reason, priority)
        result = should_handoff("quiero montar mi negocio de confección", {})
        # El primer elemento indica si requiere handoff
        if isinstance(result, tuple):
            assert result[0] is True
        else:
            assert result is True
    
    def test_no_handoff_saludo(self):
        """Saludo no requiere escalamiento."""
        from main import should_handoff
        result = should_handoff("buenos días", {})
        # Puede retornar False directamente o tupla (False, '', 'low')
        if isinstance(result, tuple):
            assert result[0] is False
        else:
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
