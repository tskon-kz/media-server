#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

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

printf "%s" "$MSG_TEARDOWN_IMAGES_CONFIRM"
read -r REMOVE_IMAGES
if [[ "$REMOVE_IMAGES" =~ ^[Yy]$ ]]; then
    echo "$MSG_TEARDOWN_STOPPING"
    docker compose down --volumes --rmi all 2>/dev/null || true
else
    echo "$MSG_TEARDOWN_STOPPING"
    docker compose down --volumes 2>/dev/null || true
fi

echo "$MSG_TEARDOWN_REMOVING"
sudo rm -rf data bot-data .env

printf "%s" "$MSG_TEARDOWN_MEDIA_CONFIRM"
read -r REMOVE_MEDIA
if [[ "$REMOVE_MEDIA" =~ ^[Yy]$ ]]; then
    sudo rm -rf media
    echo "$MSG_TEARDOWN_MEDIA_REMOVED"
else
    echo "$MSG_TEARDOWN_MEDIA_KEPT"
fi

echo "$MSG_TEARDOWN_DONE"
