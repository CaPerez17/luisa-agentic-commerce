#!/usr/bin/env python3
"""
Script de verificación Go/No-Go previo a producción.

Ejecuta checks automáticos contra el backend en ejecución:
- GET /health
- Casos de conversación clave en /api/chat
- Validación de trazas en SQLite (interaction_traces)

Uso:
    python3 scripts/go_no_go.py

Requisitos:
- Servidor backend corriendo en BASE_URL (default: http://localhost:8000)
- Acceso de lectura a la base SQLite (DB_PATH o candidatos por defecto)
- Dependencias: httpx (ya incluida en requirements), sqlite3 (stdlib)
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DEFAULT_BASE_URL = "http://localhost:8000"
BASE_URL = os.getenv("BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _candidate_db_paths() -> List[Path]:
    env_db = os.getenv("DB_PATH")
    candidates: List[Path] = []

    if env_db:
        p = Path(env_db)
        if not p.is_absolute():
            p = BASE_DIR / env_db
        candidates.append(p)

    # Prefer data/ first (nuevo layout), luego root backend/
    candidates.extend(
        [
            BASE_DIR / "data" / "luisa.db",
            BASE_DIR / "luisa.db",
            BASE_DIR.parent / "luisa.db",
        ]
    )
    # Dedup manteniendo orden
    deduped: List[Path] = []
    for c in candidates:
        if c not in deduped:
            deduped.append(c)
    return deduped


def resolve_db_path() -> Path:
    for cand in _candidate_db_paths():
        if cand.exists():
            return cand
    # Último recurso: primer candidato aunque no exista aún
    return _candidate_db_paths()[0]


DB_PATH = resolve_db_path()


# -----------------------------------------------------------------------------
# Tipos y utilidades
# -----------------------------------------------------------------------------
@dataclass
class ScenarioResult:
    name: str
    ok: bool
    reason: str
    details: Dict[str, Any]


def log(msg: str) -> None:
    print(msg)


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def count_traces(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM interaction_traces")
    return int(cur.fetchone()[0])


def fetch_last_trace(conn: sqlite3.Connection, conversation_id: str) -> Optional[Dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT * FROM interaction_traces
        WHERE conversation_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (conversation_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return dict(row)


def make_conversation_id(suffix: str) -> str:
    return f"go-nogo-{suffix}-{uuid.uuid4().hex[:8]}"


def ensure_trace_growth(delta: int) -> Tuple[bool, str]:
    if delta > 0:
        return True, f"trace +{delta}"
    return False, "trace table did not grow"


# -----------------------------------------------------------------------------
# Validadores de escenarios
# -----------------------------------------------------------------------------
def validate_saludo(resp: Dict[str, Any], trace: Dict[str, Any], delta: int) -> Tuple[bool, str]:
    ok_delta, reason_delta = ensure_trace_growth(delta)
    conditions = [
        ok_delta,
        resp.get("asset") is None,
        trace is not None,
        trace.get("selected_asset_id") in (None, "", "null"),
        trace.get("openai_called") in (0, None, False),
    ]
    reasons = []
    if not ok_delta:
        reasons.append(reason_delta)
    if resp.get("asset") is not None:
        reasons.append("asset should be None for saludo")
    if trace:
        if trace.get("selected_asset_id"):
            reasons.append("selected_asset_id should be empty")
        if trace.get("intent") not in (None, "", "saludo"):
            reasons.append(f"unexpected intent={trace.get('intent')}")
    else:
        reasons.append("trace missing for saludo")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_non_business(resp: Dict[str, Any], trace: Dict[str, Any], delta: int) -> Tuple[bool, str]:
    ok_delta, reason_delta = ensure_trace_growth(delta)
    decision = (trace or {}).get("decision_path", "") or ""
    conditions = [
        ok_delta,
        trace is not None,
        (trace or {}).get("openai_called") in (0, None, False),
        ("non_business" in decision) or ("blocked_non_business" in decision) or ("non_business_handled" in decision),
    ]
    reasons = []
    if not ok_delta:
        reasons.append(reason_delta)
    if trace:
        if trace.get("openai_called"):
            reasons.append("openai_called should be false")
        if not conditions[-1]:
            reasons.append(f"decision_path missing non_business flag ({decision})")
    else:
        reasons.append("trace missing for non_business")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_faq(resp: Dict[str, Any], trace: Dict[str, Any], delta: int, expect_cache_hit: bool) -> Tuple[bool, str]:
    ok_delta, reason_delta = ensure_trace_growth(delta)
    cache_hit = (trace or {}).get("cache_hit")
    decision = (trace or {}).get("decision_path", "") or ""
    conditions = [
        ok_delta,
        trace is not None,
        (trace or {}).get("openai_called") in (0, None, False),
        (cache_hit == 1) if expect_cache_hit else True,
    ]
    reasons = []
    if not ok_delta:
        reasons.append(reason_delta)
    if trace:
        if trace.get("openai_called"):
            reasons.append("openai_called should be false for FAQ")
        if expect_cache_hit and cache_hit != 1:
            reasons.append("cache_hit expected on second FAQ call")
        if "openai_blocked_faq" not in decision and "openai_blocked" not in decision and "openai_skipped" not in decision:
            reasons.append(f"decision_path missing FAQ openai block/skip ({decision})")
    else:
        reasons.append("trace missing for FAQ")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_asset(resp: Dict[str, Any], trace: Dict[str, Any], delta: int) -> Tuple[bool, str]:
    ok_delta, reason_delta = ensure_trace_growth(delta)
    asset = resp.get("asset")
    conditions = [
        ok_delta,
        trace is not None,
        asset is not None,
        (trace or {}).get("selected_asset_id") not in (None, "", "null"),
    ]
    reasons = []
    if not ok_delta:
        reasons.append(reason_delta)
    if asset is None:
        reasons.append("asset missing in response")
    if trace:
        if not trace.get("selected_asset_id"):
            reasons.append("selected_asset_id missing in trace")
    else:
        reasons.append("trace missing for asset scenario")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_handoff(resp: Dict[str, Any], trace: Dict[str, Any], delta: int) -> Tuple[bool, str]:
    ok_delta, reason_delta = ensure_trace_growth(delta)
    decision = (trace or {}).get("decision_path", "") or ""
    conditions = [
        ok_delta,
        trace is not None,
        bool(resp.get("needs_escalation")) or bool(resp.get("routed_notification")),
        (trace or {}).get("routed_team") not in (None, "", "null"),
        "handoff" in decision or "routed" in decision,
    ]
    reasons = []
    if not ok_delta:
        reasons.append(reason_delta)
    if not resp.get("needs_escalation") and not resp.get("routed_notification"):
        reasons.append("needs_escalation/routed_notification missing")
    if trace:
        if not trace.get("routed_team"):
            reasons.append("routed_team missing in trace")
        if not ("handoff" in decision or "routed" in decision):
            reasons.append(f"decision_path missing handoff flag ({decision})")
    else:
        reasons.append("trace missing for handoff")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_openai(resp: Dict[str, Any], trace: Dict[str, Any], delta: int) -> Tuple[bool, str]:
    ok_delta, reason_delta = ensure_trace_growth(delta)
    decision = (trace or {}).get("decision_path", "") or ""
    conditions = [
        ok_delta,
        trace is not None,
        (trace or {}).get("openai_called") in (1, True),
        "openai_called" in decision,
    ]
    reasons = []
    if not ok_delta:
        reasons.append(reason_delta)
    if trace:
        if trace.get("openai_called") not in (1, True):
            reasons.append("openai_called should be true")
        if "openai_called" not in decision:
            reasons.append(f"decision_path missing openai flag ({decision})")
    else:
        reasons.append("trace missing for openai scenario")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


# -----------------------------------------------------------------------------
# Ejecución de escenarios
# -----------------------------------------------------------------------------
def run_health(client: httpx.Client) -> ScenarioResult:
    name = "health"
    details: Dict[str, Any] = {}
    try:
        resp = client.get("/health", timeout=8.0)
    except Exception as exc:
        return ScenarioResult(name, False, f"health request failed: {exc}", details)

    if resp.status_code != 200:
        return ScenarioResult(name, False, f"status_code={resp.status_code}", details)

    data = resp.json()
    details["response"] = data
    modules = data.get("modules", {})
    catalog_items = data.get("catalog_items", 0)
    ok = (
        data.get("status") == "healthy"
        and isinstance(modules, dict)
        and catalog_items is not None
    )
    reason = "ok" if ok else "health payload missing required fields"
    return ScenarioResult(name, ok, reason, details)


def run_chat_case(
    client: httpx.Client,
    conn: sqlite3.Connection,
    name: str,
    text: str,
    validator,
    expect_cache_hit: bool = False,
) -> ScenarioResult:
    conversation_id = make_conversation_id(name)
    payload = {
        "conversation_id": conversation_id,
        "text": text,
        "sender": "customer",
    }

    try:
        pre_count = count_traces(conn)
    except Exception as exc:
        return ScenarioResult(name, False, f"cannot read traces: {exc}", {"conversation_id": conversation_id})

    try:
        resp = client.post("/api/chat", json=payload, timeout=12.0)
    except Exception as exc:
        return ScenarioResult(name, False, f"chat request failed: {exc}", {"conversation_id": conversation_id})

    if resp.status_code != 200:
        return ScenarioResult(
            name,
            False,
            f"status_code={resp.status_code}",
            {"conversation_id": conversation_id, "response": resp.text},
        )

    # Esperar breve para asegurar escritura de trazas
    time.sleep(0.15)

    try:
        post_count = count_traces(conn)
        trace = fetch_last_trace(conn, conversation_id)
    except Exception as exc:
        return ScenarioResult(name, False, f"trace fetch failed: {exc}", {"conversation_id": conversation_id})

    delta = post_count - pre_count
    resp_json = resp.json()
    ok, reason = validator(resp_json, trace, delta) if validator else (True, "ok")
    details = {
        "conversation_id": conversation_id,
        "delta_traces": delta,
        "trace": trace,
        "response": resp_json,
    }
    if expect_cache_hit:
        details["expect_cache_hit"] = True
    return ScenarioResult(name, ok, reason, details)


def main() -> int:
    parser = argparse.ArgumentParser(description="Go/No-Go checks antes de deploy")
    parser.add_argument("--hard-fail", action="store_true", default=True, help="Hard-fail si checks críticos fallan (default: True)")
    parser.add_argument("--no-hard-fail", dest="hard_fail", action="store_false", help="No hard-fail, solo warnings")
    args = parser.parse_args()
    
    hard_fail = args.hard_fail
    
    log("🏁 Ejecutando Go/No-Go suite...")
    log(f"BASE_URL={BASE_URL}")
    log(f"DB_PATH={DB_PATH}")
    log(f"Hard-fail: {hard_fail}")

    if not DB_PATH.exists():
        log("❌ DB no encontrada. Ejecuta primero `python scripts/init_db.py` y corre el servidor.")
        return 1

    try:
        conn = get_connection(DB_PATH)
        cols = table_columns(conn, "interaction_traces")
        if not cols:
            log("❌ Tabla interaction_traces no encontrada. Inicializa la base de datos.")
            return 1
    except Exception as exc:
        log(f"❌ Error abriendo DB: {exc}")
        return 1

    results: List[ScenarioResult] = []
    hard_fail_results: List[ScenarioResult] = []
    warning_results: List[ScenarioResult] = []

    with httpx.Client(base_url=BASE_URL) as client:
        # 1) Health (HARD-FAIL)
        health_result = run_health(client)
        results.append(health_result)
        if not health_result.ok:
            hard_fail_results.append(health_result)
            if hard_fail:
                log("❌ Health check falló (HARD-FAIL)")
                return 1
            else:
                log("⚠️ Health check falló; continuando con los demás escenarios.")
        
        openai_enabled = False
        if health_result.ok:
            openai_enabled = bool(health_result.details.get("response", {}).get("modules", {}).get("openai"))

        # 2) Saludo (HARD-FAIL)
        saludo_result = run_chat_case(client, conn, "saludo", "hola, ¿cómo estás?", validate_saludo)
        results.append(saludo_result)
        if not saludo_result.ok:
            hard_fail_results.append(saludo_result)

        # 3) No negocio (programación) (HARD-FAIL)
        non_business_result = run_chat_case(
            client,
            conn,
            "nonbusiness",
            "cómo hago un for en python",
            validate_non_business,
        )
        results.append(non_business_result)
        if not non_business_result.ok:
            hard_fail_results.append(non_business_result)

        # 4) FAQ horarios (warm) (HARD-FAIL)
        faq_result1 = run_chat_case(
            client,
            conn,
            "faq-horarios-1",
            "¿cuáles son los horarios?",
            lambda r, t, d: validate_faq(r, t, d, expect_cache_hit=False),
        )
        results.append(faq_result1)
        if not faq_result1.ok:
            hard_fail_results.append(faq_result1)
        
        # 4b) FAQ horarios (cache hit esperado) (HARD-FAIL)
        faq_result2 = run_chat_case(
            client,
            conn,
            "faq-horarios-2",
            "¿cuáles son los horarios?",
            lambda r, t, d: validate_faq(r, t, d, expect_cache_hit=True),
            expect_cache_hit=True,
        )
        results.append(faq_result2)
        if not faq_result2.ok:
            hard_fail_results.append(faq_result2)

        # 5) Consulta industrial con asset (WARNING)
        asset_result = run_chat_case(
            client,
            conn,
            "industrial-asset",
            "busco una máquina industrial recta para jeans con motor ahorrador",
            validate_asset,
        )
        results.append(asset_result)
        if not asset_result.ok:
            warning_results.append(asset_result)

        # 6) Caso de escalamiento (pago realizado + ciudad) (WARNING)
        handoff_result = run_chat_case(
            client,
            conn,
            "handoff-pago",
            "ya pagué la máquina, estoy en bogota, por favor confirmen la entrega",
            validate_handoff,
        )
        results.append(handoff_result)
        if not handoff_result.ok:
            warning_results.append(handoff_result)

        # 7) Caso OpenAI (solo si está habilitado) (WARNING)
        if openai_enabled:
            openai_result = run_chat_case(
                client,
                conn,
                "openai-consult",
                "tengo un taller de botas con cuero grueso y quiero optimizar la ergonomía y el flujo, ¿qué configuraciones avanzadas de máquina recomiendas?",
                validate_openai,
            )
            results.append(openai_result)
            if not openai_result.ok:
                warning_results.append(openai_result)
        else:
            log("ℹ️ OPENAI_ENABLED=false según /health; se omite prueba de OpenAI.")

    # Resumen final
    log("\n================ GO / NO-GO =================")
    
    # Mostrar hard-fail checks
    if hard_fail_results:
        log("\n🔴 HARD-FAIL CHECKS:")
        for res in hard_fail_results:
            log(f"  ❌ {res.name}: {res.reason}")
            log(f"     details: {res.details}")
    
    # Mostrar warnings
    if warning_results:
        log("\n⚠️  WARNINGS:")
        for res in warning_results:
            log(f"  ⚠️  {res.name}: {res.reason}")
    
    # Mostrar todos los resultados
    log("\n📊 TODOS LOS CHECKS:")
    for res in results:
        status = "✅ PASS" if res.ok else "❌ FAIL"
        log(f"  [{status}] {res.name}: {res.reason}")

    log("\nRutas relevantes:")
    log(f"- Health: {BASE_URL}/health")
    log(f"- Chat:   {BASE_URL}/api/chat")
    log(f"- DB:     {DB_PATH}")

    # Determinar resultado final
    if hard_fail_results and hard_fail:
        log(f"\n❌ RESULTADO: NO-GO ({len(hard_fail_results)} hard-fail checks fallaron)")
        return 1
    elif hard_fail_results:
        log(f"\n⚠️  RESULTADO: GO con warnings ({len(hard_fail_results)} hard-fail checks fallaron pero --no-hard-fail activo)")
        return 0
    elif warning_results:
        log(f"\n✅ RESULTADO: GO con warnings ({len(warning_results)} warnings)")
        return 0
    else:
        log("\n✅ RESULTADO: GO (todas las verificaciones pasaron)")
        return 0


if __name__ == "__main__":
    sys.exit(main())

