#!/usr/bin/env python3
"""
Script de verificación Go/No-Go para producción con WhatsApp y OpenAI.

Valida:
- Health endpoint
- Chat scenarios (saludo, non-business, FAQ)
- OpenAI gating (openai_called=0 para casos bloqueados)
- WhatsApp webhook readiness
- Trace growth y decision_path flags
- Instrucciones exactas para probar WhatsApp

Uso:
    python3 scripts/go_no_go_whatsapp_openai.py

Requisitos:
- Servidor backend corriendo en BASE_URL (default: http://localhost:8000)
- Acceso de lectura a la base SQLite (DB_PATH)
- Dependencias: httpx, sqlite3 (stdlib)
"""

from __future__ import annotations

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

    candidates.extend(
        [
            BASE_DIR / "data" / "luisa.db",
            BASE_DIR / "luisa.db",
            BASE_DIR.parent / "luisa.db",
        ]
    )
    deduped: List[Path] = []
    for c in candidates:
        if c not in deduped:
            deduped.append(c)
    return deduped


def resolve_db_path() -> Path:
    for cand in _candidate_db_paths():
        if cand.exists():
            return cand
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
    """Valida que saludo NO llama OpenAI y NO tiene asset."""
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
        if trace.get("openai_called") not in (0, None, False):
            reasons.append(f"openai_called should be 0, got {trace.get('openai_called')}")
    else:
        reasons.append("trace missing for saludo")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_non_business(resp: Dict[str, Any], trace: Dict[str, Any], delta: int) -> Tuple[bool, str]:
    """Valida que mensaje no-negocio NO llama OpenAI."""
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
        if trace.get("openai_called") not in (0, None, False):
            reasons.append(f"openai_called should be 0 for non-business, got {trace.get('openai_called')}")
        if not conditions[-1]:
            reasons.append(f"decision_path missing non_business flag ({decision})")
    else:
        reasons.append("trace missing for non_business")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_faq(resp: Dict[str, Any], trace: Dict[str, Any], delta: int, expect_cache_hit: bool) -> Tuple[bool, str]:
    """Valida que FAQ NO llama OpenAI."""
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
        if trace.get("openai_called") not in (0, None, False):
            reasons.append(f"openai_called should be 0 for FAQ, got {trace.get('openai_called')}")
        if expect_cache_hit and cache_hit != 1:
            reasons.append("cache_hit expected on second FAQ call")
        if "openai_blocked_faq" not in decision and "openai_blocked" not in decision and "openai_skipped" not in decision:
            reasons.append(f"decision_path missing FAQ openai block/skip ({decision})")
    else:
        reasons.append("trace missing for FAQ")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


def validate_openai_allowed(resp: Dict[str, Any], trace: Dict[str, Any], delta: int) -> Tuple[bool, str]:
    """Valida que OpenAI se llama cuando está permitido."""
    ok_delta, reason_delta = ensure_trace_growth(delta)
    decision = (trace or {}).get("decision_path", "") or ""
    conditions = [
        ok_delta,
        trace is not None,
        (trace or {}).get("openai_called") in (1, True),
        "openai_called" in decision or "openai_called_fallback" in decision,
    ]
    reasons = []
    if not ok_delta:
        reasons.append(reason_delta)
    if trace:
        if trace.get("openai_called") not in (1, True):
            reasons.append(f"openai_called should be 1, got {trace.get('openai_called')}")
        if "openai_called" not in decision and "openai_called_fallback" not in decision:
            reasons.append(f"decision_path missing openai flag ({decision})")
    else:
        reasons.append("trace missing for openai scenario")
    return all(conditions), "; ".join(reasons) if reasons else "ok"


# -----------------------------------------------------------------------------
# Ejecución de escenarios
# -----------------------------------------------------------------------------
def run_health(client: httpx.Client) -> ScenarioResult:
    """Valida endpoint /health."""
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
    """Ejecuta un caso de chat y valida resultado."""
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


def check_whatsapp_config() -> Tuple[bool, List[str]]:
    """Verifica configuración de WhatsApp."""
    warnings = []
    whatsapp_enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
    
    if not whatsapp_enabled:
        warnings.append("WHATSAPP_ENABLED=false (no está habilitado)")
        return False, warnings
    
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    test_notify = os.getenv("TEST_NOTIFY_NUMBER", "")
    
    if not access_token:
        warnings.append("WHATSAPP_ACCESS_TOKEN está vacío")
    if not phone_number_id:
        warnings.append("WHATSAPP_PHONE_NUMBER_ID está vacío")
    if not verify_token or verify_token == "luisa-verify-token-2024":
        warnings.append("WHATSAPP_VERIFY_TOKEN debe ser un token seguro (no usar default)")
    if not test_notify:
        warnings.append("TEST_NOTIFY_NUMBER está vacío")
    
    return len(warnings) == 0, warnings


