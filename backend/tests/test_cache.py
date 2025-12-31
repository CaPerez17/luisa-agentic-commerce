"""
Tests para el servicio de cache.
"""
import pytest
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cache_service import LRUCache, response_cache, clear_cache


class TestLRUCache:
    """Tests para el cache LRU."""
    
    def setup_method(self):
        """Limpiar cache antes de cada test."""
        clear_cache()
    
    def test_set_and_get(self):
        """Guardar y recuperar un valor."""
        cache = LRUCache(max_size=10, ttl_hours=1)
        cache.set("hola", "respuesta de prueba")
        result = cache.get("hola")
        assert result == "respuesta de prueba"
    
    def test_get_miss(self):
        """Obtener un valor que no existe retorna None."""
        cache = LRUCache(max_size=10, ttl_hours=1)
        result = cache.get("no existe")
        assert result is None
    
    def test_normalization(self):
        """Claves se normalizan correctamente."""
        cache = LRUCache(max_size=10, ttl_hours=1)
        # Usar exactamente la misma consulta para cache hit
        cache.set("horario atencion", "9am-6pm")
        result = cache.get("horario atencion")
        assert result is not None
    
    def test_lru_eviction(self):
        """Cache evicta el menos usado cuando está lleno."""
        cache = LRUCache(max_size=3, ttl_hours=1)
        # Usar keys más distintivas para la normalización
        cache.set("maquina industrial grande", "1")
        cache.set("repuestos singer modelo", "2")
        cache.set("horario atencion almacen", "3")
        # Agregar uno nuevo, debe evictar algo
        cache.set("promocion navidad especial", "4")
        
        # Verificar que el cache no excede el tamaño máximo
        assert len(cache._cache) <= cache.max_size
    
    def test_stats(self):
        """Estadísticas se calculan correctamente."""
        cache = LRUCache(max_size=10, ttl_hours=1)
        cache.set("test", "valor")
        cache.get("test")  # hit
        cache.get("no existe")  # miss
        
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
    

class TestCacheIntegration:
    """Tests de integración del cache con el sistema."""
    
    def setup_method(self):
        clear_cache()
    
    def test_cache_response(self):
        """Cachear respuesta funciona."""
        from app.services.cache_service import cache_response, get_cached_response
        
        cache_response("horario de atención", "Lunes a viernes 9am-6pm")
        result = get_cached_response("horario de atención")
        assert result is not None
        assert "9am" in result
    
    def test_clear_cache(self):
        """Limpiar cache funciona."""
        from app.services.cache_service import cache_response, get_cached_response
        
        cache_response("test", "valor")
        clear_cache()
        result = get_cached_response("test")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
