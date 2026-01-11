#!/usr/bin/env python3
"""
Script de pruebas para activación de OpenAI en producción.
Ejecuta los 8 mensajes del plan de pruebas y genera un reporte.
"""
import sys
import json
import time
import httpx
from typing import Dict, Any, List, Tuple
from datetime import datetime
import subprocess

# URL del webhook (local o producción)
WEBHOOK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/whatsapp/webhook"
TEST_PHONE = "573142156486"  # Número de prueba
BASE_URL = WEBHOOK_URL.replace("/whatsapp/webhook", "")


def send_test_message(text: str, phone: str = TEST_PHONE, message_id: str = None) -> Dict[str, Any]:
    """Envía mensaje de prueba al webhook."""
    if not message_id:
        message_id = f"wamid.test_{int(time.time() * 1000)}_{hash(text) % 10000}"
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1357466656541301",  # WABA ID
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551380876",
                        "phone_number_id": "996869753500859"
                    },
                    "contacts": [{
                        "profile": {"name": "Test User"},
                        "wa_id": phone
                    }],
                    "messages": [{
                        "from": phone,
                        "id": message_id,
                        "timestamp": str(int(time.time())),
                        "type": "text",
                        "text": {"body": text}
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    start_time = time.perf_counter()
    try:
        response = httpx.post(WEBHOOK_URL, json=payload, timeout=30.0)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            "status": response.status_code,
            "response": response.json() if response.status_code == 200 else {},
            "message_id": message_id,
            "elapsed_ms": round(elapsed_ms, 1),
            "success": response.status_code == 200
        }
    except Exception as e:
        return {
            "status": 500,
            "error": str(e),
            "message_id": message_id,
            "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 1),
            "success": False
        }


def get_logs(last_n: int = 50) -> List[str]:
    """Obtiene los últimos logs del backend."""
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--tail", str(last_n), "backend"],
            capture_output=True,
            text=True,
            cwd="/Users/camilope/AI-Agents/Sastre"
        )
        return result.stdout.split("\n") if result.returncode == 0 else []
    except:
        return []


def check_health() -> Tuple[bool, Dict[str, Any]]:
    """Verifica health check."""
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        return response.status_code == 200, response.json() if response.status_code == 200 else {}
    except:
        return False, {}


def parse_log_event(log_line: str) -> Dict[str, Any]:
    """Intenta parsear un log JSON."""
    try:
        # Buscar JSON en la línea
        start = log_line.find("{")
        end = log_line.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = log_line[start:end]
            return json.loads(json_str)
    except:
        pass
    return {}