def check_openai_config() -> Tuple[bool, List[str]]:
    """Verifica configuración de OpenAI."""
    warnings = []
    openai_enabled = os.getenv("OPENAI_ENABLED", "false").lower() == "true"
    
    if not openai_enabled:
        warnings.append("OPENAI_ENABLED=false (no está habilitado)")
        return False, warnings
    
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-your"):
        warnings.append("OPENAI_API_KEY está vacío o es placeholder")
    
    return len(warnings) == 0, warnings


def print_whatsapp_instructions(base_url: str) -> None:
    """Imprime instrucciones exactas para probar WhatsApp."""
    log("\n" + "=" * 70)
    log("📱 INSTRUCCIONES PARA PROBAR WHATSAPP CLOUD API")
    log("=" * 70)
    
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "luisa-verify-token-2024")
    
    log("\n1️⃣ Exponer webhook públicamente:")
    log("   Opción A (ngrok para testing):")
    log("      ngrok http 8000")
    log("      # Copia la URL HTTPS (ej: https://abc123.ngrok.io)")
    log("   Opción B (producción):")
    log("      Despliega backend con HTTPS (AWS/GCP/Azure)")
    
    log("\n2️⃣ Configurar webhook en Meta Business Dashboard:")
    log("   - Ve a: https://business.facebook.com/")
    log("   - WhatsApp → API Setup → Webhooks")
    log(f"   - Webhook URL: https://tu-dominio.com/whatsapp/webhook")
    log(f"   - Verify Token: {verify_token}")
    log("   - Suscríbete a eventos: 'messages'")
    
    log("\n3️⃣ Verificar webhook (Meta enviará GET request):")
    log(f"   GET {base_url}/whatsapp/webhook?hub.mode=subscribe&hub.verify_token={verify_token}&hub.challenge=CHALLENGE")
    log("   Respuesta esperada: 'CHALLENGE' (text/plain)")
    
    log("\n4️⃣ Probar recepción de mensajes:")
    log("   - Envía mensaje desde WhatsApp al número configurado")
    log("   - Meta enviará POST a /whatsapp/webhook")
    log("   - Verifica logs del backend para confirmar recepción")
    
    log("\n5️⃣ Verificar notificaciones internas:")
    log(f"   - Mensajes con handoff → notificación a TEST_NOTIFY_NUMBER")
    log("   - Verifica que el número recibe WhatsApp con formato:")
    log("     💰 ATENCIÓN COMERCIAL o ⚙️ ATENCIÓN TÉCNICA")
    
    log("\n6️⃣ Verificar shadow mode:")
    log("   - Después de handoff → conversation_mode = HUMAN_ACTIVE")
    log("   - Bot no responde automáticamente")
    log("   - Consulta DB: SELECT conversation_mode FROM conversations WHERE conversation_id = '...'")
    
    log("\n" + "=" * 70)


