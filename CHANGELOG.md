# Changelog

## [2.1.0] - 2025-01-XX

### Added
- **Operations Observability:** `/ops/snapshot` endpoint and `ops_snapshot.py` script for production metrics
- **WhatsApp Send Hardening:** Guaranteed logging for all WhatsApp message sends with latency and error tracking
- **HUMAN_ACTIVE TTL Hardening:** Epoch-based timestamps and `fix_stuck_human_active.py` script for automatic cleanup
- **Classification Persistence:** Classification scoring (0.0-1.0) and reasons persisted in `interaction_traces`
- **Filtering Validation:** Versioned dataset (`filtering_dataset_v1.json`) and `validate_filtering.py` script (precision >= 90%)
- **OpenAI Canary:** Allowlist-based gating for controlled OpenAI usage in production
- **Cost Monitoring:** `monitor_openai_costs.py` script to track and validate OpenAI costs (< $0.05/conv)
- **Deploy Integration:** `go_no_go.py` integrated in `deploy.sh` with hard-fail checks

### Changed
- `is_business_related()` now returns `(is_business, reason, score, reasons_list)` for better observability
- `send_whatsapp_message()` now requires `conversation_id` parameter for tracing
- Filtering optimization: LLM only used if classification_score < 0.3 (reduces LLM usage to < 10%)

### Fixed
- TTL parsing robustness: fallback to `created_at + 24h` if `mode_updated_at` parsing fails
- WhatsApp send logging: 100% coverage with structured fields

### Database Schema
- Added to `interaction_traces`: `whatsapp_send_success`, `whatsapp_send_latency_ms`, `whatsapp_send_error_code`, `classification`, `is_personal`, `classification_score`, `classification_reasons`, `classifier_version`, `openai_canary_allowed`, `openai_latency_ms`, `openai_error`, `openai_fallback_used`
- Added to `conversations`: `mode_updated_at_epoch` (INTEGER, UTC epoch)

### Documentation
- Added `docs/OPERATIONS_AND_TRADEOFFS.md` (English) with architecture decisions and trade-offs
- Updated README.md with Operations section

## [2.0.0] - 2024-12-XX

- Modularización del backend (`backend/app`) con servicios, reglas y routers desacoplados.
- Guardrails de negocio + gating estricto de OpenAI para evitar gastos fuera de contexto.
- Cache in-memory (LRU/TTL) para FAQs seguras y respuestas rápidas.
- Trazabilidad completa en SQLite (`interaction_traces`) con latencias y decision_path.
- Gestión de assets por catálogo (local/Drive) con proxy y metadata versionada.
- Webhook de WhatsApp Cloud API con notificaciones internas y modo sombra.
- Post-procesador que fuerza preguntas cerradas para mantener la conversación caliente.
- Scripts operativos: `scripts/analyze_traces.py` y `scripts/go_no_go.py` para QA y reportes.

