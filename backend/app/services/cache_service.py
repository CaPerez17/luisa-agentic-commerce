"""
Servicio de cache in-memory con TTL para respuestas de FAQs.
Sin Redis, solo estructuras de datos de Python.
"""
import time
from typing import Optional, Dict, Any
from collections import OrderedDict
from threading import Lock

from app.config import CACHE_ENABLED, CACHE_MAX_SIZE, CACHE_TTL_HOURS
from app.rules.keywords import normalize_text


class LRUCache:
    """
    Cache LRU (Least Recently Used) con TTL.
    Thread-safe para uso en FastAPI.
    """
    
    def __init__(self, max_size: int = 200, ttl_hours: int = 12):
        self.max_size = max_size
        self.ttl_seconds = ttl_hours * 3600
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
    
    def _normalize_key(self, text: str) -> str:
        """Normaliza el texto para usar como clave."""
        # Normalizar y reducir a palabras clave significativas
        normalized = normalize_text(text)
        # Remover palabras muy comunes que no aportan
        stopwords = {"el", "la", "los", "las", "un", "una", "de", "del", "que", "y", "a", "en", "por", "para"}
        words = [w for w in normalized.split() if w not in stopwords and len(w) > 2]
        return " ".join(sorted(words[:10]))  # Máximo 10 palabras, ordenadas
    
    def get(self, text: str) -> Optional[str]:
        """
        Obtiene una respuesta cacheada.
        
        Returns:
            Respuesta cacheada o None si no existe o expiró.
        """
        if not CACHE_ENABLED:
            return None
        
        key = self._normalize_key(text)
        
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # Verificar TTL
            if time.time() > entry["expires_at"]:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Mover al final (más reciente)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry["response"]
    
    def set(self, text: str, response: str) -> None:
        """
        Guarda una respuesta en el cache.
        """
        if not CACHE_ENABLED:
            return
        
        key = self._normalize_key(text)
        
        with self._lock:
            # Si ya existe, actualizar
            if key in self._cache:
                self._cache[key] = {
                    "response": response,
                    "expires_at": time.time() + self.ttl_seconds,
                    "created_at": time.time()
                }
                self._cache.move_to_end(key)
                return
            
            # Si está lleno, eliminar el más antiguo
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            # Agregar nuevo
            self._cache[key] = {
                "response": response,
                "expires_at": time.time() + self.ttl_seconds,
                "created_at": time.time()
            }
    
    def clear(self) -> None:
        """Limpia todo el cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del cache."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "enabled": CACHE_ENABLED,
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_hours": self.ttl_seconds / 3600,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2)
            }
    
    def cleanup_expired(self) -> int:
        """
        Limpia entradas expiradas.
        Retorna el número de entradas eliminadas.
        """
        removed = 0
        current_time = time.time()
        
        with self._lock:
            keys_to_remove = [
                key for key, entry in self._cache.items()
                if current_time > entry["expires_at"]
            ]
            for key in keys_to_remove:
                del self._cache[key]
                removed += 1
        
        return removed


# Instancia global del cache
response_cache = LRUCache(max_size=CACHE_MAX_SIZE, ttl_hours=CACHE_TTL_HOURS)


def get_cached_response(text: str) -> Optional[str]:
    """Obtiene respuesta cacheada."""
    return response_cache.get(text)


def cache_response(text: str, response: str) -> None:
    """Cachea una respuesta."""
    response_cache.set(text, response)


def get_cache_stats() -> Dict[str, Any]:
    """Obtiene estadísticas del cache."""
    return response_cache.stats()


def clear_cache() -> None:
    """Limpia el cache."""
    response_cache.clear()
