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

echo "⬇  Fetching latest files from 'dev' branch..."
if [ ! -d .git ]; then
    git init -q
    git remote add origin "https://github.com/$REPO.git"
elif ! git remote get-url origin &>/dev/null 2>&1; then
    git remote add origin "https://github.com/$REPO.git"
fi
git fetch --depth=1 -q origin dev
git checkout --force origin/dev -- .
chmod +x update.sh update-dev.sh teardown.sh migrate-media.sh

echo "⏹  Stopping containers..."
docker compose down

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
