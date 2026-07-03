#!/bin/bash
# One-time migration script for servers deployed before Jackett support was added.
# Safe to delete this file once all existing installations have been updated.
set -e

REPO="tskon-kz/media-server"
RAW="https://raw.githubusercontent.com/$REPO/main"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "1) English"
echo "2) Русский"
printf "Select language / Выберите язык [1/2]: "
read -r LANG_CHOICE
case "$LANG_CHOICE" in
    2) source "$SCRIPT_DIR/lang/ru.sh" ;;
    *) source "$SCRIPT_DIR/lang/en.sh" ;;
esac

echo ""
echo "$MSG_JACKETT_TITLE"
echo ""

# Verify this is an existing installation
if [ ! -f "$SCRIPT_DIR/.env" ] || [ ! -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    echo "$MSG_JACKETT_NO_ENV"
    exit 1
fi

cd "$SCRIPT_DIR"

# Idempotency: skip if jackett already present
if grep -q "jackett" docker-compose.yml 2>/dev/null; then
    echo "$MSG_JACKETT_ALREADY_DONE"
    exit 0
fi

# Update docker-compose.yml
echo "$MSG_JACKETT_UPDATING"
curl -fsSL "$RAW/docker-compose.yml" -o docker-compose.yml

# Add JACKETT_PORT to .env if missing
if ! grep -q "JACKETT_PORT" .env 2>/dev/null; then
    echo "" >> .env
    echo "# Optional — Jackett web UI port (default: 9117)" >> .env
    echo "# JACKETT_PORT=9117" >> .env
fi

# Pull new image and start all services
echo "$MSG_JACKETT_STARTING"
docker compose pull
docker compose up -d

# Resolve JACKETT_PORT for the final message
JACKETT_PORT=$(grep "^JACKETT_PORT=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
JACKETT_PORT="${JACKETT_PORT:-9117}"

# Try to get server_ip from SQLite DB
SERVER_IP=$(python3 -c "
import sqlite3, os
try:
    db = sqlite3.connect(os.path.join('$SCRIPT_DIR', 'bot-data', 'media_server.db'))
    r = db.execute(\"SELECT value FROM config WHERE key='server_ip'\").fetchone()
    print(r[0] if r and r[0] else 'YOUR_SERVER_IP')
except Exception:
    print('YOUR_SERVER_IP')
" 2>/dev/null || echo "YOUR_SERVER_IP")

echo ""
echo "$MSG_JACKETT_DONE_TITLE"
echo ""
echo "$MSG_JACKETT_DONE_NEXT"
echo "$MSG_JACKETT_DONE_1"
echo "     http://$SERVER_IP:$JACKETT_PORT"
echo "$MSG_JACKETT_DONE_2"
echo "$MSG_JACKETT_DONE_3"
echo "$MSG_JACKETT_DONE_UPDATE"
echo "$MSG_JACKETT_DONE_UPDATE2"
echo ""
