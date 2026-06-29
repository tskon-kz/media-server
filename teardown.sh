#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "1) English"
echo "2) Русский"
printf "Select language / Выберите язык [1/2]: "
read -r LANG_CHOICE
case "$LANG_CHOICE" in
    2) source "$SCRIPT_DIR/lang/ru.sh" ;;
    *) source "$SCRIPT_DIR/lang/en.sh" ;;
esac

echo ""
printf "%s" "$MSG_TEARDOWN_CONFIRM"
read -r CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo "$MSG_TEARDOWN_ABORT"; exit 0; }

echo "$MSG_TEARDOWN_STOPPING"
docker compose down --volumes --rmi all 2>/dev/null || true

echo "$MSG_TEARDOWN_REMOVING"
sudo rm -rf media data bot/creds.json bot/lang.json .env

echo "$MSG_TEARDOWN_DONE"
