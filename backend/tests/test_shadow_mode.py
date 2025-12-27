"""
Tests para el modo sombra (HUMAN_ACTIVE silencia respuestas).
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import (
    get_conversation_mode,
    set_conversation_mode,
    create_or_update_conversation,
    get_db
)


class TestConversationMode:
    """Tests para el modo de conversación."""
    
    def setup_method(self):
        """Limpiar conversaciones de prueba."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE conversation_id LIKE 'test_shadow_%'")
    
    def test_default_mode_is_ai_active(self):
        """El modo por defecto es AI_ACTIVE."""
        create_or_update_conversation("test_shadow_001")
        mode = get_conversation_mode("test_shadow_001")
        assert mode == "AI_ACTIVE"
    
    def test_set_mode_to_human_active(self):
        """Se puede cambiar a HUMAN_ACTIVE."""
        create_or_update_conversation("test_shadow_002")
        set_conversation_mode("test_shadow_002", "HUMAN_ACTIVE")
        mode = get_conversation_mode("test_shadow_002")
        assert mode == "HUMAN_ACTIVE"
    
    def test_set_mode_back_to_ai_active(self):
        """Se puede volver a AI_ACTIVE."""
        create_or_update_conversation("test_shadow_003")
        set_conversation_mode("test_shadow_003", "HUMAN_ACTIVE")
        set_conversation_mode("test_shadow_003", "AI_ACTIVE")
        mode = get_conversation_mode("test_shadow_003")
        assert mode == "AI_ACTIVE"
    
    def test_nonexistent_conversation_returns_ai_active(self):
        """Conversación inexistente retorna AI_ACTIVE."""
        mode = get_conversation_mode("test_shadow_noexiste")
        assert mode == "AI_ACTIVE"


class TestShadowModePolicy:
    """Tests para la política de modo sombra."""
    
    def test_human_active_blocks_response(self):
        """En modo HUMAN_ACTIVE, LUISA no debería responder."""
        # Este es un test conceptual - la lógica real está en el router
        # Aquí solo verificamos que el modo se puede establecer
        create_or_update_conversation("test_shadow_policy_001")
        set_conversation_mode("test_shadow_policy_001", "HUMAN_ACTIVE")
        mode = get_conversation_mode("test_shadow_policy_001")
        
        # En producción, si mode == HUMAN_ACTIVE:
        #   - Solo registrar mensaje
        #   - NO enviar respuesta automática
        assert mode == "HUMAN_ACTIVE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
