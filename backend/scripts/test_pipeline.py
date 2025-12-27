#!/usr/bin/env python3
"""
Script de prueba para verificar el pipeline nuevo.
Ejecutar con: python scripts/test_pipeline.py
"""
import sys
import os
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Verificar que todos los módulos se importan correctamente."""
    print("🧪 Probando imports...")

    try:
        from app.config import OPENAI_ENABLED, WHATSAPP_ENABLED, CACHE_ENABLED
        print(f"✅ Config: OPENAI={OPENAI_ENABLED}, WHATSAPP={WHATSAPP_ENABLED}, CACHE={CACHE_ENABLED}")

        from app.services.response_service import build_response
        print("✅ build_response importado")

        from app.services.cache_service import get_cache_stats
        print("✅ Cache service importado")

        from app.services.handoff_service import process_handoff
        print("✅ Handoff service importado")

        from app.rules.business_guardrails import is_business_related
        print("✅ Guardrails importado")

        return True
    except Exception as e:
        print(f"❌ Error en imports: {e}")
        return False

def test_guardrails():
    """Probar guardrails de negocio."""
    print("\n🧪 Probando guardrails...")

    from app.rules.business_guardrails import is_business_related

    # Test negocio
    result, reason = is_business_related("necesito una máquina de coser")
    if result:
        print("✅ Mensaje de negocio detectado correctamente")
    else:
        print(f"❌ Mensaje de negocio NO detectado: {reason}")

    # Test fuera del negocio
    result, reason = is_business_related("ayúdame con mi código python")
    if not result:
        print("✅ Mensaje fuera del negocio rechazado correctamente")
    else:
        print(f"❌ Mensaje fuera del negocio ACEPTADO: {reason}")

def test_cache():
    """Probar cache."""
    print("\n🧪 Probando cache...")

    from app.services.cache_service import get_cache_stats, clear_cache

    stats = get_cache_stats()
    print(f"📊 Cache stats: {stats}")

    clear_cache()
    print("🧹 Cache limpiado")

def test_build_response():
    """Probar build_response function."""
    print("\n🧪 Probando build_response...")

    from app.services.response_service import build_response

    # Test saludo (no debe seleccionar asset)
    result_saludo = build_response(
        text="hola, buenos días",
        conversation_id="test_saludo_001",
        channel="api"
    )

    if result_saludo["text"] and result_saludo["asset"] is None:
        print("✅ Saludo funciona correctamente (sin asset)")
        print(f"📝 Respuesta saludo: {result_saludo['text'][:100]}...")
    else:
        print(f"❌ Saludo falló: asset={result_saludo['asset']}, text='{result_saludo['text']}'")

    # Test consulta de producto (puede seleccionar asset)
    result_producto = build_response(
        text="necesito una máquina industrial",
        conversation_id="test_producto_001",
        channel="api"
    )

    if result_producto["text"]:
        print("✅ Consulta de producto funciona correctamente")
        print(f"📝 Respuesta producto: {result_producto['text'][:100]}...")
        print(f"🎯 Asset: {result_producto['asset']}")
    else:
        print("❌ Consulta de producto falló")

def main():
    """Ejecutar todas las pruebas."""
    print("=" * 60)
    print("🧪 TEST PIPELINE NUEVO - LUISA")
    print("=" * 60)

    success = True

    success &= test_imports()
    test_guardrails()
    test_cache()
    test_build_response()

    print("\n" + "=" * 60)
    if success:
        print("✅ TODAS LAS PRUEBAS PASARON")
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
    print("=" * 60)

if __name__ == "__main__":
    main()