def main() -> int:
    log("🏁 Ejecutando Go/No-Go suite para WhatsApp + OpenAI...")
    log(f"BASE_URL={BASE_URL}")
    log(f"DB_PATH={DB_PATH}")

    if not DB_PATH.exists():
        log("❌ DB no encontrada. Ejecuta primero `python scripts/init_db.py` y corre el servidor.")
        return 1

    try:
        conn = get_connection(DB_PATH)
        cols = conn.execute("PRAGMA table_info(interaction_traces)").fetchall()
        if not cols:
            log("❌ Tabla interaction_traces no encontrada. Inicializa la base de datos.")
            return 1
    except Exception as exc:
        log(f"❌ Error abriendo DB: {exc}")
        return 1

    results: List[ScenarioResult] = []

    # Verificar configuración
    log("\n📋 Verificando configuración...")
    whatsapp_ok, whatsapp_warnings = check_whatsapp_config()
    openai_ok, openai_warnings = check_openai_config()
    
    if whatsapp_warnings:
        log("⚠️ WhatsApp config warnings:")
        for w in whatsapp_warnings:
            log(f"   - {w}")
    
    if openai_warnings:
        log("⚠️ OpenAI config warnings:")
        for w in openai_warnings:
            log(f"   - {w}")

    with httpx.Client(base_url=BASE_URL) as client:
        # 1) Health
        health_result = run_health(client)
        results.append(health_result)
        openai_enabled_in_health = False
        whatsapp_enabled_in_health = False
        
        if health_result.ok:
            modules = health_result.details.get("response", {}).get("modules", {})
            openai_enabled_in_health = bool(modules.get("openai"))
            whatsapp_enabled_in_health = bool(modules.get("whatsapp"))
            log(f"\n✅ Health OK - OpenAI: {openai_enabled_in_health}, WhatsApp: {whatsapp_enabled_in_health}")
        else:
            log("⚠️ Health check falló; continuando con los demás escenarios.")

        # 2) Saludo (NO OpenAI, NO asset)
        log("\n📝 Ejecutando escenario: saludo...")
        results.append(
            run_chat_case(client, conn, "saludo", "hola, ¿cómo estás?", validate_saludo)
        )

        # 3) No negocio (NO OpenAI)
        log("📝 Ejecutando escenario: non-business...")
        results.append(
            run_chat_case(
                client,
                conn,
                "nonbusiness",
                "cómo hago un for en python",
                validate_non_business,
            )
        )

        # 4) FAQ horarios (NO OpenAI, cacheable)
        log("📝 Ejecutando escenario: FAQ horarios (warm)...")
        results.append(
            run_chat_case(
                client,
                conn,
                "faq-horarios-1",
                "¿cuáles son los horarios?",
                lambda r, t, d: validate_faq(r, t, d, expect_cache_hit=False),
            )
        )
        log("📝 Ejecutando escenario: FAQ horarios (cache hit)...")
        results.append(
            run_chat_case(
                client,
                conn,
                "faq-horarios-2",
                "¿cuáles son los horarios?",
                lambda r, t, d: validate_faq(r, t, d, expect_cache_hit=True),
                expect_cache_hit=True,
            )
        )

        # 5) Caso OpenAI (solo si está habilitado)
        if openai_enabled_in_health:
            log("📝 Ejecutando escenario: OpenAI allowed (complex consult)...")
            results.append(
                run_chat_case(
                    client,
                    conn,
                    "openai-consult",
                    "tengo un taller de botas con cuero grueso y quiero optimizar la ergonomía y el flujo, ¿qué configuraciones avanzadas de máquina recomiendas?",
                    validate_openai_allowed,
                )
            )
        else:
            log("ℹ️ OPENAI_ENABLED=false según /health; se omite prueba de OpenAI.")

    # Resumen final
    log("\n" + "=" * 70)
    log("================ GO / NO-GO RESULTADO =================")
    log("=" * 70)
    
    overall_ok = True
    for res in results:
        status = "✅ PASS" if res.ok else "❌ FAIL"
        if not res.ok:
            overall_ok = False
        log(f"[{status}] {res.name}: {res.reason}")
        if not res.ok:
            log(f"    details: {res.details}")

    log("\n📊 Resumen de validaciones:")
    log(f"   - Health check: {'✅' if health_result.ok else '❌'}")
    log(f"   - Saludo (no OpenAI): {'✅' if any(r.name == 'saludo' and r.ok for r in results) else '❌'}")
    log(f"   - Non-business (no OpenAI): {'✅' if any(r.name == 'nonbusiness' and r.ok for r in results) else '❌'}")
    log(f"   - FAQ (no OpenAI): {'✅' if any(r.name.startswith('faq-horarios') and r.ok for r in results) else '❌'}")
    if openai_enabled_in_health:
        log(f"   - OpenAI allowed: {'✅' if any(r.name == 'openai-consult' and r.ok for r in results) else '❌'}")

    log("\n🔗 Rutas relevantes:")
    log(f"   - Health: {BASE_URL}/health")
    log(f"   - Chat:   {BASE_URL}/api/chat")
    log(f"   - WhatsApp webhook: {BASE_URL}/whatsapp/webhook")
    log(f"   - DB:     {DB_PATH}")

    # Instrucciones WhatsApp si está habilitado
    if whatsapp_enabled_in_health or whatsapp_ok:
        print_whatsapp_instructions(BASE_URL)

    if overall_ok:
        log("\n✅ RESULTADO FINAL: GO (todas las verificaciones pasaron)")
        log("   El sistema está listo para producción con las configuraciones actuales.")
        return 0
    else:
        log("\n❌ RESULTADO FINAL: NO-GO (ver fallas arriba)")
        log("   Corrige los problemas antes de desplegar a producción.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

