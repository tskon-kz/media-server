#!/bin/sh
# Ephemeral stack updater. The bot launches this inside a `docker:cli` container
# that is NOT part of the compose project, so it survives `docker compose up -d`
# recreating the bot. Mirrors update.sh but runs container-side.
#
# Inputs (env, set by the bot):
#   BOT_IMAGE_TAG         target bot image tag (stable | edge | vX.Y.Z)
#   COMPOSE_PROJECT_NAME  original compose project name (host project-dir basename)
#   REPO_SLUG             owner/repo used to fetch the latest compose + lang files
# Working dir is the mounted host project directory (/project).
set -e

REPO="${REPO_SLUG:-tskon-kz/media-server}"
RAW="https://raw.githubusercontent.com/$REPO/main"

echo "[updater] project=${COMPOSE_PROJECT_NAME:-?} tag=${BOT_IMAGE_TAG:-?}"

# docker:cli usually ships the compose plugin; install it if not.
if ! docker compose version >/dev/null 2>&1; then
    echo "[updater] installing docker-cli-compose"
    apk add --no-cache docker-cli-compose >/dev/null 2>&1 || {
        echo "[updater] ERROR: docker compose unavailable and install failed" >&2
        exit 1
    }
fi

fetch() {  # fetch <url> <out> — download to a temp file, then swap in atomically
    wget -q -T 30 -O "$2.tmp" "$1" && mv "$2.tmp" "$2"
}

echo "[updater] downloading latest compose + scripts + lang"
fetch "$RAW/docker-compose.yml" docker-compose.yml
fetch "$RAW/update.sh"          update.sh  && chmod +x update.sh  || true
fetch "$RAW/install.sh"         install.sh && chmod +x install.sh || true
mkdir -p lang
fetch "$RAW/lang/en.sh" lang/en.sh || true
fetch "$RAW/lang/ru.sh" lang/ru.sh || true

# Pin the bot image tag in .env so cold starts and this up -d agree.
touch .env
if grep -q '^BOT_IMAGE_TAG=' .env 2>/dev/null; then
    sed -i "s|^BOT_IMAGE_TAG=.*|BOT_IMAGE_TAG=$BOT_IMAGE_TAG|" .env
else
    echo "BOT_IMAGE_TAG=$BOT_IMAGE_TAG" >> .env
fi

# Pull ONLY the bot image. jellyfin/qbittorrent/jackett/cloudflared are pinned to
# :latest, so a blanket `docker compose pull` would silently upgrade and recreate
# them on every bot update — breaking a working stack (e.g. a new jellyfin:latest
# migrating its DB, or qBittorrent resetting its WebUI auth). `up -d` below still
# creates new sidecars and applies our own compose changes without touching them.
echo "[updater] pulling bot image"
n=1
until docker compose pull telegram-bot; do
    if [ "$n" -ge 3 ]; then
        echo "[updater] ERROR: pull failed after 3 attempts" >&2
        exit 1
    fi
    n=$((n + 1))
    sleep $((n * 3))
done

echo "[updater] applying stack"
docker compose up -d --remove-orphans

echo "[updater] done"
