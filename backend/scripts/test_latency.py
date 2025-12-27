#!/usr/bin/env python3
"""
Script para demostrar medición de latencia precisa.
Ejecutar con: python scripts/test_latency.py
"""
import sys
import time
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_latency_precision():
    """Demuestra medición de latencia precisa."""
    from app.services.trace_service import InteractionTracer

    print("🕒 Probando medición de latencia precisa...")

    # Crear tracer
    tracer = InteractionTracer(request_id="test_lat_001", conversation_id="test_lat")
    tracer.start()

    # Simular procesamiento
    time.sleep(0.01)  # 10ms
    tracer.raw_text = "test message"
    tracer.intent = "test"
    tracer.response_text = "test response"

    # Detener y mostrar resultados
    latency_ms = tracer.stop()

    print(f"   latency_ms: {latency_ms:.1f} ms")
    print(f"   latency_us: {tracer.latency_us} μs")

    # Verificar que no es 0
    assert latency_ms > 0, "Latency debe ser > 0"
    assert tracer.latency_us > 0, "Latency_us debe ser > 0"
    assert latency_ms >= 10, "Debe medir al menos los 10ms de sleep"

    print("✅ Latencia medida correctamente!")


def test_database_latency():
    """Verifica que la latencia se guarda correctamente en BD."""
    from app.services.response_service import build_response

    print("\n💾 Probando latencia con escritura a BD...")

    result = build_response(
        text="hola",
        conversation_id="test_db_latency",
        channel="api"
    )

    print("✅ Respuesta generada")

    # Verificar en BD
    import sqlite3
    conn = sqlite3.connect("luisa.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT latency_ms, latency_us, response_len_chars
        FROM interaction_traces
        WHERE conversation_id='test_db_latency'
        ORDER BY created_at DESC LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if row:
        latency_ms, latency_us, response_len_chars = row
        print(f"   latency_ms: {latency_ms:.1f} ms")
        print(f"   latency_us: {latency_us} μs")
        print(f"   response_len_chars: {response_len_chars}")

        assert latency_ms > 0, "Latency_ms debe ser > 0 en BD"
        assert latency_us > 0, "Latency_us debe ser > 0 en BD"
        assert response_len_chars > 0, "Response_len_chars debe ser > 0"

        print("✅ Latencia guardada correctamente en BD!")
    else:
        raise AssertionError("No se encontró la traza en BD")


def main():
    """Ejecutar pruebas de latencia."""
    print("=" * 60)
    print("🕒 TEST LATENCIA PRECISA")
    print("=" * 60)

    test_latency_precision()
    test_database_latency()

    print("\n" + "=" * 60)
    print("✅ TODAS LAS PRUEBAS DE LATENCIA PASARON!")
    print("   - Medición precisa con time.perf_counter()")
    print("   - Latencia en ms (float con 1 decimal)")
    print("   - Latencia en μs (integer)")
    print("   - Incluye escritura de trace")
    print("   - Nunca 0ms por truncamiento")
    print("=" * 60)


if __name__ == "__main__":
    main()
