#!/usr/bin/env python3
"""
Script de prueba para verificar idempotencia del webhook de WhatsApp.
Simula dos POSTs con el mismo message_id y verifica que el segundo sea deduplicado.
"""
import requests
import json
import sys
import time

# URL del webhook (local o producción)
WEBHOOK_URL = "http://localhost:8000/whatsapp/webhook"

# Payload de prueba (simula un mensaje real de Meta)
TEST_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551380876",
                            "phone_number_id": "996869753500859"
                        },
                        "contacts": [
                            {
                                "profile": {
                                    "name": "Test User"
                                },
                                "wa_id": "573142156486"
                            }
                        ],
                        "messages": [
                            {
                                "from": "573142156486",
                                "id": "wamid.test_idempotency_12345",
                                "timestamp": "1234567890",
                                "type": "text",
                                "text": {
                                    "body": "hola"
                                }
                            }
                        ]
                    },
                    "field": "messages"
                }
            ]
        }
    ]
}


def test_idempotency():
    """Prueba que el mismo message_id no se procese dos veces."""
    print("=" * 70)
    print("PRUEBA DE IDEMPOTENCIA - WhatsApp Webhook")
    print("=" * 70)
    print()
    
    # Primer request
    print("1️⃣ Enviando primer request (message_id nuevo)...")
    start1 = time.perf_counter()
    try:
        response1 = requests.post(
            WEBHOOK_URL,
            json=TEST_PAYLOAD,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        elapsed1 = (time.perf_counter() - start1) * 1000
        print(f"   Status: {response1.status_code}")
        print(f"   Response: {response1.json()}")
        print(f"   Tiempo: {elapsed1:.1f}ms")
        
        if response1.status_code != 200:
            print(f"   ❌ ERROR: Primer request falló con status {response1.status_code}")
            return False
        
        result1 = response1.json()
        if result1.get("dedup"):
            print("   ⚠️  WARNING: Primer request fue marcado como duplicado (no debería)")
            return False
        
        if not result1.get("queued"):
            print("   ⚠️  WARNING: Primer request no fue encolado")
        
    except Exception as e:
        print(f"   ❌ ERROR en primer request: {e}")
        return False
    
    print()
    time.sleep(0.5)  # Pequeña pausa entre requests
    
    # Segundo request (mismo message_id)
    print("2️⃣ Enviando segundo request (mismo message_id)...")
    start2 = time.perf_counter()
    try:
        response2 = requests.post(
            WEBHOOK_URL,
            json=TEST_PAYLOAD,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        elapsed2 = (time.perf_counter() - start2) * 1000
        print(f"   Status: {response2.status_code}")
        print(f"   Response: {response2.json()}")
        print(f"   Tiempo: {elapsed2:.1f}ms")
        
        if response2.status_code != 200:
            print(f"   ❌ ERROR: Segundo request falló con status {response2.status_code}")
            return False
        
        result2 = response2.json()
        if not result2.get("dedup"):
            print("   ❌ ERROR: Segundo request NO fue deduplicado (debería ser dedup=True)")
            return False
        
        if elapsed2 > 1000:
            print(f"   ⚠️  WARNING: Segundo request tardó {elapsed2:.1f}ms (debería ser <1000ms)")
        
    except Exception as e:
        print(f"   ❌ ERROR en segundo request: {e}")
        return False
    
    print()
    print("=" * 70)
    print("✅ PRUEBA EXITOSA")
    print("=" * 70)
    print()
    print("Resumen:")
    print(f"  - Primer request: procesado (queued=True)")
    print(f"  - Segundo request: deduplicado (dedup=True)")
    print(f"  - ACK rápido: {elapsed1:.1f}ms y {elapsed2:.1f}ms")
    print()
    
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        WEBHOOK_URL = sys.argv[1]
        print(f"Usando URL: {WEBHOOK_URL}")
        print()
    
    success = test_idempotency()
    sys.exit(0 if success else 1)

