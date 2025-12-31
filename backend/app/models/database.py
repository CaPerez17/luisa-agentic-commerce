"""
Gestión de base de datos SQLite para LUISA.
Incluye tablas legacy + nuevas (trazas, notificaciones, modo sombra).
"""
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional, List, Dict, Any
from datetime import datetime

from app.config import DB_PATH


def get_connection(timeout: float = 10.0) -> sqlite3.Connection:
    """Obtiene una conexión a la base de datos."""
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager para conexiones de base de datos."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Inicializa todas las tablas de la base de datos."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # ================================================================
        # TABLAS LEGACY (mantener compatibilidad)
        # ================================================================
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                customer_name TEXT,
                customer_phone TEXT,
                status TEXT DEFAULT 'active',
                conversation_mode TEXT DEFAULT 'AI_ACTIVE',
                mode_updated_at TIMESTAMP,
                channel TEXT DEFAULT 'api',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                text TEXT,
                sender TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS handoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                reason TEXT,
                priority TEXT,
                summary TEXT,
                suggested_response TEXT,
                customer_name TEXT,
                routed_team TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalog_items (
                image_id TEXT PRIMARY KEY,
                title TEXT,
                category TEXT,
                brand TEXT,
                model TEXT,
                represents TEXT,
                conversation_role TEXT,
                priority INTEGER,
                send_when_customer_says TEXT,
                meta_json TEXT,
                drive_file_id TEXT,
                drive_mime_type TEXT,
                asset_provider TEXT DEFAULT 'local',
                file_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                cache_key TEXT PRIMARY KEY,
                file_path TEXT,
                drive_file_id TEXT,
                mime_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)
        
        # ================================================================
        # NUEVAS TABLAS
        # ================================================================
        
        # Tabla de trazas de interacciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                conversation_id TEXT,
                channel TEXT,
                customer_phone_hash TEXT,
                raw_text TEXT,
                normalized_text TEXT,
                business_related INTEGER,
                intent TEXT,
                routed_team TEXT,
                selected_asset_id TEXT,
                openai_called INTEGER DEFAULT 0,
                prompt_version TEXT,
                cache_hit INTEGER DEFAULT 0,
                response_text TEXT,
                latency_ms REAL,
                latency_us INTEGER DEFAULT 0,
                decision_path TEXT,
                response_len_chars INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de notificaciones internas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                team TEXT,
                notification_text TEXT,
                destination_number TEXT,
                sent_at TIMESTAMP,
                delivery_status TEXT DEFAULT 'pending',
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices para mejor rendimiento
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation 
            ON messages(conversation_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_conversation 
            ON interaction_traces(conversation_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_created 
            ON interaction_traces(created_at)
        """)

        # Agregar columnas nuevas a tablas existentes si no existen
        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN conversation_mode TEXT DEFAULT 'AI_ACTIVE'")
        except sqlite3.OperationalError:
            pass  # Columna ya existe

        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN mode_updated_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN customer_phone TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN channel TEXT DEFAULT 'api'")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE handoffs ADD COLUMN routed_team TEXT")
        except sqlite3.OperationalError:
            pass

        # Migraciones adicionales para interaction_traces
        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN error_message TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN customer_phone_hash TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN normalized_text TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN selected_asset_id TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN prompt_version TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN decision_path TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN response_len_chars INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE interaction_traces ADD COLUMN latency_us INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # Tabla para idempotencia de mensajes WhatsApp
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wa_processed_messages (
                message_id TEXT PRIMARY KEY,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                phone_from TEXT,
                text_preview TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_processed_received 
            ON wa_processed_messages(received_at)
        """)
        
        # Tabla para deduplicación de outbox (anti-spam)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wa_outbox_dedup (
                dedup_key TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ttl_seconds INTEGER DEFAULT 120,
                phone_to TEXT,
                text_preview TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_outbox_created 
            ON wa_outbox_dedup(created_at)
        """)
        
        # Tabla para estado conversacional (Sales Dialogue Manager)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wa_conversations (
                phone_from TEXT PRIMARY KEY,
                state_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_conversations_updated 
            ON wa_conversations(updated_at)
        """)
        
        # Configurar SQLite para mejor concurrencia
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=3000")


# ============================================================================
# FUNCIONES DE ACCESO A DATOS
# ============================================================================

