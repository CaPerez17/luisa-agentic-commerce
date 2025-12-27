# Changelog

## Unreleased

- Modularización del backend (`backend/app`) con servicios, reglas y routers desacoplados.
- Guardrails de negocio + gating estricto de OpenAI para evitar gastos fuera de contexto.
- Cache in-memory (LRU/TTL) para FAQs seguras y respuestas rápidas.
- Trazabilidad completa en SQLite (`interaction_traces`) con latencias y decision_path.
- Gestión de assets por catálogo (local/Drive) con proxy y metadata versionada.
- Webhook de WhatsApp Cloud API con notificaciones internas y modo sombra.
- Post-procesador que fuerza preguntas cerradas para mantener la conversación caliente.
- Scripts operativos: `scripts/analyze_traces.py` y `scripts/go_no_go.py` para QA y reportes.

