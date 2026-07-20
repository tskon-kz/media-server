#!/bin/bash
# bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/update.sh)
set -e

REPO="tskon-kz/media-server"
RAW="https://raw.githubusercontent.com/$REPO/main"
INSTALL_DIR="$HOME/media-server"

# Run the latest update.sh even when this on-disk copy is stale: download it and
# re-exec once (guarded against a loop). Falls back to the local copy if offline.
if [ -z "${UPDATE_SH_REEXEC:-}" ]; then
    _self="$(mktemp)"
    if curl -fsSL "$RAW/update.sh" -o "$_self" && [ -s "$_self" ]; then
        export UPDATE_SH_REEXEC="$_self"
        exec bash "$_self" "$@"
    fi
    rm -f "$_self"
    echo "  ⚠ couldn't fetch latest update.sh; running local copy" >&2
fi
[ -n "${UPDATE_SH_REEXEC:-}" ] && trap 'rm -f "$UPDATE_SH_REEXEC"' EXIT

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

# WEBAPP_DOMAIN in .env drives the proxy: set -> caddy (own-domain profile),
# unset -> default quick tunnel. Exported for this run only, not persisted.
if grep -q "^WEBAPP_DOMAIN=." .env 2>/dev/null; then
    export COMPOSE_PROFILES="own-domain"
else
    unset COMPOSE_PROFILES
fi

echo "⬇  Fetching latest files from GitHub..."
if [ ! -d .git ]; then
    git init -q
    git remote add origin "https://github.com/$REPO.git"
elif ! git remote get-url origin &>/dev/null 2>&1; then
    git remote add origin "https://github.com/$REPO.git"
fi
git fetch --depth=1 -q origin main
git checkout --force FETCH_HEAD -- .
chmod +x update.sh teardown.sh migrate-media.sh

echo "⏹  Stopping containers..."
# --remove-orphans clears the proxy being switched off (it's out of profile scope).
COMPOSE_PROFILES=own-domain docker compose down --remove-orphans

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

echo "🔨  Rebuilding upscaler (local image)..."
docker compose build upscaler

echo "▶  Starting containers..."
docker compose up -d

echo ""
echo "✓ Update complete"
