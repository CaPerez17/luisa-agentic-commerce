#!/usr/bin/env python3
"""
Script CLI para obtener snapshot de métricas operacionales.
Imprime las mismas métricas que el endpoint /ops/snapshot.
"""
import sys
from pathlib import Path

# Agregar backend al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.ops_service import get_ops_snapshot


def main():
    """Función principal."""
    print("📊 Snapshot de Métricas Operacionales (últimas 60 minutos)\n")
    
    snapshot = get_ops_snapshot()
    
    if "error" in snapshot:
        print(f"❌ Error obteniendo métricas: {snapshot['error']}")
        return 1
    
    print(f"Total mensajes: {snapshot['total_msgs_60m']}")
    print(f"% Personal: {snapshot['pct_personal']}%")
    print(f"% Handoff: {snapshot['pct_handoff']}%")
    print(f"% OpenAI: {snapshot['pct_openai']}%")
    print(f"Errores: {snapshot['errores_count']}")
    print(f"P95 Latencia: {snapshot['p95_latency_ms']}ms")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
