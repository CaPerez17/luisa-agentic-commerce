#!/usr/bin/env python3
"""
Script de prueba para el Sales Dialogue Manager.
Prueba los 5 escenarios end-to-end.
"""
import requests
import json
import sys
import time

# URL del webhook (local o producción)
WEBHOOK_URL = "http://localhost:8000/whatsapp/webhook"


def send_message(message_text: str, message_id: str = None) -> dict:
    """Envía un mensaje simulado al webhook."""
    if not message_id:
        message_id = f"wamid.test_{int(time.time() * 1000)}"
    
    payload = {
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
                                    "profile": {"name": "Test User"},
                                    "wa_id": "573142156486"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "573142156486",
                                    "id": message_id,
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": message_text}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return {
            "status": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text,
            "success": response.status_code == 200
        }
    except Exception as e:
        return {"status": 0, "response": str(e), "success": False}


def test_scenario_1():
    """Escenario 1: Industrial → precio → fotos"""
    print("=" * 70)
    print("ESCENARIO 1: Industrial → precio → fotos")
    print("=" * 70)
    print()
    
    steps = [
        ("Industrial", "Usuario indica tipo industrial"),
        ("Precio", "Usuario pregunta precio"),
        ("Tienes fotos?", "Usuario pide fotos")
    ]
    
    results = []
    for msg, desc in steps:
        print(f"📤 {desc}: '{msg}'")
        result = send_message(msg)
        results.append((msg, result))
        print(f"   Status: {result['status']}")
        print(f"   Response: {result['response']}")
        print()
        time.sleep(2)  # Pausa entre mensajes
    
    print("✅ Escenario 1 completado")
    print()
    return all(r[1]["success"] for r in results)


def test_scenario_2():
    """Escenario 2: Horarios → quiero pasar → ciudad distinta → disambiguación"""
    print("=" * 70)
    print("ESCENARIO 2: Horarios → quiero pasar → ciudad distinta → disambiguación")
    print("=" * 70)
    print()
    
    steps = [
        ("Horarios", "Usuario pregunta horarios"),
        ("Quiero pasar", "Usuario quiere visitar"),
        ("Montelíbano", "Usuario menciona ciudad distinta")
    ]
    
    results = []
    for msg, desc in steps:
        print(f"📤 {desc}: '{msg}'")
        result = send_message(msg)
        results.append((msg, result))
        print(f"   Status: {result['status']}")
        print(f"   Response: {result['response']}")
        print()
        time.sleep(2)
    
    print("✅ Escenario 2 completado")
    print()
    return all(r[1]["success"] for r in results)


def test_scenario_3():
    """Escenario 3: 'tienes fotos?' en medio de calificación"""
    print("=" * 70)
    print("ESCENARIO 3: 'tienes fotos?' en medio de calificación")
    print("=" * 70)
    print()
    
    steps = [
        ("Industrial", "Usuario indica tipo"),
        ("Gorras", "Usuario indica uso"),
        ("Tienes fotos?", "Usuario cambia de tema (fotos)")
    ]
    
    results = []
    for msg, desc in steps:
        print(f"📤 {desc}: '{msg}'")
        result = send_message(msg)
        results.append((msg, result))
        print(f"   Status: {result['status']}")
        print(f"   Response: {result['response']}")
        print()
        time.sleep(2)
    
    print("✅ Escenario 3 completado")
    print()
    return all(r[1]["success"] for r in results)


def test_scenario_4():
    """Escenario 4: 'garantía' y 'repuestos'"""
    print("=" * 70)
    print("ESCENARIO 4: 'garantía' y 'repuestos'")
    print("=" * 70)
    print()
    
    steps = [
        ("Garantía", "Usuario pregunta garantía"),
        ("Repuestos", "Usuario pregunta repuestos")
    ]
    
    results = []
    for msg, desc in steps:
        print(f"📤 {desc}: '{msg}'")
        result = send_message(msg)
        results.append((msg, result))
        print(f"   Status: {result['status']}")
        print(f"   Response: {result['response']}")
        print()
        time.sleep(2)
    
    print("✅ Escenario 4 completado")
    print()
    return all(r[1]["success"] for r in results)


def test_scenario_5():
    """Escenario 5: Usuario confuso ('no sé cuál') → recomendación con 2 opciones + CTA"""
    print("=" * 70)
    print("ESCENARIO 5: Usuario confuso → recomendación con opciones")
    print("=" * 70)
    print()
    
    steps = [
        ("Industrial", "Usuario indica tipo"),
        ("No sé cuál", "Usuario está confuso")
    ]
    
    results = []
    for msg, desc in steps:
        print(f"📤 {desc}: '{msg}'")
        result = send_message(msg)
        results.append((msg, result))
        print(f"   Status: {result['status']}")
        print(f"   Response: {result['response']}")
        print()
        time.sleep(2)
    
    print("✅ Escenario 5 completado")
    print()
    return all(r[1]["success"] for r in results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        WEBHOOK_URL = sys.argv[1]
        print(f"Usando URL: {WEBHOOK_URL}")
        print()
    
    print("🧪 EJECUTANDO SUITE DE PRUEBAS - Sales Dialogue Manager")
    print()
    
    results = []
    
    # Ejecutar todos los escenarios
    results.append(("Escenario 1", test_scenario_1()))
    results.append(("Escenario 2", test_scenario_2()))
    results.append(("Escenario 3", test_scenario_3()))
    results.append(("Escenario 4", test_scenario_4()))
    results.append(("Escenario 5", test_scenario_5()))
    
    # Resumen
    print("=" * 70)
    print("RESUMEN DE PRUEBAS")
    print("=" * 70)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(result[1] for result in results)
    print()
    if all_passed:
        print("✅ TODAS LAS PRUEBAS PASARON")
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
    
    sys.exit(0 if all_passed else 1)

