#!/usr/bin/env python3
"""
Analizador de trazas de interaction_traces.
Genera reporte completo de métricas, auditoría y calidad.
"""
import sqlite3
import sys
import statistics
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Any


class TraceAnalyzer:
    """Analizador de trazas de interacción."""

    def __init__(self, db_path: str = "luisa.db"):
        self.db_path = db_path
        self.traces = []
        self.load_traces()

    def load_traces(self, limit: int = 80) -> None:
        """Carga las últimas N trazas."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM interaction_traces
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        self.traces = [dict(row) for row in cursor.fetchall()]
        conn.close()

        print(f"📊 Cargadas {len(self.traces)} trazas recientes")

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calcula métricas principales."""
        if not self.traces:
            return {}

        total = len(self.traces)

        # Métricas básicas
        openai_called = sum(1 for t in self.traces if t.get('openai_called', 0))
        business_related = sum(1 for t in self.traces if t.get('business_related', 1))
        cache_hits = sum(1 for t in self.traces if t.get('cache_hit', 0))

        # Latencias
        latencies_ms = [t.get('latency_ms', 0) for t in self.traces if t.get('latency_ms', 0) > 0]
        latencies_us = [t.get('latency_us', 0) for t in self.traces if t.get('latency_us', 0) > 0]

        # Top intents y teams
        intents = Counter(t.get('intent', '') for t in self.traces if t.get('intent'))
        routed_teams = Counter(t.get('routed_team', '') for t in self.traces if t.get('routed_team'))

        return {
            'total_interacciones': total,
            'openai_called_percent': round((openai_called / total) * 100, 1) if total > 0 else 0,
            'business_related_percent': round((business_related / total) * 100, 1) if total > 0 else 0,
            'cache_hit_percent': round((cache_hits / total) * 100, 1) if total > 0 else 0,
            'latencies_ms': {
                'count': len(latencies_ms),
                'avg': round(statistics.mean(latencies_ms), 1) if latencies_ms else 0,
                'median': round(statistics.median(latencies_ms), 1) if latencies_ms else 0,
                'p95': round(sorted(latencies_ms)[int(len(latencies_ms) * 0.95)] if latencies_ms else 0, 1),
                'min': min(latencies_ms) if latencies_ms else 0,
                'max': max(latencies_ms) if latencies_ms else 0
            },
            'latencies_us': {
                'count': len(latencies_us),
                'avg': round(statistics.mean(latencies_us), 0) if latencies_us else 0,
                'median': round(statistics.median(latencies_us), 0) if latencies_us else 0
            },
            'top_intents': intents.most_common(10),
            'top_routed_teams': routed_teams.most_common(5)
        }

    def audit_costs(self) -> Dict[str, Any]:
        """Auditoría de costos de OpenAI."""
        openai_called_traces = [t for t in self.traces if t.get('openai_called', 0)]

        # Casos donde OpenAI se llamó pero no debería
        wasteful_calls = []
        for trace in openai_called_traces:
            intent = trace.get('intent', '').lower()
            text = trace.get('raw_text', '').lower()

            # Reglas de auditoría
            should_not_call = (
                intent in ['saludo', 'cierre', 'despedida', 'info_general'] or
                'hola' in text or 'gracias' in text or
                'horario' in text or 'direccion' in text or
                'ubicacion' in text or 'telefono' in text
            )

            if should_not_call:
                wasteful_calls.append({
                    'id': trace.get('id'),
                    'intent': intent,
                    'text': text[:50] + '...' if len(text) > 50 else text,
                    'latency_ms': trace.get('latency_ms', 0)
                })

        # Top respuestas largas (posibles prompts largos)
        long_responses = sorted(
            [(t.get('response_len_chars', 0), t.get('id'), t.get('intent', '')) for t in self.traces],
            reverse=True
        )[:10]

        return {
            'wasteful_openai_calls': wasteful_calls,
            'wasteful_count': len(wasteful_calls),
            'long_responses': long_responses
        }

    def analyze_quality(self) -> Dict[str, Any]:
        """Análisis de calidad conversacional."""
        # Respuestas demasiado largas
        too_long = [t for t in self.traces if t.get('response_len_chars', 0) > 350]

        # Respuestas sin pregunta cerrada (heurística simple)
        no_question = []
        for trace in self.traces:
            response = trace.get('response_text', '')
            if response and '?' not in response[-100:]:  # Últimos 100 chars
                no_question.append({
                    'id': trace.get('id'),
                    'intent': trace.get('intent', ''),
                    'response': response[:100] + '...' if len(response) > 100 else response
                })

        return {
            'too_long_responses': too_long,
            'too_long_count': len(too_long),
            'no_question_responses': no_question,
            'no_question_count': len(no_question)
        }

    def analyze_message_types(self) -> Dict[str, Any]:
        """Análisis por tipo de mensaje."""
        message_types = Counter(t.get('message_type', 'unknown') for t in self.traces)

        # OpenAI por tipo de mensaje
        openai_by_type = {}
        for msg_type in message_types.keys():
            type_traces = [t for t in self.traces if t.get('message_type') == msg_type]
            openai_called = sum(1 for t in type_traces if t.get('openai_called', 0))
            total = len(type_traces)
            openai_by_type[msg_type] = {
                'total': total,
                'openai_called': openai_called,
                'openai_percent': round((openai_called / total) * 100, 1) if total > 0 else 0
            }

        return {
            'message_types_breakdown': message_types.most_common(10),
            'openai_by_message_type': openai_by_type
        }

    def analyze_routing(self) -> Dict[str, Any]:
        """Análisis de routing y handoffs."""
        routed_traces = [t for t in self.traces if t.get('routed_team')]

        # Motivos por equipo
        comercial_motivos = []
        tecnica_motivos = []

        for trace in routed_traces:
            team = trace.get('routed_team', '')
            text = trace.get('raw_text', '').lower()

            if team == 'comercial':
                comercial_motivos.append(text[:50])
            elif team == 'tecnica':
                tecnica_motivos.append(text[:50])

        # Falsos positivos (heurística simple)
        false_positives = []
        for trace in routed_traces:
            team = trace.get('routed_team', '')
            text = trace.get('raw_text', '').lower()

            if 'addi' in text and team != 'comercial':
                false_positives.append({
                    'id': trace.get('id'),
                    'team': team,
                    'text': text[:50],
                    'issue': 'Addi debería ir a comercial'
                })

        return {
            'comercial_motivos': comercial_motivos[:10],
            'tecnica_motivos': tecnica_motivos[:10],
            'false_positives': false_positives,
            'false_positives_count': len(false_positives)
        }

    def analyze_assets(self) -> Dict[str, Any]:
        """Análisis de selección de assets."""
        # Assets en saludos (debería ser 0)
        assets_in_greetings = [
            t for t in self.traces
            if (t.get('intent') or '').lower() in ['saludo', 'cierre', 'despedida']
            and t.get('selected_asset_id')
        ]

        # Conteo por asset_id
        asset_counts = Counter(
            t.get('selected_asset_id', '') for t in self.traces
            if t.get('selected_asset_id')
        )

        return {
            'assets_in_greetings': assets_in_greetings,
            'assets_in_greetings_count': len(assets_in_greetings),
            'asset_counts': asset_counts.most_common(10)
        }

    def generate_report(self) -> str:
        """Genera reporte completo en Markdown."""
        metrics = self.calculate_metrics()
        costs = self.audit_costs()
        quality = self.analyze_quality()
        routing = self.analyze_routing()
        assets = self.analyze_assets()
        message_types = self.analyze_message_types()

        report = f"""# 📊 Reporte de Análisis de Trazas

**Total de trazas analizadas:** {metrics.get('total_interacciones', 0)}

## 1️⃣ Métricas Principales

### Uso del Sistema
- **Total interacciones:** {metrics.get('total_interacciones', 0)}
- **OpenAI llamado:** {metrics.get('openai_called_percent', 0)}%
- **Relacionado con negocio:** {metrics.get('business_related_percent', 0)}%
- **Cache hits:** {metrics.get('cache_hit_percent', 0)}%

### Latencia (ms)
- **Conteo:** {metrics.get('latencies_ms', {}).get('count', 0)}
- **Promedio:** {metrics.get('latencies_ms', {}).get('avg', 0)}ms
- **Mediana:** {metrics.get('latencies_ms', {}).get('median', 0)}ms
- **P95:** {metrics.get('latencies_ms', {}).get('p95', 0)}ms
- **Mín/Máx:** {metrics.get('latencies_ms', {}).get('min', 0)}ms / {metrics.get('latencies_ms', {}).get('max', 0)}ms

### Latencia (μs)
- **Conteo:** {metrics.get('latencies_us', {}).get('count', 0)}
- **Promedio:** {metrics.get('latencies_us', {}).get('avg', 0)}μs
- **Mediana:** {metrics.get('latencies_us', {}).get('median', 0)}μs

### Top Intents
"""
        for intent, count in metrics.get('top_intents', []):
            report += f"- **{intent or '(vacío)'}:** {count}\n"

        report += "\n### Top Routed Teams\n"
        for team, count in metrics.get('top_routed_teams', []):
            report += f"- **{team or '(ninguno)'}:** {count}\n"

        report += "\n## 2️⃣ Auditoría de Costos\n"
        report += f"### Llamadas OpenAI Innecesarias: {costs.get('wasteful_count', 0)}\n"

        for call in costs.get('wasteful_openai_calls', [])[:5]:  # Top 5
            report += f"- **ID {call['id']}:** {call['intent']} - \"{call['text']}\" ({call['latency_ms']}ms)\n"

        report += "\n### Respuestas Más Largas (Posibles Prompts Largos)\n"
        for length, trace_id, intent in costs.get('long_responses', []):
            report += f"- **ID {trace_id}:** {length} chars - {intent}\n"

        report += "\n## 3️⃣ Calidad Conversacional\n"
        report += f"### Respuestas Demasiado Largas (>350 chars): {quality.get('too_long_count', 0)}\n"

        for trace in quality.get('too_long_responses', [])[:3]:  # Top 3
            report += f"- **ID {trace.get('id')}:** {trace.get('response_len_chars', 0)} chars\n"

        report += f"\n### Respuestas Sin Pregunta Cerrada: {quality.get('no_question_count', 0)}\n"

        for resp in quality.get('no_question_responses', [])[:3]:  # Top 3
            report += f"- **ID {resp['id']}:** {resp['intent']} - \"{resp['response'][:50]}...\"\n"

        report += "\n## 4️⃣ Routing y Handoffs\n"
        report += "### Motivos 💰 Comercial\n"
        for motivo in routing.get('comercial_motivos', [])[:5]:
            report += f"- \"{motivo}...\"\n"

        report += "\n### Motivos ⚙️ Técnica\n"
        for motivo in routing.get('tecnica_motivos', [])[:5]:
            report += f"- \"{motivo}...\"\n"

        report += f"\n### Falsos Positivos: {routing.get('false_positives_count', 0)}\n"
        for fp in routing.get('false_positives', []):
            report += f"- **ID {fp['id']}:** {fp['issue']} - \"{fp['text']}\"\n"

        report += "\n## 5️⃣ Assets\n"
        report += f"### Assets en Saludos (Debería ser 0): {assets.get('assets_in_greetings_count', 0)}\n"

        for trace in assets.get('assets_in_greetings', []):
            report += f"- **ID {trace.get('id')}:** {trace.get('intent')} -> {trace.get('selected_asset_id')}\n"

        report += "\n### Conteo por Asset ID\n"
        for asset_id, count in assets.get('asset_counts', []):
            report += f"- **{asset_id}:** {count} usos\n"

        report += "\n## 6️⃣ Análisis por Tipo de Mensaje\n"
        report += "### Breakdown de Tipos de Mensaje\n"
        for msg_type, count in message_types.get('message_types_breakdown', []):
            report += f"- **{msg_type}:** {count}\n"

        report += "\n### OpenAI por Tipo de Mensaje\n"
        for msg_type, stats in message_types.get('openai_by_message_type', {}).items():
            report += f"- **{msg_type}:** {stats['openai_called']}/{stats['total']} ({stats['openai_percent']}%)\n"

        report += "\n---\n*Reporte generado automáticamente por `analyze_traces.py`*"

        return report


def main():
    """Función principal."""
    print("🔍 ANALIZANDO TRAZAS...\n")

    analyzer = TraceAnalyzer()

    if not analyzer.traces:
        print("❌ No hay trazas para analizar")
        return

    report = analyzer.generate_report()
    print(report)

    # Guardar reporte a archivo
    with open("trace_analysis_report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("\n💾 Reporte guardado en: trace_analysis_report.md")
    print(f"📊 Analizadas {len(analyzer.traces)} trazas")


if __name__ == "__main__":
    main()
