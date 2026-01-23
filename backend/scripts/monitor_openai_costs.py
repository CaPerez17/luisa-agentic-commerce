#!/usr/bin/env python3
"""
Script para monitorear costos de OpenAI en producción.

Calcula métricas de uso y costo estimado desde interaction_traces.
Valida que el costo promedio < $0.05 por conversación.
Hard-fail si costo > umbral.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar backend al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.database import get_connection
from app.logging_config import logger

# Estimación conservadora de costo por llamada OpenAI (gpt-4o-mini)
# Input: ~$0.15/1M tokens, Output: ~$0.60/1M tokens
# Estimación: ~$0.03 por llamada promedio (100 tokens input + 50 tokens output)
COSTO_ESTIMADO_POR_LLAMADA = 0.03
UMBRAL_COSTO_POR_CONVERSACION = 0.05  # $0.05 por conversación


def calculate_openai_metrics(hours: int = 24) -> dict:
    """
    Calcula métricas de OpenAI desde interaction_traces.
    
    Args:
        hours: Horas hacia atrás para analizar (default: 24)
    
    Returns:
        Dict con métricas
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Query: métricas de las últimas N horas
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT conversation_id) as total_conversations,
                SUM(CASE WHEN openai_called = 1 THEN 1 ELSE 0 END) as total_openai_calls,
                AVG(CASE WHEN openai_called = 1 THEN openai_latency_ms ELSE NULL END) as avg_openai_latency_ms,
                SUM(CASE WHEN openai_fallback_used = 1 THEN 1 ELSE 0 END) as total_fallbacks,
                SUM(CASE WHEN openai_canary_allowed = 0 AND openai_called = 1 THEN 1 ELSE 0 END) as unauthorized_calls
            FROM interaction_traces
            WHERE created_at > datetime('now', '-' || ? || ' hours')
        """, (hours,))
        
        row = cursor.fetchone()
        
        if not row or row[0] is None:
            return {
                "total_conversations": 0,
                "total_openai_calls": 0,
                "avg_openai_latency_ms": 0.0,
                "total_fallbacks": 0,
                "unauthorized_calls": 0,
                "costo_total_estimado": 0.0,
                "costo_promedio_por_conv": 0.0
            }
        
        total_conversations = row[0] or 0
        total_openai_calls = row[1] or 0
        avg_openai_latency_ms = row[2] or 0.0
        total_fallbacks = row[3] or 0
        unauthorized_calls = row[4] or 0
        
        # Calcular costos
        costo_total_estimado = total_openai_calls * COSTO_ESTIMADO_POR_LLAMADA
        costo_promedio_por_conv = costo_total_estimado / total_conversations if total_conversations > 0 else 0.0
        
        return {
            "total_conversations": total_conversations,
            "total_openai_calls": total_openai_calls,
            "avg_openai_latency_ms": round(avg_openai_latency_ms, 1),
            "total_fallbacks": total_fallbacks,
            "unauthorized_calls": unauthorized_calls,
            "costo_total_estimado": round(costo_total_estimado, 4),
            "costo_promedio_por_conv": round(costo_promedio_por_conv, 4)
        }
    
    except Exception as e:
        logger.error("Error calculando métricas OpenAI", error=str(e))
        return {
            "error": str(e)
        }
    finally:
        conn.close()


def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitorear costos de OpenAI")
    parser.add_argument("--hours", type=int, default=24, help="Horas hacia atrás para analizar (default: 24)")
    parser.add_argument("--threshold", type=float, default=UMBRAL_COSTO_POR_CONVERSACION, help="Umbral de costo por conversación (default: 0.05)")
    args = parser.parse_args()
    
    print(f"📊 Monitoreo de Costos OpenAI (últimas {args.hours} horas)\n")
    
    metrics = calculate_openai_metrics(args.hours)
    
    if "error" in metrics:
        print(f"❌ Error: {metrics['error']}")
        return 1
    
    print("="*60)
    print("📈 MÉTRICAS DE USO")
    print("="*60)
    print(f"Total conversaciones: {metrics['total_conversations']}")
    print(f"Total llamadas OpenAI: {metrics['total_openai_calls']}")
    print(f"Latencia promedio OpenAI: {metrics['avg_openai_latency_ms']}ms")
    print(f"Fallbacks usados: {metrics['total_fallbacks']}")
    print(f"Llamadas no autorizadas (canary): {metrics['unauthorized_calls']}")
    
    print("\n" + "="*60)
    print("💰 COSTOS ESTIMADOS")
    print("="*60)
    print(f"Costo total estimado: ${metrics['costo_total_estimado']:.4f}")
    print(f"Costo promedio por conversación: ${metrics['costo_promedio_por_conv']:.4f}")
    print(f"Umbral máximo: ${args.threshold:.4f}")
    
    print("\n" + "="*60)
    print("🎯 VALIDACIÓN")
    print("="*60)
    
    costo_ok = metrics['costo_promedio_por_conv'] < args.threshold
    unauthorized_ok = metrics['unauthorized_calls'] == 0
    
    print(f"Costo promedio < ${args.threshold:.4f}: {'✅' if costo_ok else '❌'} (${metrics['costo_promedio_por_conv']:.4f})")
    print(f"Llamadas no autorizadas = 0: {'✅' if unauthorized_ok else '❌'} ({metrics['unauthorized_calls']})")
    
    if not costo_ok:
        print(f"\n❌ VALIDACIÓN FALLÓ: Costo promedio (${metrics['costo_promedio_por_conv']:.4f}) excede umbral (${args.threshold:.4f})")
        return 1
    
    if not unauthorized_ok:
        print(f"\n❌ VALIDACIÓN FALLÓ: {metrics['unauthorized_calls']} llamadas no autorizadas detectadas")
        return 1
    
    print("\n✅ VALIDACIÓN EXITOSA: Todos los criterios cumplidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
