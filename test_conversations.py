#!/usr/bin/env python3
"""
Script de prueba automática de flujos conversacionales de Luisa
Simula conversaciones completas y evalúa si conducen a cierre o escalamiento
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.main import generate_response, extract_context_from_history, is_ready_for_close, analyze_message

def evaluate_response(response: str, turn: int) -> dict:
    """Evalúa si una respuesta de Luisa cumple los criterios"""
    response_lower = response.lower()
    
    # Verificar frases prohibidas
    forbidden_phrases = [
        "cuéntame más", "qué necesitas", "dime más detalles",
        "trabajamos con", "ofrecemos", "cuéntame", "dime más"
    ]
    has_forbidden = any(phrase in response_lower for phrase in forbidden_phrases)
    
    # Verificar afirmación técnica
    technical_terms = [
        "recta industrial", "mecatrónica", "telas", "costura",
        "producción", "máquina", "industrial", "familiar"
    ]
    has_technical = any(term in response_lower for term in technical_terms)
    
    # Verificar pregunta cerrada (tiene "?" y opciones limitadas)
    has_question = "?" in response
    has_options = any(word in response_lower for word in ["o", "entre", "cuál", "qué"])
    
    # Verificar preparación de cierre
    has_close_prep = any(word in response_lower for word in [
        "ciudad", "envío", "recomiendo", "te recomiendo", "conectarte"
    ])
    
    return {
        "has_forbidden": has_forbidden,
        "has_technical": has_technical,
        "has_question": has_question,
        "has_options": has_options,
        "has_close_prep": has_close_prep,
        "is_closing": has_close_prep and "ciudad" in response_lower
    }

def simulate_conversation(scenario_name: str, messages: list) -> dict:
    """Simula una conversación completa"""
    history = []
    results = {
        "scenario": scenario_name,
        "turns": [],
        "status": "IN_PROGRESS",
        "final_turn": None,
        "issues": []
    }
    
    for turn, message in enumerate(messages, 1):
        # Agregar mensaje del cliente al historial
        history.append({"text": message, "sender": "customer", "timestamp": f"turn_{turn}"})
        
        # Generar respuesta de Luisa
        analysis = analyze_message(message, history)
        response = generate_response(message, history, analysis["needs_escalation"])
        
        # Agregar respuesta de Luisa al historial
        history.append({"text": response, "sender": "luisa", "timestamp": f"turn_{turn}_response"})
        
        # Evaluar respuesta
        evaluation = evaluate_response(response, turn)
        
        turn_result = {
            "turn": turn,
            "customer": message,
            "luisa": response,
            "evaluation": evaluation,
            "needs_escalation": analysis["needs_escalation"],
            "priority": analysis.get("priority", "low")
        }
        
        results["turns"].append(turn_result)
        
        # Verificar problemas
        if evaluation["has_forbidden"]:
            results["issues"].append(f"Turno {turn}: Contiene frase prohibida")
        
        if not evaluation["has_technical"] and turn > 1:
            results["issues"].append(f"Turno {turn}: Falta afirmación técnica")
        
        if turn > 1 and not evaluation["has_question"]:
            results["issues"].append(f"Turno {turn}: Falta pregunta cerrada")
        
        # Verificar si llegó a cierre
        if evaluation["is_closing"] or analysis["needs_escalation"]:
            results["status"] = "CLOSED"
            results["final_turn"] = turn
            break
        
        # Verificar estancamiento (2 turnos sin avanzar)
        if turn >= 2:
            prev_eval = results["turns"][-2]["evaluation"]
            if not prev_eval["has_close_prep"] and not evaluation["has_close_prep"]:
                if turn >= 6:
                    results["issues"].append(f"Estancamiento detectado en turno {turn}")
        
        # Límite de turnos
        if turn >= 8:
            results["status"] = "STALLED"
            results["issues"].append("Conversación excedió 8 turnos sin cierre")
            break
    
    return results

# ESCENARIOS DE PRUEBA (conversaciones completas simuladas)
scenarios = [
    {
        "name": "Precio desde Facebook - Wilcox",
        "messages": [
            "Precio de la Wilcox",
            "Para ropa",
            "Producción constante",
            "Bogotá"
        ]
    },
    {
        "name": "Emprendimiento sin claridad",
        "messages": [
            "Qué máquina me recomiendas para empezar",
            "Ropa",
            "Constante",
            "Medellín"
        ]
    },
    {
        "name": "Uso específico - Gorras",
        "messages": [
            "Quiero una máquina industrial para gorras",
            "Producción constante",
            "Cali"
        ]
    },
    {
        "name": "Cliente caliente - Producción continua",
        "messages": [
            "La necesito para taller y producción continua",
            "Gorras",
            "Montería"
        ]
    },
    {
        "name": "Acción crítica - Pago",
        "messages": [
            "Ya hice el pago"
        ]
    }
]

if __name__ == "__main__":
    print("="*80)
    print("PRUEBAS AUTOMÁTICAS DE FLUJOS CONVERSACIONALES - LUISA")
    print("="*80)
    print()
    
    all_results = []
    
    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"ESCENARIO: {scenario['name']}")
        print(f"{'='*80}")
        
        result = simulate_conversation(scenario["name"], scenario["messages"])
        all_results.append(result)
        
        # Mostrar conversación
        for turn_result in result["turns"]:
            print(f"\nTurno {turn_result['turn']}:")
            print(f"  Cliente: {turn_result['customer']}")
            print(f"  Luisa: {turn_result['luisa']}")
            print(f"  Evaluación: Técnica={turn_result['evaluation']['has_technical']}, "
                  f"Pregunta={turn_result['evaluation']['has_question']}, "
                  f"Cierre={turn_result['evaluation']['is_closing']}")
            if turn_result["needs_escalation"]:
                print(f"  ⚠️  ESCALAMIENTO: {turn_result['priority']}")
        
        # Mostrar resultado
        print(f"\n{'─'*80}")
        print(f"RESULTADO: {result['status']}")
        if result["final_turn"]:
            print(f"Turnos hasta cierre: {result['final_turn']}")
        if result["issues"]:
            print(f"PROBLEMAS DETECTADOS:")
            for issue in result["issues"]:
                print(f"  ❌ {issue}")
        else:
            print("✅ Sin problemas detectados")
    
    # Resumen final
    print(f"\n\n{'='*80}")
    print("RESUMEN FINAL")
    print(f"{'='*80}")
    
    passed = sum(1 for r in all_results if r["status"] == "CLOSED" and not r["issues"])
    failed = len(all_results) - passed
    
    print(f"Escenarios probados: {len(all_results)}")
    print(f"✅ Pasados: {passed}")
    print(f"❌ Fallidos: {failed}")
    
    for result in all_results:
        status_icon = "✅" if result["status"] == "CLOSED" and not result["issues"] else "❌"
        print(f"{status_icon} {result['scenario']}: {result['status']}")

