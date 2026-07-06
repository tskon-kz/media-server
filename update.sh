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

echo "⬇  Downloading latest files..."
curl -fsSL "$RAW/docker-compose.yml" -o docker-compose.new.yml
curl -fsSL "$RAW/update.sh"          -o update.sh && chmod +x update.sh
mkdir -p lang
curl -fsSL "$RAW/lang/en.sh"         -o lang/en.sh
curl -fsSL "$RAW/lang/ru.sh"         -o lang/ru.sh

echo "⏹  Stopping containers..."
docker compose down

echo "📄  Applying new docker-compose.yml..."
mv docker-compose.new.yml docker-compose.yml

echo "📦  Pulling latest images..."
docker compose pull

echo "▶  Starting containers..."
docker compose up -d

echo ""
echo "✓ Update complete"
