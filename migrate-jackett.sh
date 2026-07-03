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

# Translations are kept inline so this one-time script has no dependency on
# lang/*.sh and can be deleted from the repo in a single step.
case "$LANG_CHOICE" in
    2)
        MSG_JACKETT_TITLE="=== Миграция: добавление Jackett ==="
        MSG_JACKETT_NO_ENV="Ошибка: .env или docker-compose.yml не найден. Для новой установки используй install.sh."
        MSG_JACKETT_ALREADY_DONE="✅ Jackett уже есть в docker-compose.yml. Ничего делать не нужно."
        MSG_JACKETT_UPDATING="⬇  Загружаю актуальный docker-compose.yml..."
        MSG_JACKETT_STARTING="▶  Запускаю контейнеры (Jackett будет добавлен)..."
        MSG_JACKETT_DONE_TITLE="✅ Готово! Jackett запущен."
        MSG_JACKETT_DONE_NEXT="Следующие шаги:"
        MSG_JACKETT_DONE_1="  1. Открой веб-интерфейс Jackett и добавь индексаторы:"
        MSG_JACKETT_DONE_2="  2. Скопируй API Key с верхней части страницы Jackett."
        MSG_JACKETT_DONE_3="  3. В Telegram-боте: /settings → Jackett → Указать API key"
        MSG_JACKETT_DONE_UPDATE="     (Если бот ещё не обновился: /settings → Обновление, или выполни:"
        MSG_JACKETT_DONE_UPDATE2="      docker compose pull telegram-bot && docker compose up -d telegram-bot)"
        MSG_JACKETT_DONE_PASS="  ⚠️  Пароль Jackett не задан — панель пока публична. Установи его в боте: /settings → Jackett."
        ;;
    *)
        MSG_JACKETT_TITLE="=== Jackett Migration ==="
        MSG_JACKETT_NO_ENV="Error: .env or docker-compose.yml not found. Use install.sh for a fresh install."
        MSG_JACKETT_ALREADY_DONE="✅ Jackett is already present in docker-compose.yml. Nothing to do."
        MSG_JACKETT_UPDATING="⬇  Downloading latest docker-compose.yml..."
        MSG_JACKETT_STARTING="▶  Starting containers (Jackett will be added)..."
        MSG_JACKETT_DONE_TITLE="✅ Done! Jackett is running."
        MSG_JACKETT_DONE_NEXT="Next steps:"
        MSG_JACKETT_DONE_1="  1. Open the Jackett web UI and add your indexers:"
        MSG_JACKETT_DONE_2="  2. Copy the API Key from the top of the Jackett page."
        MSG_JACKETT_DONE_3="  3. In the Telegram bot: /settings → Jackett → Set API key"
        MSG_JACKETT_DONE_UPDATE="     (If the bot hasn't updated yet: /settings → Update, or run:"
        MSG_JACKETT_DONE_UPDATE2="      docker compose pull telegram-bot && docker compose up -d telegram-bot)"
        MSG_JACKETT_DONE_PASS="  ⚠️  No Jackett password yet — the panel is public. Set it in the bot: /settings → Jackett."
        ;;
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

# Pull new image and start all services
echo "$MSG_JACKETT_STARTING"
docker compose pull
docker compose up -d

# The Jackett admin password is set from the bot (/settings → Jackett), not here —
# the bot writes it into the mounted config and restarts the container itself.

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
echo "$MSG_JACKETT_DONE_PASS"
echo ""
