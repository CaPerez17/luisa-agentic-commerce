#!/usr/bin/env python3
"""
Script de prueba para el sistema de triage.
Prueba los 5 casos requeridos.
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
    """Caso 1: input 'Hola' => respuesta contiene menú 1-4 y stage=triage"""
    print("=" * 70)
    print("CASO 1: 'Hola' => menú triage")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'Hola'")
    result = send_message("Hola")
    print(f"   Status: {result['status']}")
    print(f"   Response: {result['response']}")
    
    # Verificar que contiene menú
    response_str = json.dumps(result['response'])
    has_menu = "1)" in response_str or "1)" in str(result['response'])
    has_triage = "Comprar máquina" in response_str or "repuestos" in response_str.lower()
    
    print()
    if has_menu and has_triage:
        print("✅ PASS: Respuesta contiene menú triage")
        return True
    else:
        print("❌ FAIL: Respuesta no contiene menú triage")
        print(f"   has_menu: {has_menu}, has_triage: {has_triage}")
        return False


def test_case_2():
    """Caso 2: input 'Precio' => NO triage; va a pricing (reglas)"""
    print("=" * 70)
    print("CASO 2: 'Precio' => NO triage, va a pricing")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'Precio'")
    result = send_message("Precio")
    print(f"   Status: {result['status']}")
    print(f"   Response: {result['response']}")
    
    # Verificar que NO contiene menú triage
    response_str = json.dumps(result['response'])
    has_triage_menu = "1)" in response_str and "2)" in response_str
    has_pricing = "precio" in response_str.lower() or "$" in response_str
    
    print()
    if not has_triage_menu and has_pricing:
        print("✅ PASS: Respuesta NO contiene triage, va directo a pricing")
        return True
    else:
        print("❌ FAIL: Respuesta contiene triage o no va a pricing")
        print(f"   has_triage_menu: {has_triage_menu}, has_pricing: {has_pricing}")
        return False


def test_case_3():
    """Caso 3: input 'Repuestos' => route a spare_parts y pregunta correcta"""
    print("=" * 70)
    print("CASO 3: 'Repuestos' => spare_parts")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'Repuestos'")
    result = send_message("Repuestos")
    print(f"   Status: {result['status']}")
    print(f"   Response: {result['response']}")
    
    # Verificar que pregunta por marca/modelo o foto
    response_str = json.dumps(result['response'])
    has_spare_parts = "repuesto" in response_str.lower()
    has_question = "marca" in response_str.lower() or "placa" in response_str.lower() or "foto" in response_str.lower()
    
    print()
    if has_spare_parts and has_question:
        print("✅ PASS: Respuesta routea a spare_parts y pregunta marca/placa")
        return True
    else:
        print("❌ FAIL: Respuesta no routea correctamente a spare_parts")
        print(f"   has_spare_parts: {has_spare_parts}, has_question: {has_question}")
        return False


def test_case_4():
    """Caso 4: input 'Garantía' => tech_support"""
    print("=" * 70)
    print("CASO 4: 'Garantía' => tech_support")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'Garantía'")
    result = send_message("Garantía")
    print(f"   Status: {result['status']}")
    print(f"   Response: {result['response']}")
    
    # Verificar que responde sobre garantía
    response_str = json.dumps(result['response'])
    has_guarantee = "garantía" in response_str.lower() or "garantia" in response_str.lower()
    has_info = "meses" in response_str.lower() or "3" in response_str
    
    print()
    if has_guarantee and has_info:
        print("✅ PASS: Respuesta routea a tech_support (garantía)")
        return True
    else:
        print("❌ FAIL: Respuesta no routea correctamente a tech_support")
        print(f"   has_guarantee: {has_guarantee}, has_info: {has_info}")
        return False


def test_case_5():
    """Caso 5: input 'Quiero montar un negocio de gorras' => business_advice"""
    print("=" * 70)
    print("CASO 5: 'Quiero montar un negocio de gorras' => business_advice")
    print("=" * 70)
    print()
    
    print("📤 Enviando: 'Quiero montar un negocio de gorras'")
    result = send_message("Quiero montar un negocio de gorras")
    print(f"   Status: {result['status']}")
    print(f"   Response: {result['response']}")
    
    # Verificar que responde sobre asesoría de negocio
    response_str = json.dumps(result['response'])
    has_advice = "gorra" in response_str.lower() or "industrial" in response_str.lower() or "recomiendo" in response_str.lower()
    has_question = "?" in response_str
    
    print()
    if has_advice and has_question:
        print("✅ PASS: Respuesta routea a business_advice")
        return True
    else:
        print("❌ FAIL: Respuesta no routea correctamente a business_advice")
        print(f"   has_advice: {has_advice}, has_question: {has_question}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        WEBHOOK_URL = sys.argv[1]
        print(f"Usando URL: {WEBHOOK_URL}")
        print()
    
    print("🧪 EJECUTANDO SUITE DE PRUEBAS - Triage System")
    print()
    
    results = []
    
    # Ejecutar todos los casos
    results.append(("Caso 1: Hola => triage", test_case_1()))
    print()
    time.sleep(2)
    
    results.append(("Caso 2: Precio => NO triage", test_case_2()))
    print()
    time.sleep(2)
    
    results.append(("Caso 3: Repuestos => spare_parts", test_case_3()))
    print()
    time.sleep(2)
    
    results.append(("Caso 4: Garantía => tech_support", test_case_4()))
    print()
    time.sleep(2)
    
    results.append(("Caso 5: Negocio gorras => business_advice", test_case_5()))
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

