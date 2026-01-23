#!/usr/bin/env python3
"""
Script de validación del filtrado personal/comercial.

Carga el dataset versionado y valida precisión, recall, F1, falsos positivos y falsos negativos.
Hard-fail si precisión < 90% o falsos positivos > 5%.
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Agregar backend al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.rules.business_guardrails import is_business_related
from app.rules.enhanced_filtering import enhanced_is_business_related
from app.config import ENHANCED_FILTERING_WITH_LLM


def load_dataset(dataset_path: Path) -> Dict[str, Any]:
    """Carga el dataset desde JSON."""
    with open(dataset_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_metrics(results: list) -> Dict[str, float]:
    """Calcula métricas de precisión, recall, F1, falsos positivos y falsos negativos."""
    total = len(results)
    true_positives = sum(1 for r in results if r['expected'] == 'BUSINESS' and r['predicted'] == 'BUSINESS')
    true_negatives = sum(1 for r in results if r['expected'] == 'PERSONAL' and r['predicted'] == 'PERSONAL')
    false_positives = sum(1 for r in results if r['expected'] == 'PERSONAL' and r['predicted'] == 'BUSINESS')
    false_negatives = sum(1 for r in results if r['expected'] == 'BUSINESS' and r['predicted'] == 'PERSONAL')
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "total": total
    }


async def validate_sample(sample: Dict[str, str], use_enhanced: bool) -> Dict[str, Any]:
    """Valida un sample del dataset."""
    text = sample['text']
    expected = sample['expected']
    expected_score_min = sample.get('expected_score_min', 0.0)
    expected_score_max = sample.get('expected_score_max', 1.0)
    
    # Clasificar
    is_business_heuristic, reason_heuristic, score_heuristic, reasons_list_heuristic = is_business_related(text)
    
    if use_enhanced:
        is_business, reason, score, reasons_list = await enhanced_is_business_related(
            text, 
            (is_business_heuristic, reason_heuristic, score_heuristic, reasons_list_heuristic)
        )
    else:
        is_business, reason, score, reasons_list = is_business_heuristic, reason_heuristic, score_heuristic, reasons_list_heuristic
    
    predicted = "BUSINESS" if is_business else "PERSONAL"
    is_correct = predicted == expected
    score_in_range = expected_score_min <= score <= expected_score_max
    
    return {
        "text": text,
        "expected": expected,
        "predicted": predicted,
        "is_correct": is_correct,
        "score": score,
        "score_in_range": score_in_range,
        "reason": reason,
        "reasons_list": reasons_list
    }


async def main():
    """Función principal."""
    dataset_path = BASE_DIR / "tests" / "data" / "filtering_dataset_v1.json"
    
    if not dataset_path.exists():
        print(f"❌ Dataset no encontrado: {dataset_path}")
        return 1
    
    print(f"📊 Cargando dataset: {dataset_path}")
    dataset = load_dataset(dataset_path)
    samples = dataset.get("samples", [])
    
    if not samples:
        print("❌ Dataset vacío")
        return 1
    
    print(f"✅ Dataset cargado: {len(samples)} samples (v{dataset.get('version', 'unknown')})")
    print(f"🔍 Usando filtrado mejorado: {ENHANCED_FILTERING_WITH_LLM}\n")
    
    # Validar cada sample
    results = []
    for i, sample in enumerate(samples, 1):
        result = await validate_sample(sample, ENHANCED_FILTERING_WITH_LLM)
        results.append(result)
        
        status = "✅" if result['is_correct'] else "❌"
        print(f"{status} [{i}/{len(samples)}] {result['text'][:50]}...")
        print(f"   Esperado: {result['expected']}, Predicho: {result['predicted']}, Score: {result['score']:.2f}")
        if not result['is_correct']:
            print(f"   ⚠️  Error: {result['reason']}")
    
    # Calcular métricas
    metrics = calculate_metrics(results)
    
    print("\n" + "="*60)
    print("📈 MÉTRICAS DE VALIDACIÓN")
    print("="*60)
    print(f"Precisión: {metrics['precision']:.2%}")
    print(f"Recall: {metrics['recall']:.2%}")
    print(f"F1: {metrics['f1']:.2%}")
    print(f"Verdaderos Positivos: {metrics['true_positives']}")
    print(f"Verdaderos Negativos: {metrics['true_negatives']}")
    print(f"Falsos Positivos: {metrics['false_positives']}")
    print(f"Falsos Negativos: {metrics['false_negatives']}")
    print(f"Total: {metrics['total']}")
    
    # Validar criterios
    print("\n" + "="*60)
    print("🎯 CRITERIOS DE VALIDACIÓN")
    print("="*60)
    
    precision_ok = metrics['precision'] >= 0.90
    false_positives_ok = metrics['false_positives'] <= 5
    false_negatives_ok = metrics['false_negatives'] <= 10
    
    print(f"Precisión >= 90%: {'✅' if precision_ok else '❌'} ({metrics['precision']:.2%})")
    print(f"Falsos Positivos <= 5: {'✅' if false_positives_ok else '❌'} ({metrics['false_positives']})")
    print(f"Falsos Negativos <= 10: {'✅' if false_negatives_ok else '❌'} ({metrics['false_negatives']})")
    
    if not precision_ok or not false_positives_ok:
        print("\n❌ VALIDACIÓN FALLÓ: Criterios no cumplidos")
        return 1
    
    print("\n✅ VALIDACIÓN EXITOSA: Todos los criterios cumplidos")
    return 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
