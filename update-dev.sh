#!/bin/bash
# Dev-server update: pulls files from the 'dev' branch and the :dev bot image.
# bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/dev/update-dev.sh)
set -e

REPO="tskon-kz/media-server"
RAW="https://raw.githubusercontent.com/$REPO/dev"
INSTALL_DIR="$HOME/media-server"

if [ ! -f "$INSTALL_DIR/docker-compose.yml" ]; then
    echo "Error: $INSTALL_DIR not found. Run install.sh first."
    exit 1
fi

cd "$INSTALL_DIR"

# Dev servers always track the :dev image tag.
BOT_IMAGE_TAG="dev"
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

echo "⬇  Downloading latest files from 'dev' branch..."
_curl_fetch "$RAW/docker-compose.yml"   docker-compose.new.yml
_curl_fetch "$RAW/update-dev.sh"        update-dev.sh && chmod +x update-dev.sh
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

echo "📦  Pulling latest :dev bot image..."
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
echo "✓ Dev update complete (branch: dev, image: :dev)"
