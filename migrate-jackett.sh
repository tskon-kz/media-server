#!/bin/bash
# bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/migrate-jackett.sh)
# One-time migration script for servers deployed before Jackett support was added.
# Safe to delete this file once all existing installations have been updated.
set -e

REPO="tskon-kz/media-server"
RAW="https://raw.githubusercontent.com/$REPO/main"
INSTALL_DIR="$HOME/media-server"

echo "1) English"
echo "2) Русский"
printf "Select language / Выберите язык [1/2]: "
read -r LANG_CHOICE

TMP_LANG=$(mktemp -d)
curl -fsSL "$RAW/lang/en.sh" -o "$TMP_LANG/en.sh"
curl -fsSL "$RAW/lang/ru.sh" -o "$TMP_LANG/ru.sh"
case "$LANG_CHOICE" in
    2) source "$TMP_LANG/ru.sh" ;;
    *) source "$TMP_LANG/en.sh" ;;
esac

echo ""
echo "$MSG_JACKETT_TITLE"
echo ""

# Verify this is an existing installation
if [ ! -f "$INSTALL_DIR/.env" ] || [ ! -f "$INSTALL_DIR/docker-compose.yml" ]; then
    echo "$MSG_JACKETT_NO_ENV"
    exit 1
fi

cd "$INSTALL_DIR"

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

printf "%s" "$MSG_ASK_JACKETT_PASS"; read -rs JACKETT_PASS; echo

# Pull new image and start all services
echo "$MSG_JACKETT_STARTING"
docker compose pull
docker compose up -d

# ---- Jackett password setup ----

JACKETT_CFG="$INSTALL_DIR/data/jackett/config/Jackett/ServerConfig.json"
if [ -n "$JACKETT_PASS" ]; then
    printf "  %s" "$MSG_JACKETT_WAIT"
    for i in $(seq 1 30); do
        [ -f "$JACKETT_CFG" ] && break
        printf "."
        sleep 2
    done
    printf "\n"
    if [ -f "$JACKETT_CFG" ]; then
        python3 - "$JACKETT_CFG" "$JACKETT_PASS" <<'PYEOF'
import json, sys, hashlib
cfg, pw = sys.argv[1], sys.argv[2]
with open(cfg) as f:
    d = json.load(f)
d['AdminPassword'] = hashlib.sha1(pw.encode()).hexdigest()
with open(cfg, 'w') as f:
    json.dump(d, f, indent=2)
PYEOF
        docker compose restart jackett >/dev/null 2>&1
        echo "$MSG_JACKETT_PASS_SET"
    else
        echo "$MSG_JACKETT_PASS_SKIP"
    fi
else
    echo "$MSG_JACKETT_PASS_SKIP"
fi

# Resolve JACKETT_PORT for the final message
JACKETT_PORT=$(grep "^JACKETT_PORT=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
JACKETT_PORT="${JACKETT_PORT:-9117}"

# Try to get server_ip from SQLite DB
SERVER_IP=$(python3 -c "
import sqlite3, os
try:
    db = sqlite3.connect(os.path.join('$INSTALL_DIR', 'bot-data', 'media_server.db'))
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