def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene una conversación por ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?",
            (conversation_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def create_or_update_conversation(
    conversation_id: str,
    customer_phone: Optional[str] = None,
    channel: str = "api"
) -> None:
    """Crea o actualiza una conversación."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (conversation_id, customer_phone, channel, status, conversation_mode)
            VALUES (?, ?, ?, 'active', 'AI_ACTIVE')
            ON CONFLICT(conversation_id) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP,
                customer_phone = COALESCE(?, customer_phone),
                channel = COALESCE(?, channel)
        """, (conversation_id, customer_phone, channel, customer_phone, channel))


def get_conversation_mode(conversation_id: str) -> str:
    """Obtiene el modo actual de la conversación (AI_ACTIVE o HUMAN_ACTIVE)."""
    conversation = get_conversation(conversation_id)
    if conversation:
        return conversation.get("conversation_mode") or "AI_ACTIVE"
    return "AI_ACTIVE"


def set_conversation_mode(conversation_id: str, mode: str) -> None:
    """Establece el modo de la conversación."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE conversations 
            SET conversation_mode = ?, mode_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE conversation_id = ?
        """, (mode, conversation_id))


def get_conversation_history(conversation_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Obtiene el historial de mensajes de una conversación."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT text, sender, timestamp 
            FROM messages 
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (conversation_id, limit))
        return [dict(row) for row in cursor.fetchall()]


def save_message(conversation_id: str, text: str, sender: str) -> None:
    """Guarda un mensaje en el historial."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (conversation_id, text, sender)
            VALUES (?, ?, ?)
        """, (conversation_id, text, sender))


def save_trace(
    request_id: str,
    conversation_id: str,
    channel: str,
    customer_phone_hash: Optional[str],
    raw_text: str,
    normalized_text: str,
    business_related: bool,
    intent: Optional[str],
    routed_team: Optional[str],
    selected_asset_id: Optional[str],
    openai_called: bool,
    prompt_version: Optional[str],
    cache_hit: bool,
    response_text: str,
    latency_ms: float,
    latency_us: int,
    message_type: Optional[str] = None,
    decision_path: Optional[str] = None,
    response_len_chars: int = 0,
    error_message: Optional[str] = None
) -> None:
    """Guarda una traza de interacción."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interaction_traces (
                request_id, conversation_id, channel, customer_phone_hash,
                raw_text, normalized_text, business_related, intent,
                routed_team, selected_asset_id, openai_called, prompt_version,
                cache_hit, response_text, latency_ms, latency_us, message_type,
                decision_path, response_len_chars, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id, conversation_id, channel, customer_phone_hash,
            raw_text, normalized_text, int(business_related), intent,
            routed_team, selected_asset_id, int(openai_called), prompt_version,
            int(cache_hit), response_text, latency_ms, latency_us, message_type,
            decision_path, response_len_chars, error_message
        ))


def save_notification(
    conversation_id: str,
    team: str,
    notification_text: str,
    destination_number: str
) -> int:
    """Guarda una notificación interna."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (conversation_id, team, notification_text, destination_number)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, team, notification_text, destination_number))
        return cursor.lastrowid


def update_notification_status(notification_id: int, status: str, error: Optional[str] = None) -> None:
    """Actualiza el estado de entrega de una notificación."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notifications 
            SET delivery_status = ?, sent_at = CURRENT_TIMESTAMP, error = ?
            WHERE id = ?
        """, (status, error, notification_id))