# Plan de pruebas (8 mensajes)
TEST_PLAN = [
    {
        "id": 1,
        "name": "Saludo",
        "message": "Hola",
        "expected_logs": ["message_received", "Mensaje WhatsApp procesado y respondido"],
        "expected_intent": "saludo",
        "expected_openai": False,
        "max_response_time_ms": 2000
    },
    {
        "id": 2,
        "name": "Intención Clara (Máquina Industrial)",
        "message": "Quiero una máquina industrial para gorras",
        "expected_logs": ["message_received", "Mensaje WhatsApp procesado y respondido"],
        "expected_intent": "buscar_maquina_industrial",
        "expected_openai": None,  # Puede ser true o false
        "max_response_time_ms": 3000
    },
    {
        "id": 3,
        "name": "Objeción de Precio (DEBE usar OpenAI)",
        "message": "Está muy caro, no tengo ese presupuesto",
        "expected_logs": ["message_received", "llm_decision_made", "LLM Adapter usado exitosamente", "Mensaje WhatsApp procesado y respondido"],
        "expected_intent": None,  # Puede variar
        "expected_openai": True,
        "expected_task_type": "objecion",
        "max_response_time_ms": 5000
    },
    {
        "id": 4,
        "name": "Pregunta Ambigua (DEBE usar OpenAI)",
        "message": "No sé qué máquina me conviene",
        "expected_logs": ["message_received", "llm_decision_made", "LLM Adapter usado exitosamente", "Mensaje WhatsApp procesado y respondido"],
        "expected_intent": None,  # Puede variar
        "expected_openai": True,
        "expected_task_type": "consulta_compleja",
        "max_response_time_ms": 5000
    },
    {
        "id": 5,
        "name": "Caso Técnico (Ruido, Hilo se Rompe)",
        "message": "Mi máquina hace mucho ruido y el hilo se rompe constantemente",
        "expected_logs": ["message_received", "Mensaje WhatsApp procesado y respondido"],
        "expected_intent": "soporte_tecnico",
        "expected_openai": False,
        "max_response_time_ms": 3000
    },
    {
        "id": 6,
        "name": "Handoff 'Sí' (FIX P0 - nunca silencio)",
        "message": "Sí, llámenme",
        "expected_logs": ["message_received", "Mensaje registrado en modo HUMAN_ACTIVE", "reply_sent_in_human_active"],
        "expected_intent": None,
        "expected_openai": False,
        "max_response_time_ms": 2000,
        "note": "Este mensaje requiere un handoff previo. Si no hay handoff, puede fallar."
    },
    {
        "id": 7,
        "name": "Follow-up 'Hola' Después de Handoff",
        "message": "Hola",
        "expected_logs": ["message_received", "Mensaje registrado en modo HUMAN_ACTIVE", "reply_sent_in_human_active"],
        "expected_intent": None,
        "expected_openai": False,
        "max_response_time_ms": 2000,
        "note": "Este mensaje requiere que estemos en HUMAN_ACTIVE (del mensaje 6)."
    },
    {
        "id": 8,
        "name": "Prueba de Fallback (Límite Excedido)",
        "message": "Tengo otra objeción sobre el precio",
        "expected_logs": ["message_received", "llm_decision_made", "LLM Adapter: Límite de llamadas excedido", "LLM Adapter fallback usado"],
        "expected_intent": None,
        "expected_openai": False,  # Fallback, no OpenAI real
        "max_response_time_ms": 2000,
        "note": "Este mensaje requiere 4 llamadas previas a OpenAI (mensajes 3, 4 y 2 más)."
    }
]


