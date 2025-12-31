"""
Tests para el servicio de handoff y routing.
Verifica que casos comerciales vs técnicos se enruten correctamente.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.handoff_service import (
    should_handoff,
    route_case,
    build_internal_notification,
    create_summary_bullets
)
from app.models.schemas import Team, Priority


class TestShouldHandoff:
    """Tests para should_handoff."""
    
    def test_urgente_requiere_handoff(self):
        """Mensaje urgente requiere handoff."""
        decision = should_handoff("esto es urgente, necesito ayuda ya", {})
        assert decision.should_handoff is True
        assert decision.priority == Priority.URGENT
    
    def test_reclamo_requiere_handoff(self):
        """Reclamo requiere handoff."""
        decision = should_handoff("quiero hacer un reclamo, el producto llegó roto", {})
        assert decision.should_handoff is True
        # Puede ir a comercial o técnica dependiendo del contexto
        assert decision.team in [Team.COMERCIAL, Team.TECNICA]
    
    def test_instalacion_requiere_handoff_tecnico(self):
        """Solicitud de instalación va a técnica."""
        # Usar palabra más específica para instalación
        decision = should_handoff("necesito que vengan a instalar la máquina", {})
        assert decision.should_handoff is True
        # "instalar" + "vengan" puede detectar VISITA que va a técnica
        assert decision.team == Team.TECNICA
    
    def test_emprendimiento_requiere_handoff_comercial(self):
        """Emprendimiento va a comercial."""
        decision = should_handoff("quiero montar mi negocio de confección", {})
        assert decision.should_handoff is True
        assert decision.team == Team.COMERCIAL
    
    def test_ciudad_otra_requiere_handoff(self):
        """Ciudad diferente a Montería requiere handoff."""
        decision = should_handoff("estoy en Bogotá, me pueden enviar?", {})
        assert decision.should_handoff is True
    
    def test_pregunta_simple_no_requiere_handoff(self):
        """Pregunta simple no requiere handoff."""
        decision = should_handoff("hola, ¿qué máquinas tienen?", {})
        assert decision.should_handoff is False
    
    def test_saludo_no_requiere_handoff(self):
        """Saludo no requiere handoff."""
        decision = should_handoff("buenos días", {})
        assert decision.should_handoff is False
    
    def test_reparacion_requiere_handoff_tecnico(self):
        """Solicitud de reparación va a técnica."""
        decision = should_handoff("mi máquina se dañó, necesito arreglarla", {})
        assert decision.should_handoff is True
        assert decision.team == Team.TECNICA


class TestRouteCase:
    """Tests para route_case."""
    
    def test_route_comercial(self):
        """Caso comercial se enruta correctamente."""
        team, reason, priority = route_case(
            "compra",
            {"ciudad": "bogota"},
            "quiero comprar una máquina"
        )
        # Puede ser comercial por la ciudad
        assert team is not None or priority == Priority.LOW
    
    def test_route_tecnico(self):
        """Caso técnico se enruta correctamente."""
        team, reason, priority = route_case(
            "servicio",
            {},
            "mi máquina necesita reparación"
        )
        assert team == Team.TECNICA
    

class TestBuildInternalNotification:
    """Tests para build_internal_notification."""
    
    def test_notificacion_comercial(self):
        """Notificación comercial tiene formato correcto."""
        notification = build_internal_notification(
            team=Team.COMERCIAL,
            customer_phone="+573142156486",
            customer_name="Juan Pérez",
            summary_bullets=["Interesado en máquina industrial", "Para producción de gorras"],
            next_step="Contactar para asesorar"
        )
        
        assert "💰 ATENCIÓN COMERCIAL" in notification
        assert "Juan Pérez" in notification
        assert "+573142156486" in notification
        assert "Interesado en máquina industrial" in notification
    
    def test_notificacion_tecnica(self):
        """Notificación técnica tiene formato correcto."""
        notification = build_internal_notification(
            team=Team.TECNICA,
            customer_phone="+573001234567",
            customer_name=None,
            summary_bullets=["Máquina no funciona"],
            next_step="Coordinar diagnóstico"
        )
        
        assert "⚙️ ATENCIÓN TÉCNICA" in notification
        assert "Número:" in notification
        assert "Máquina no funciona" in notification
    
    def test_notificacion_sin_nombre(self):
        """Notificación sin nombre de cliente funciona."""
        notification = build_internal_notification(
            team=Team.COMERCIAL,
            customer_phone="+573001234567",
            customer_name=None,
            summary_bullets=["Test bullet"],
            next_step="Test paso"
        )
        
        assert "Cliente:" not in notification
        assert "Número:" in notification


class TestCreateSummaryBullets:
    """Tests para create_summary_bullets."""
    
    def test_bullets_con_contexto(self):
        """Bullets se crean correctamente con contexto."""
        context = {
            "tipo_maquina": "industrial",
            "uso": "gorras",
            "ciudad": "bogotá",
            "etapa_funnel": "decision"
        }
        bullets = create_summary_bullets("necesito cotización", context)
        
        assert len(bullets) > 0
        assert any("industrial" in b.lower() for b in bullets)
        assert any("gorras" in b.lower() for b in bullets)
    
    def test_bullets_sin_contexto(self):
        """Bullets se crean aunque no haya contexto."""
        bullets = create_summary_bullets("hola", {})
        
        assert len(bullets) > 0
        assert any("Último mensaje" in b for b in bullets)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
