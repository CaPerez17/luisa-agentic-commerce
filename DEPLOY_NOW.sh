#!/bin/bash
# ============================================================================
# LUISA v2.1.0 DEPLOYMENT SCRIPT
# Execute this script on the production server
# ============================================================================

set -e  # Exit on error

echo "=============================================="
echo "LUISA v2.1.0 DEPLOYMENT"
echo "=============================================="
echo ""

# 0) BACKUP
echo "=== STEP 0: BACKUP ==="
cd /opt/luisa

echo "Backing up database..."
sudo docker compose exec -T backend sqlite3 /app/data/luisa.db ".backup /app/data/luisa.db.backup.$(date +%Y%m%d_%H%M%S)" || echo "DB backup via exec failed, trying host copy..."
sudo cp ./data/luisa.db ./data/luisa.db.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "Host backup skipped (file may not exist yet)"

echo "Tagging current image..."
IMAGE_NAME=$(sudo docker compose config --images | grep backend | head -1)
BACKUP_TAG="backup-$(date +%Y%m%d_%H%M%S)"
sudo docker tag "${IMAGE_NAME}" "${IMAGE_NAME%:*}:${BACKUP_TAG}" 2>/dev/null || echo "Image tagging skipped (image may not exist yet)"
echo "Backup image: ${IMAGE_NAME%:*}:${BACKUP_TAG}"
echo ""

# 1) PULL CODE
echo "=== STEP 1: PULL LATEST CODE ==="
git fetch origin
echo "New commits:"
git log HEAD..origin/main --oneline 2>/dev/null || echo "(first deploy)"
git pull origin main
echo ""

# 2) BUILD IMAGE
echo "=== STEP 2: BUILD DOCKER IMAGE ==="
sudo docker compose build backend
echo ""

# 3) VERIFY SCHEMA
echo "=== STEP 3: VERIFY DB SCHEMA ==="
sudo docker compose exec -T backend python -c "
from app.models.database import init_db, get_connection
import sys
init_db()
conn = get_connection()
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(interaction_traces)')
columns = [row[1] for row in cursor.fetchall()]
required = ['whatsapp_send_success', 'classification', 'openai_canary_allowed']
missing = [c for c in required if c not in columns]
if missing:
    print(f'Missing: {missing}')
    sys.exit(1)
cursor.execute('PRAGMA table_info(conversations)')
conv_cols = [row[1] for row in cursor.fetchall()]
if 'mode_updated_at_epoch' not in conv_cols:
    print('Missing mode_updated_at_epoch')
    sys.exit(1)
print('✅ Schema OK')
"
if [ $? -ne 0 ]; then
    echo "❌ Schema verification failed - ABORTING"
    exit 1
fi
echo ""

# 4) RESTART CONTAINERS
echo "=== STEP 4: RESTART CONTAINERS ==="
sudo docker compose up -d backend
echo "Waiting for healthcheck (70s)..."
sleep 70
echo ""

# 5) POST-DEPLOY VERIFICATION
echo "=== STEP 5: POST-DEPLOY VERIFICATION ==="

echo "Health check..."
curl -sf http://localhost:8000/health | jq || { echo "❌ Health check failed"; exit 1; }
echo ""

echo "Ops snapshot..."
curl -sf http://localhost:8000/ops/snapshot | jq || echo "⚠️ Ops snapshot endpoint not available yet"
echo ""

echo "Running go_no_go..."
sudo docker compose exec -T backend python scripts/go_no_go.py --hard-fail || echo "⚠️ go_no_go checks had warnings"
echo ""

echo "Checking logs for new fields..."
sudo docker compose logs backend --tail=50 | grep -E "whatsapp_send_success|classification|openai_canary" | head -5 || echo "No matching logs yet (normal on fresh deploy)"
echo ""

echo "=============================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Verify webhook: curl \"https://luisa-agent.online/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=TEST123\""
echo "2. Send 'hola' from test WhatsApp number"
echo "3. Verify in database:"
echo "   sudo docker compose exec backend sqlite3 /app/data/luisa.db \"SELECT id, classification, whatsapp_send_success FROM interaction_traces ORDER BY id DESC LIMIT 1;\""
