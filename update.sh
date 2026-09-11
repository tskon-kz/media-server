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

# .env drives the proxy, exported for this run only (not persisted):
#   WEBAPP_PROXY_PORT set -> behind-proxy (Caddy as a loopback HTTP bridge behind
#     the host's own reverse proxy); WEBAPP_DOMAIN set -> own-domain (Caddy owns
#     80/443, auto-HTTPS); neither -> default quick Cloudflare tunnel.
if grep -q "^WEBAPP_PROXY_PORT=." .env 2>/dev/null; then
    export COMPOSE_PROFILES="behind-proxy"
elif grep -q "^WEBAPP_DOMAIN=." .env 2>/dev/null; then
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
OLD_JF_IMAGE="$(grep -m1 'image: jellyfin/jellyfin' docker-compose.yml || true)"
git fetch --depth=1 -q origin main
git checkout --force FETCH_HEAD -- .
NEW_JF_IMAGE="$(grep -m1 'image: jellyfin/jellyfin' docker-compose.yml || true)"
JF_UPGRADE=""
if [ "$OLD_JF_IMAGE" != "$NEW_JF_IMAGE" ] && [ -d data/jellyfin/config ]; then
    JF_UPGRADE=1
fi
chmod +x update.sh teardown.sh migrate-media.sh

echo "⏹  Stopping containers..."
# --remove-orphans clears whichever proxy is being switched off (out of profile
# scope). Name every proxy profile so compose knows about all of them and can tear
# down the outgoing one regardless of which mode we're leaving.
COMPOSE_PROFILES=own-domain,behind-proxy docker compose down --remove-orphans

# A Jellyfin version bump migrates its DB irreversibly (12.0 can't roll back to
# 10.11 without a restore), so snapshot the config dir while containers are down.
# Done via a throwaway container: the files are root-owned inside the volume.
if [ -n "$JF_UPGRADE" ]; then
    JF_BACKUP="backups/jellyfin-config-$(date +%Y%m%d-%H%M%S).tar.gz"
    echo "💾  Backing up Jellyfin config to $JF_BACKUP (version bump detected)..."
    mkdir -p backups
    docker run --rm \
        -v "$INSTALL_DIR/data/jellyfin/config:/src:ro" \
        -v "$INSTALL_DIR/backups:/dst" \
        alpine tar czf "/dst/$(basename "$JF_BACKUP")" \
            --exclude=./log --exclude=./transcodes -C /src .
fi

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

# After a Jellyfin version bump the release notes require a full library scan
# (12.0 drops auto-resolved alternative versions until rescanned). Wait for the
# DB migration to finish (the API is down meanwhile), then kick the scan.
if [ -n "$JF_UPGRADE" ]; then
    JF_PORT="$(grep -m1 '^JELLYFIN_PORT=' .env 2>/dev/null | cut -d= -f2)"
    JF_PORT="${JF_PORT:-8096}"
    JF_API_KEY="$(python3 - "$DB_FILE" << 'PYEOF'
import sqlite3, os, sys
db = sys.argv[1]
if os.path.exists(db):
    row = sqlite3.connect(db).execute("SELECT value FROM config WHERE key='jellyfin_api_key'").fetchone()
    print(row[0] if row and row[0] else "")
PYEOF
)"
    printf "⏳  Waiting for Jellyfin to finish migrating"
    JF_READY=""
    for i in $(seq 1 120); do
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$JF_PORT/System/Info/Public" 2>/dev/null || echo "000")
        if [ "$STATUS" = "200" ]; then JF_READY=1; break; fi
        printf "."
        sleep 5
    done
    printf "\n"
    if [ -n "$JF_READY" ] && [ -n "$JF_API_KEY" ]; then
        curl -s -o /dev/null -X POST "http://localhost:$JF_PORT/Library/Refresh" \
            -H "Authorization: MediaBrowser Token=\"$JF_API_KEY\"" \
            && echo "🔍  Full library scan started (first scan after upgrade takes longer)" \
            || echo "  ⚠ couldn't trigger library scan — run it manually in Jellyfin Dashboard"
    else
        echo "  ⚠ Jellyfin not ready or no API key — run a full library scan manually in Jellyfin Dashboard"
    fi
fi

# Point Jackett at FlareSolverr (for Cloudflare-gated indexers like RuTracker).
# Idempotent: only writes + restarts jackett if the value is not already set.
JACKETT_CFG="$INSTALL_DIR/data/jackett/config/Jackett/ServerConfig.json"
if [ -f "$JACKETT_CFG" ]; then
    if python3 - "$JACKETT_CFG" <<'PYEOF'
import json, sys
cfg = sys.argv[1]
with open(cfg) as f:
    d = json.load(f)
if d.get('FlareSolverrUrl'):
    sys.exit(1)
d['FlareSolverrUrl'] = 'http://flaresolverr:8191'
with open(cfg, 'w') as f:
    json.dump(d, f, indent=2)
PYEOF
    then
        echo "🛡  Configured FlareSolverr in Jackett"
        docker compose restart jackett
    fi
fi

echo ""
echo "✓ Update complete"
