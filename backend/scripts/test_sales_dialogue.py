#!/usr/bin/env python3
"""
Script de prueba para el Sales Dialogue Manager.
Prueba los 5 casos nuevos: saludo humano, comprar máquina, ciudad, visita, agendamiento.
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


def test_case_1():
    """Caso 1: 'Hola' => saludo humano sin menú"""
    print("=" * 70)
    print("CASO 1: 'Hola' => saludo humano sin menú")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'Hola'")
    result = send_message("Hola")
    print(f"   Status: {result['status']}")
    response_str = json.dumps(result['response'])
    print(f"   Response: {response_str[:200]}")
    
    # Verificar que NO contiene menú numerado
    has_menu = "1)" in response_str and "2)" in response_str
    has_human_greeting = "Luisa" in response_str or "Almacén" in response_str or "El Sastre" in response_str
    
    print()
    if not has_menu and has_human_greeting:
        print("✅ PASS: Saludo humano sin menú")
        return True
    else:
        print("❌ FAIL: Contiene menú o no es saludo humano")
        return False


def test_case_2():
    """Caso 2: 'comprar máquina' => pregunta correcta"""
    print("=" * 70)
    print("CASO 2: 'comprar máquina' => pregunta correcta")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'comprar máquina'")
    result = send_message("comprar máquina")
    print(f"   Status: {result['status']}")
    response_str = json.dumps(result['response'])
    print(f"   Response: {response_str[:200]}")
    
    # Verificar que pregunta por tipo
    has_question = "?" in response_str
    has_machine_type = "familiar" in response_str.lower() or "industrial" in response_str.lower()
    
    print()
    if has_question and has_machine_type:
        print("✅ PASS: Pregunta correcta sobre tipo de máquina")
        return True
    else:
        print("❌ FAIL: No pregunta correctamente")
        return False


def test_case_3():
    """Caso 3: 'Montelibano' => city_filled y NO repregunta ciudad"""
    print("=" * 70)
    print("CASO 3: 'Montelibano' => city_filled y NO repregunta ciudad")
    print("=" * 70)
    print()
    
    steps = [
        ("Industrial", "Usuario indica tipo"),
        ("Montelíbano", "Usuario da ciudad")
    ]
    
    results = []
    for msg, desc in steps:
        print(f"📤 {desc}: '{msg}'")
        result = send_message(msg)
        results.append((msg, result))
        print(f"   Status: {result['status']}")
        response_str = json.dumps(result['response'])
        print(f"   Response: {response_str[:150]}")
        print()
        time.sleep(2)
    
    # Verificar que después de dar ciudad, NO pregunta ciudad de nuevo
    last_response = json.dumps(results[-1][1]['response'])
    asks_city_again = "ciudad" in last_response.lower() and "?" in last_response
    
    print()
    if not asks_city_again:
        print("✅ PASS: NO repregunta ciudad después de darla")
        return True
    else:
        print("❌ FAIL: Repregunta ciudad")
        return False


def test_case_4():
    """Caso 4: 'puedo visitar la tienda? donde queda?' => responde dirección/horarios + pregunta hoy/mañana, sin handoff"""
    print("=" * 70)
    print("CASO 4: Visita => dirección/horarios + pregunta hoy/mañana, sin handoff")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'puedo visitar la tienda? donde queda?'")
    result = send_message("puedo visitar la tienda? donde queda?")
    print(f"   Status: {result['status']}")
    response_str = json.dumps(result['response'])
    print(f"   Response: {response_str}")
    
    # Verificar que contiene dirección/horarios
    has_address = "Calle 34" in response_str or "Montería" in response_str
    has_hours = "9am" in response_str or "horario" in response_str.lower()
    asks_when = "hoy" in response_str.lower() or "mañana" in response_str.lower() or "mañana" in response_str.lower()
    no_handoff = "handoff" not in response_str.lower() and "escalar" not in response_str.lower()
    
    print()
    if has_address and has_hours and asks_when and no_handoff:
        print("✅ PASS: Responde dirección/horarios y pregunta cuándo, sin handoff")
        return True
    else:
        print("❌ FAIL: No responde correctamente o hace handoff")
        return False


def test_case_5():
    """Caso 5: Usuario responde 'sí' a llamada/cita => pide datos (no dead-end)"""
    print("=" * 70)
    print("CASO 5: 'sí' a llamada/cita => pide datos (no dead-end)")
    print("=" * 70)
    print()
    
    steps = [
        ("puedo visitar?", "Usuario pregunta por visita"),
        ("mañana", "Usuario responde cuándo"),
        ("sí", "Usuario confirma llamada")
    ]
    
    results = []
    for msg, desc in steps:
        print(f"📤 {desc}: '{msg}'")
        result = send_message(msg)
        results.append((msg, result))
        print(f"   Status: {result['status']}")
        response_str = json.dumps(result['response'])
        print(f"   Response: {response_str[:200]}")
        print()
        time.sleep(2)
    
    # Verificar que después de "sí", pide más datos o confirma
    last_response = json.dumps(results[-1][1]['response'])
    has_followup = "?" in last_response or "llamamos" in last_response.lower() or "confirmar" in last_response.lower()
    
    print()
    if has_followup:
        print("✅ PASS: Pide datos o confirma (no dead-end)")
        return True
    else:
        print("❌ FAIL: Dead-end (no hay seguimiento)")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        WEBHOOK_URL = sys.argv[1]
        print(f"Usando URL: {WEBHOOK_URL}")
        print()
    
    print("🧪 EJECUTANDO SUITE DE PRUEBAS - Sales Dialogue Manager (Versión Humana)")
    print()
    
    results = []
    
    # Ejecutar todos los casos
    results.append(("Caso 1: Hola => saludo humano", test_case_1()))
    print()
    time.sleep(2)
    
    results.append(("Caso 2: comprar máquina => pregunta", test_case_2()))
    print()
    time.sleep(2)
    
    results.append(("Caso 3: Montelibano => NO repregunta ciudad", test_case_3()))
    print()
    time.sleep(2)
    
    results.append(("Caso 4: Visita => dirección sin handoff", test_case_4()))
    print()
    time.sleep(2)
    
    results.append(("Caso 5: sí a llamada => pide datos", test_case_5()))
    print()
    
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
