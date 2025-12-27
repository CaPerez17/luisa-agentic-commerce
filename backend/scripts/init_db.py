"""
Script to initialize the database schema for LUISA.
Run this to create all required tables from scratch.

Usage:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import init_db
from app.config import DB_PATH


def main():
    """Initialize database schema."""
    print(f"🔧 Initializing database at: {DB_PATH}")
    
    try:
        init_db()
        print("✅ Database initialized successfully!")
        print(f"📊 Database location: {DB_PATH}")
        print("\n📋 Tables created:")
        print("  - conversations (customer conversations)")
        print("  - messages (conversation history)")
        print("  - handoffs (escalation to humans)")
        print("  - catalog_items (product catalog)")
        print("  - interaction_traces (analytics & traceability)")
        print("  - notifications (WhatsApp notifications)")
        print("  - conversation_modes (AI/Human mode tracking)")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

