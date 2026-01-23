"""
Servicio de operaciones y métricas para observabilidad mínima.
Expone métricas críticas desde interaction_traces.
"""
import sqlite3
from typing import Dict, Any, Optional
from pathlib import Path
import statistics

from app.config import DB_PATH
from app.models.database import get_connection


def get_ops_snapshot() -> Dict[str, Any]:
    """
    Obtiene snapshot de métricas operacionales desde interaction_traces.
    
    Calcula métricas de las últimas 60 minutos:
    - total_msgs_60m: Total de mensajes procesados
    - pct_personal: Porcentaje de mensajes personales
    - pct_handoff: Porcentaje de handoffs
    - pct_openai: Porcentaje de llamadas a OpenAI
    - errores_count: Cantidad de errores
    - p95_latency_ms: Percentil 95 de latencia
    
    Returns:
        Dict con métricas
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Query base: mensajes de las últimas 60 minutos
        cursor.execute("""
            SELECT 
                COUNT(*) as total_msgs_60m,
                SUM(CASE WHEN is_personal = 1 THEN 1 ELSE 0 END) as personal_count,
                SUM(CASE WHEN routed_team IS NOT NULL AND routed_team != '' THEN 1 ELSE 0 END) as handoff_count,
                SUM(CASE WHEN openai_called = 1 THEN 1 ELSE 0 END) as openai_count,
                SUM(CASE WHEN error_message IS NOT NULL AND error_message != '' THEN 1 ELSE 0 END) as errores_count,
                AVG(latency_ms) as avg_latency_ms
            FROM interaction_traces
            WHERE created_at > datetime('now', '-60 minutes')
        """)
        
        row = cursor.fetchone()
        
        if not row or row[0] is None:
            # No hay datos
            return {
                "total_msgs_60m": 0,
                "pct_personal": 0.0,
                "pct_handoff": 0.0,
                "pct_openai": 0.0,
                "errores_count": 0,
                "p95_latency_ms": 0.0
            }
        
        total_msgs_60m = row[0] or 0
        personal_count = row[1] or 0
        handoff_count = row[2] or 0
        openai_count = row[3] or 0
        errores_count = row[4] or 0
        avg_latency_ms = row[5] or 0.0
        
        # Calcular porcentajes
        pct_personal = (personal_count / total_msgs_60m * 100.0) if total_msgs_60m > 0 else 0.0
        pct_handoff = (handoff_count / total_msgs_60m * 100.0) if total_msgs_60m > 0 else 0.0
        pct_openai = (openai_count / total_msgs_60m * 100.0) if total_msgs_60m > 0 else 0.0
        
        # Calcular P95 de latencia
        cursor.execute("""
            SELECT latency_ms
            FROM interaction_traces
            WHERE created_at > datetime('now', '-60 minutes')
            AND latency_ms IS NOT NULL
            AND latency_ms > 0
            ORDER BY latency_ms
        """)
        
        latencies = [row[0] for row in cursor.fetchall()]
        
        if latencies:
            p95_index = int(len(latencies) * 0.95)
            p95_latency_ms = latencies[p95_index] if p95_index < len(latencies) else latencies[-1]
        else:
            p95_latency_ms = 0.0
        
        return {
            "total_msgs_60m": total_msgs_60m,
            "pct_personal": round(pct_personal, 2),
            "pct_handoff": round(pct_handoff, 2),
            "pct_openai": round(pct_openai, 2),
            "errores_count": errores_count,
            "p95_latency_ms": round(p95_latency_ms, 1)
        }
    
    except Exception as e:
        # En caso de error, retornar métricas vacías
        return {
            "total_msgs_60m": 0,
            "pct_personal": 0.0,
            "pct_handoff": 0.0,
            "pct_openai": 0.0,
            "errores_count": 0,
            "p95_latency_ms": 0.0,
            "error": str(e)
        }
    finally:
        conn.close()
