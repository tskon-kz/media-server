#!/bin/bash
# bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/update.sh)
set -e

REPO="tskon-kz/media-server"
RAW="https://raw.githubusercontent.com/$REPO/main"
INSTALL_DIR="$HOME/media-server"

if [ ! -f "$INSTALL_DIR/docker-compose.yml" ]; then
    echo "Error: $INSTALL_DIR not found. Run install.sh first."
    exit 1
fi

cd "$INSTALL_DIR"

DB_FILE="$INSTALL_DIR/bot-data/media_server.db"

# The bot image tag is chosen at runtime via the Telegram "Update"/"Force update"
# actions, which persist it to the DB (bot_image_tag). docker-compose reads it
# from .env at cold start, so keep the two in sync here: DB wins, default :stable.
BOT_IMAGE_TAG="$(python3 - "$DB_FILE" << 'PYEOF'
import sqlite3, os, sys
db = sys.argv[1]
tag = "stable"
if os.path.exists(db):
    row = sqlite3.connect(db).execute(
        "SELECT value FROM config WHERE key='bot_image_tag' AND value IS NOT NULL AND value != ''"
    ).fetchone()
    if row:
        tag = row[0]
print(tag)
PYEOF
)"
export BOT_IMAGE_TAG
if grep -q "^BOT_IMAGE_TAG=" .env 2>/dev/null; then
    sed -i.bak "s|^BOT_IMAGE_TAG=.*|BOT_IMAGE_TAG=$BOT_IMAGE_TAG|" .env && rm -f .env.bak
else
    echo "BOT_IMAGE_TAG=$BOT_IMAGE_TAG" >> .env
fi

_curl_fetch() {  # _curl_fetch <url> <output_path>  — downloads with timeouts and retries
    local url="$1" out="$2"
    curl -fsSL \
        --connect-timeout 10 \
        --max-time 60 \
        --retry 3 \
        --retry-delay 2 \
        --retry-all-errors \
        -o "$out" "$url"
}

echo "⬇  Downloading latest files..."
_curl_fetch "$RAW/docker-compose.yml"   docker-compose.new.yml
_curl_fetch "$RAW/update.sh"            update.sh && chmod +x update.sh
_curl_fetch "$RAW/migrate-media.sh"     migrate-media.sh && chmod +x migrate-media.sh
_curl_fetch "$RAW/teardown.sh"          teardown.sh && chmod +x teardown.sh
mkdir -p lang
_curl_fetch "$RAW/lang/en.sh"           lang/en.sh
_curl_fetch "$RAW/lang/ru.sh"           lang/ru.sh
mkdir -p upscaler
_curl_fetch "$RAW/upscaler/Dockerfile"  upscaler/Dockerfile
_curl_fetch "$RAW/upscaler/main.py"     upscaler/main.py
_curl_fetch "$RAW/upscaler/db.py"       upscaler/db.py
_curl_fetch "$RAW/upscaler/runners.py"  upscaler/runners.py

echo "⏹  Stopping containers..."
docker compose down

echo "📄  Applying new docker-compose.yml..."
mv docker-compose.new.yml docker-compose.yml

echo "📦  Pulling latest bot image..."
# Only the bot image — the other services are pinned to :latest and must not be
# silently upgraded/recreated by a bot update (see bot/updater.sh for the why).
_pull_attempt=1; _pull_max=3
until docker compose pull telegram-bot; do
    if [ "$_pull_attempt" -ge "$_pull_max" ]; then
        echo "  ✗ docker compose pull failed after $_pull_max attempts" >&2
        exit 1
    fi
    echo "  retrying pull (attempt $((_pull_attempt+1))/$_pull_max)..."
    sleep $((_pull_attempt * 3))
    _pull_attempt=$((_pull_attempt + 1))
done

echo "▶  Starting containers..."
docker compose up -d

echo ""
echo "✓ Update complete"