def run_tests() -> Dict[str, Any]:
    """Ejecuta todas las pruebas y genera reporte."""
    print("=" * 80)
    print("PRUEBAS DE ACTIVACIÓN OPENAI - LUISA")
    print("=" * 80)
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Base URL: {BASE_URL}")
    print(f"Fecha: {datetime.now().isoformat()}")
    print("=" * 80)
    print()
    
    # Verificar health check
    print("Verificando health check...")
    health_ok, health_data = check_health()
    if not health_ok:
        print("❌ Health check falló. Abortando pruebas.")
        return {"error": "Health check falló"}
    print("✅ Health check OK")
    print()
    
    results = []
    logs_before = get_logs(100)
    
    for test_case in TEST_PLAN:
        print(f"Prueba {test_case['id']}: {test_case['name']}")
        print(f"  Mensaje: '{test_case['message']}'")
        
        # Enviar mensaje
        result = send_test_message(test_case['message'], TEST_PHONE)
        
        # Esperar procesamiento
        time.sleep(2)
        
        # Obtener logs nuevos
        logs_after = get_logs(200)
        new_logs = logs_after[len(logs_before):] if len(logs_after) > len(logs_before) else logs_after
        
        # Analizar logs
        log_events = {}
        for log_line in new_logs:
            event = parse_log_event(log_line)
            if event and "message" in event:
                msg = event["message"]
                log_events[msg] = event
        
        # Validar resultados
        test_result = {
            "test_id": test_case['id'],
            "name": test_case['name'],
            "message": test_case['message'],
            "webhook_response": result,
            "log_events": log_events,
            "validations": {}
        }
        
        # Validación 1: Webhook respondió correctamente
        test_result["validations"]["webhook_ok"] = result["success"]
        if not result["success"]:
            print(f"  ❌ Webhook falló: {result.get('error', 'unknown')}")
        else:
            print(f"  ✅ Webhook OK (status {result['status']}, {result['elapsed_ms']}ms)")
        
        # Validación 2: Tiempo de respuesta
        if result["elapsed_ms"] <= test_case["max_response_time_ms"]:
            test_result["validations"]["response_time_ok"] = True
            print(f"  ✅ Tiempo de respuesta OK ({result['elapsed_ms']}ms < {test_case['max_response_time_ms']}ms)")
        else:
            test_result["validations"]["response_time_ok"] = False
            print(f"  ⚠️  Tiempo de respuesta lento ({result['elapsed_ms']}ms > {test_case['max_response_time_ms']}ms)")
        
        # Validación 3: Logs esperados
        missing_logs = []
        for expected_log in test_case["expected_logs"]:
            found = any(expected_log in msg for msg in log_events.keys())
            if not found:
                missing_logs.append(expected_log)
        
        if not missing_logs:
            test_result["validations"]["all_logs_present"] = True
            print(f"  ✅ Todos los logs esperados presentes")
        else:
            test_result["validations"]["all_logs_present"] = False
            test_result["validations"]["missing_logs"] = missing_logs
            print(f"  ⚠️  Logs faltantes: {', '.join(missing_logs)}")
        
        # Validación 4: OpenAI usado correctamente
        if test_case["expected_openai"] is not None:
            openai_used = False
            if "LLM Adapter usado exitosamente" in log_events:
                openai_used = True
            elif "llm_decision_made" in log_events and "LLM Adapter: Límite de llamadas excedido" not in log_events:
                # Si se decidió usar OpenAI pero no se excedió límite, debería haberse usado
                openai_used = True
            
            if test_case["expected_openai"] == openai_used:
                test_result["validations"]["openai_usage_correct"] = True
                print(f"  ✅ OpenAI usado correctamente (esperado: {test_case['expected_openai']}, actual: {openai_used})")
            else:
                test_result["validations"]["openai_usage_correct"] = False
                print(f"  ❌ OpenAI uso incorrecto (esperado: {test_case['expected_openai']}, actual: {openai_used})")
        
        # Validación 5: Task type si se espera
        if "expected_task_type" in test_case:
            task_type_found = False
            for event_name, event_data in log_events.items():
                if event_data.get("task_type") == test_case["expected_task_type"]:
                    task_type_found = True
                    break
            
            if task_type_found:
                test_result["validations"]["task_type_correct"] = True
                print(f"  ✅ Task type correcto ({test_case['expected_task_type']})")
            else:
                test_result["validations"]["task_type_correct"] = False
                print(f"  ⚠️  Task type no encontrado (esperado: {test_case['expected_task_type']})")
        
        # Validación 6: Intent si se espera
        if test_case["expected_intent"]:
            intent_found = False
            for event_name, event_data in log_events.items():
                if event_data.get("intent") == test_case["expected_intent"]:
                    intent_found = True
                    break
            
            if intent_found:
                test_result["validations"]["intent_correct"] = True
                print(f"  ✅ Intent correcto ({test_case['expected_intent']})")
            else:
                test_result["validations"]["intent_correct"] = False
                print(f"  ⚠️  Intent no encontrado (esperado: {test_case['expected_intent']})")
        
        results.append(test_result)
        
        # Nota si existe
        if "note" in test_case:
            print(f"  📝 Nota: {test_case['note']}")
        
        print()
        logs_before = logs_after
        
        # Esperar entre pruebas
        if test_case['id'] < len(TEST_PLAN):
            time.sleep(1)
    
    # Resumen
    print("=" * 80)
    print("RESUMEN DE PRUEBAS")
    print("=" * 80)
    
    total = len(results)
    passed = sum(1 for r in results if all(
        r["validations"].get(k, False) for k in ["webhook_ok", "response_time_ok", "all_logs_present"]
    ))
    
    print(f"Total de pruebas: {total}")
    print(f"Pruebas exitosas: {passed}")
    print(f"Pruebas con problemas: {total - passed}")
    print()
    
    # Detalles por prueba
    for result in results:
        status = "✅" if all(
            result["validations"].get(k, False) for k in ["webhook_ok", "response_time_ok", "all_logs_present"]
        ) else "❌"
        print(f"{status} Prueba {result['test_id']}: {result['name']}")
        if not result["validations"].get("webhook_ok"):
            print(f"   - Webhook falló")
        if not result["validations"].get("response_time_ok"):
            print(f"   - Tiempo de respuesta lento")
        if not result["validations"].get("all_logs_present"):
            print(f"   - Logs faltantes: {', '.join(result['validations'].get('missing_logs', []))}")
    
    print("=" * 80)
    
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    report = run_tests()
    
    # Guardar reporte en archivo
    report_file = f"/Users/camilope/AI-Agents/Sastre/reporte_pruebas_openai_{int(time.time())}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nReporte guardado en: {report_file}")
    print()

