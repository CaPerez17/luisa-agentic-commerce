# Operations and Trade-offs - LUISA

## Architecture Decisions

### Hybrid Approach: Heuristics-First + LLM Gated

**Why:** Balance between cost, latency, and intelligence.

- **Heuristics handle 70-80% of cases:** Fast (<100ms), zero cost, predictable
- **LLM handles 20-30% of complex cases:** Slower (500-2000ms), ~$0.03/call, intelligent
- **Gating ensures LLM only for complex business consultations:** Prevents waste on FAQs

**Trade-off:** Some edge cases may get deterministic responses instead of LLM-generated ones. Acceptable for cost control.

### SQLite Now (Not PostgreSQL/Redis)

**Why SQLite:**
- Single-instance deployment (VPS 512MB-1GB RAM)
- < 1000 conversations/day (well within SQLite limits)
- Zero operational overhead (no separate DB server)
- ACID guarantees sufficient for our use case
- Easy backups (single file copy)

**Why not PostgreSQL:**
- Unnecessary complexity for current scale
- Additional memory overhead
- Requires separate container/service
- Migration path exists if volume > 5000/day

**Why not Redis:**
- In-memory cache sufficient for single instance
- Rate limiting in-memory is acceptable
- No need for distributed cache yet
- Can add Redis if multi-instance needed

**Trade-off:** SQLite write contention if > 100 concurrent writes. Mitigated by:
- Background task processing (async)
- Idempotency checks reduce duplicate writes
- Read-heavy workload (most queries are SELECT)

### Epoch Timestamps for TTL

**Why INTEGER epoch instead of TIMESTAMP:**
- **Robustness:** No timezone parsing issues
- **Performance:** Integer comparison faster than datetime parsing
- **Simplicity:** `now_epoch - stored_epoch > ttl_seconds` is unambiguous
- **Portability:** Works across all SQLite versions

**Trade-off:** Less human-readable in raw DB. Mitigated by:
- Keeping `mode_updated_at` (TIMESTAMP) for compatibility
- Scripts handle both formats with fallback

### Canary Allowlist for OpenAI

**Why allowlist instead of percentage-based rollout:**
- **Control:** Exact control over which conversations use OpenAI
- **Safety:** Prevents unexpected costs during testing
- **Debugging:** Easy to test specific conversation_ids
- **Gradual rollout:** Add conversation_ids incrementally

**Trade-off:** Manual management of allowlist. Acceptable for controlled production testing.

### What We Measure and Why (/ops/snapshot)

**Metrics:**
- `total_msgs_60m`: Volume indicator (health check)
- `pct_personal`: Filtering effectiveness (should be low if filtering works)
- `pct_handoff`: Escalation rate (indicates complex cases)
- `pct_openai`: LLM usage (cost indicator, should be 20-30%)
- `errores_count`: Error rate (should be 0 or very low)
- `p95_latency_ms`: Performance (should be < 2000ms)

**Why these:** Cover cost, quality, performance, and operational health in minimal fields.

### Failure Modes and Mitigations

**LUISA Never Stays Silent:**
- **Mitigation:** Always generate response, even in HUMAN_ACTIVE mode
- **Fallback:** Deterministic greeting variants if LLM fails
- **Logging:** Every interaction logged, even if no response sent

**LLM Does Not Decide States:**
- **Mitigation:** LLM only generates text, never triggers handoff or state changes
- **Gating:** `should_call_openai()` checks business rules before LLM
- **Fallback:** Deterministic responses if LLM unavailable

**Hard-Fail Deploy:**
- **Mitigation:** `go_no_go.py --hard-fail` blocks deploy if critical checks fail
- **Checks:** Health, greeting, non-business filtering, FAQ responses
- **Rollback:** Docker image tagging + DB backup before deploy

### Filtering Dataset Skew (15 Personal / 37 Business)

**Why 15/37 ratio (not 25/25):**
- **Business priority:** LUISA's primary function is handling business inquiries. False negatives (missing business messages) are more costly than false positives (responding to personal messages).
- **Real-world distribution:** In production, business messages likely outnumber personal messages 2:1 or 3:1, especially during business hours.
- **Validation focus:** The dataset emphasizes precision on business classification (37 samples) to ensure we don't miss customer inquiries.
- **Personal message coverage:** 15 personal samples cover common patterns (greetings, programming questions, casual chat) sufficient for validation.

**Validation thresholds:**
- **Precision >= 90%:** Ensures < 10% of business messages are misclassified as personal (critical for customer service)
- **False positives <= 5%:** Acceptable trade-off - responding to occasional personal messages is less harmful than missing business inquiries
- **Recall:** Not explicitly enforced, but precision focus naturally maintains good recall on business messages

**Trade-off:** Dataset skew (15/37 ≈ 0.4 ratio) may slightly favor business classification, but this aligns with LUISA's operational priority (never miss a customer inquiry). The 15 personal samples provide sufficient coverage of edge cases for validation purposes.
