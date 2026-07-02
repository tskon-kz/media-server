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