def get_handoffs(limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene los handoffs más recientes."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT conversation_id, reason, priority, summary, suggested_response, 
                   customer_name, routed_team, timestamp
            FROM handoffs
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def save_handoff(
    conversation_id: str,
    reason: str,
    priority: str,
    summary: str,
    suggested_response: str,
    customer_name: Optional[str],
    routed_team: Optional[str] = None
) -> None:
    """Guarda un handoff en la base de datos."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO handoffs 
            (conversation_id, reason, priority, summary, suggested_response, customer_name, routed_team)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (conversation_id, reason, priority, summary, suggested_response, customer_name, routed_team))


def mark_wa_message_processed(message_id: str, phone_from: str, text_preview: str = "") -> bool:
    """
    Marca un mensaje de WhatsApp como procesado (idempotencia).
    
    Returns:
        True si el mensaje es nuevo (se insertó), False si ya existía (duplicado)
    """
    if not message_id:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        # INSERT OR IGNORE: si ya existe, no hace nada y retorna 0 cambios
        cursor.execute("""
            INSERT OR IGNORE INTO wa_processed_messages (message_id, phone_from, text_preview)
            VALUES (?, ?, ?)
        """, (message_id, phone_from[-4:] if phone_from else "", text_preview[:50] if text_preview else ""))
        
        # Si se insertó, lastrowid será el rowid del nuevo registro
        # Si no se insertó (ya existía), lastrowid será 0
        return cursor.rowcount > 0


def is_wa_message_processed(message_id: str) -> bool:
    """Verifica si un mensaje ya fue procesado."""
    if not message_id:
        return False
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM wa_processed_messages WHERE message_id = ?", (message_id,))
        return cursor.fetchone() is not None


def check_outbox_dedup(phone_to: str, text: str, ttl_seconds: int = 120) -> bool:
    """
    Verifica si ya enviamos un mensaje similar recientemente (anti-spam).
    
    Args:
        phone_to: Número de destino
        text: Texto del mensaje
        ttl_seconds: TTL en segundos (default 120 = 2 minutos)
    
    Returns:
        True si ya existe (no enviar), False si es nuevo (puede enviar)
    """
    if not phone_to or not text:
        return False
    
    # Normalizar texto (lowercase, sin espacios extra)
    normalized_text = " ".join(text.lower().strip().split()[:10])  # Primeras 10 palabras
    
    # Crear dedup_key: phone:normalized_text:minute_bucket
    from datetime import datetime
    now = datetime.utcnow()
    minute_bucket = now.strftime("%Y%m%d%H%M")  # Ventana de 1 minuto
    
    dedup_key = f"{phone_to}:{normalized_text[:50]}:{minute_bucket}"
    
    with get_db() as conn:
        cursor = conn.cursor()
        # Verificar si existe y no ha expirado
        cursor.execute("""
            SELECT 1 FROM wa_outbox_dedup 
            WHERE dedup_key = ? 
            AND (julianday('now') - julianday(created_at)) * 86400 < ttl_seconds
        """, (dedup_key,))
        
        if cursor.fetchone():
            return True  # Ya existe, no enviar
        
        # Insertar nuevo registro
        cursor.execute("""
            INSERT OR REPLACE INTO wa_outbox_dedup (dedup_key, phone_to, text_preview, ttl_seconds)
            VALUES (?, ?, ?, ?)
        """, (dedup_key, phone_to[-4:] if phone_to else "", text[:50], ttl_seconds))
        
        return False  # Es nuevo, puede enviar


def cleanup_expired_outbox_dedup():
    """Limpia registros expirados de outbox_dedup (ejecutar periódicamente)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM wa_outbox_dedup 
            WHERE (julianday('now') - julianday(created_at)) * 86400 > ttl_seconds
        """)


def get_conversation_state(phone_from: str) -> dict:
    """
    Obtiene el estado conversacional de un usuario.
    
    Returns:
        Dict con state_json parseado o estado por defecto si no existe
    """
    import json
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT state_json FROM wa_conversations WHERE phone_from = ?",
            (phone_from,)
        )
        row = cursor.fetchone()
        
        if row and row[0]:
            try:
                return json.loads(row[0])
            except:
                return _default_conversation_state()
        
        return _default_conversation_state()


def save_conversation_state(phone_from: str, state: dict) -> None:
    """
    Guarda el estado conversacional de un usuario.
    
    Args:
        phone_from: Número de teléfono (clave primaria)
        state: Dict con el estado (se serializa a JSON)
    """
    import json
    
    state_json = json.dumps(state, ensure_ascii=False)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO wa_conversations (phone_from, state_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (phone_from, state_json))


def reset_conversation_state(phone_from: str) -> None:
    """Resetea el estado conversacional a valores por defecto."""
    save_conversation_state(phone_from, _default_conversation_state())


def _default_conversation_state() -> dict:
    """Retorna el estado conversacional por defecto."""
    return {
        "stage": "discovery",  # discovery | pricing | visit | shipping | photos | support
        "last_question": None,
        "asked_questions": {},
        "slots": {
            "product_type": None,  # "familiar" | "industrial"
            "use_case": None,  # "ropa" | "gorras" | "calzado" | "accesorios"
            "city": None,
            "qty": None,
            "visit_or_delivery": None,  # "visit" | "delivery"
            "budget": None
        },
        "last_intent": None,
        "last_message_ts": None,
        "handoff_needed": False,
        "pending_question": None
    }
