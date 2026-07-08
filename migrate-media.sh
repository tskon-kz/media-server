#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "1) English"
echo "2) Русский"
printf "Select language / Выберите язык [1/2]: "
read -r LANG_CHOICE
case "$LANG_CHOICE" in
    2) source "$SCRIPT_DIR/lang/ru.sh" ;;
    *) source "$SCRIPT_DIR/lang/en.sh" ;;
esac

echo ""
echo "$MSG_MIGRATE_TITLE"
echo ""

# Resolve current media path from .env
CURRENT_RAW=$(grep "^MEDIA_PATH=" "$SCRIPT_DIR/.env" 2>/dev/null | cut -d'=' -f2- || true)
CURRENT_RAW="${CURRENT_RAW:-./media}"

_resolve() {
    local p="$1"
    if [[ "$p" == /* ]]; then echo "$p"
    else echo "$SCRIPT_DIR/${p#./}"
    fi
}

old_abs=$(_resolve "$CURRENT_RAW")

echo "$MSG_MIGRATE_CURRENT: $old_abs"
echo ""
printf "%s" "$MSG_MIGRATE_ASK_NEW"; read -r NEW_RAW

[ -z "$NEW_RAW" ] && { echo "$MSG_TEARDOWN_ABORT"; exit 0; }

new_abs=$(_resolve "$NEW_RAW")

[ "$old_abs" = "$new_abs" ] && { echo "$MSG_MIGRATE_SAME"; exit 0; }

if [ ! -d "$old_abs" ]; then
    echo "$MSG_MIGRATE_NO_SOURCE: $old_abs"
    exit 1
fi

if ! command -v rsync &>/dev/null; then
    echo "$MSG_MIGRATE_NO_RSYNC"
    exit 1
fi

mkdir -p "$new_abs"

src_bytes=$(du -sb "$old_abs" 2>/dev/null | awk '{print $1}')
src_gb=$(awk "BEGIN {printf \"%.2f GB\", $src_bytes/1024/1024/1024}")
avail_bytes=$(df -B1 "$new_abs" 2>/dev/null | awk 'NR==2{print $4}')
avail_gb=$(awk "BEGIN {printf \"%.2f GB\", $avail_bytes/1024/1024/1024}")

echo "$MSG_MIGRATE_PLAN"
echo "$MSG_MIGRATE_FROM: $old_abs"
echo "$MSG_MIGRATE_TO:   $new_abs"
echo "$MSG_MIGRATE_SIZE: $src_gb"
echo "$MSG_MIGRATE_AVAIL: $avail_gb"
echo ""

if [ "$avail_bytes" -lt "$src_bytes" ]; then
    echo "$MSG_MIGRATE_NO_SPACE"
    exit 1
fi

printf "%s" "$MSG_MIGRATE_CONFIRM"; read -r CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo "$MSG_TEARDOWN_ABORT"; exit 0; }

echo ""
echo "$MSG_MIGRATE_STOPPING"
cd "$SCRIPT_DIR"
docker compose stop || true

echo "$MSG_MIGRATE_COPYING"
if rsync -aH --info=progress2 "$old_abs/" "$new_abs/"; then
    echo ""
    echo "$MSG_MIGRATE_COPY_OK"

    # Update .env
    if grep -q "^MEDIA_PATH=" "$SCRIPT_DIR/.env" 2>/dev/null; then
        sed -i "s|^MEDIA_PATH=.*|MEDIA_PATH=$new_abs|" "$SCRIPT_DIR/.env"
    else
        echo "MEDIA_PATH=$new_abs" >> "$SCRIPT_DIR/.env"
    fi

    docker compose up -d

    echo ""
    printf "%s" "$MSG_MIGRATE_REMOVE_OLD"; read -r REMOVE_OLD
    if [[ "$REMOVE_OLD" =~ ^[Yy]$ ]]; then
        rm -rf "$old_abs"
        echo "$MSG_MIGRATE_OLD_REMOVED"
    else
        echo "$MSG_MIGRATE_OLD_KEPT $old_abs"
    fi

    echo ""
    echo "$MSG_MIGRATE_DONE $new_abs"
else
    echo ""
    echo "$MSG_MIGRATE_COPY_FAIL"
    docker compose up -d
    exit 1
fi
