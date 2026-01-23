#!/usr/bin/env python3
"""
Script para detectar y revertir conversaciones en HUMAN_ACTIVE que han excedido el TTL.

Ejecuta:
1. Query: SELECT conversation_id, mode_updated_at_epoch FROM conversations WHERE conversation_mode = 'HUMAN_ACTIVE'
2. Calcula: now_epoch - mode_updated_at_epoch > ttl_seconds
3. Revierte: UPDATE conversations SET conversation_mode = 'AI_ACTIVE' WHERE conversation_id = ...
4. Loguea: fixed_count
"""
import sys
import time
from pathlib import Path

# Agregar backend al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.database import get_connection
from app.config import HUMAN_TTL_HOURS
from app.logging_config import logger


def main():
    """Función principal."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Query: conversaciones en HUMAN_ACTIVE
        cursor.execute("""
            SELECT conversation_id, mode_updated_at_epoch, created_at
            FROM conversations
            WHERE conversation_mode = 'HUMAN_ACTIVE'
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            print("✅ No hay conversaciones en HUMAN_ACTIVE")
            return 0
        
        now_epoch = int(time.time())
        ttl_seconds = HUMAN_TTL_HOURS * 3600
        fixed_count = 0
        fixed_conversations = []
        
        for row in rows:
            conversation_id = row[0]
            mode_updated_at_epoch = row[1]
            created_at = row[2]
            
            should_fix = False
            
            if mode_updated_at_epoch:
                # Usar epoch (preferido)
                elapsed_seconds = now_epoch - mode_updated_at_epoch
                if elapsed_seconds > ttl_seconds:
                    should_fix = True
            elif created_at:
                # Fallback: usar created_at + 24h
                from datetime import datetime, timezone
                try:
                    if isinstance(created_at, str):
                        created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00").replace(" ", "T"))
                        if created_time.tzinfo is None:
                            created_time = created_time.replace(tzinfo=timezone.utc)
                    else:
                        created_time = created_at
                        if created_time.tzinfo is None:
                            created_time = created_time.replace(tzinfo=timezone.utc)
                    
                    now_utc = datetime.now(timezone.utc)
                    elapsed = now_utc - created_time
                    if elapsed.total_seconds() > 86400:  # 24 horas
                        should_fix = True
                except:
                    # Si no podemos parsear, asumir que está vencido
                    should_fix = True
            else:
                # Sin timestamp: asumir vencido
                should_fix = True
            
            if should_fix:
                # Revertir a AI_ACTIVE
                cursor.execute("""
                    UPDATE conversations
                    SET conversation_mode = 'AI_ACTIVE',
                        mode_updated_at = CURRENT_TIMESTAMP,
                        mode_updated_at_epoch = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = ?
                """, (now_epoch, conversation_id))
                
                fixed_count += 1
                fixed_conversations.append(conversation_id)
        
        conn.commit()
        
        if fixed_count > 0:
            logger.info(
                "fix_stuck_human_active",
                fixed_count=fixed_count,
                conversations=fixed_conversations[:10],  # Primeros 10 para logging
                ttl_hours=HUMAN_TTL_HOURS
            )
            print(f"✅ Revertidas {fixed_count} conversaciones de HUMAN_ACTIVE a AI_ACTIVE")
            if len(fixed_conversations) > 10:
                print(f"   (mostrando primeras 10: {', '.join(fixed_conversations[:10])})")
        else:
            print(f"✅ Todas las conversaciones en HUMAN_ACTIVE están dentro del TTL ({HUMAN_TTL_HOURS}h)")
        
        return 0
    
    except Exception as e:
        logger.error("Error en fix_stuck_human_active", error=str(e))
        print(f"❌ Error: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
