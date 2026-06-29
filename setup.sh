#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Language selection — hardcoded before sourcing
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
echo "$MSG_TITLE"
echo ""

# Docker check
if ! command -v docker &>/dev/null; then
    echo "$MSG_DOCKER_INSTALL"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "$MSG_DOCKER_DONE"
    exit 0
fi

# .env setup
if [ -f "$SCRIPT_DIR/.env" ]; then
    printf "%s" "$MSG_ENV_EXISTS"
    read -r OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
        echo "$MSG_SKIP_ENV"
        docker compose up -d
        exit 0
    fi
fi

echo "$MSG_ENTER_VALUES"
echo ""

printf "%s" "$MSG_ASK_TOKEN";     read -r BOT_TOKEN
printf "%s" "$MSG_ASK_USER_ID";   read -r ALLOWED_USER
printf "%s" "$MSG_ASK_SERVER_IP"; read -r SERVER_IP
printf "%s" "$MSG_ASK_QB_PASS";   read -r QB_PASS
printf "%s" "$MSG_ASK_PROXY";     read -r PROXY_URL

{
    echo "BOT_TOKEN=$BOT_TOKEN"
    echo "ALLOWED_USER=$ALLOWED_USER"
    echo "SERVER_IP=$SERVER_IP"
    [ -n "$PROXY_URL" ] && echo "PROXY_URL=$PROXY_URL"
} > "$SCRIPT_DIR/.env"

echo "$MSG_ENV_SAVED"

# Dirs & start
mkdir -p media data/jellyfin/config data/jellyfin/cache data/qbittorrent/config

echo ""
echo "$MSG_STARTING"
docker compose pull
docker compose up -d

# Auto-configure qBittorrent password
if [ ! -f "$SCRIPT_DIR/bot/creds.json" ]; then
    echo "$MSG_QB_WAIT"
    TEMP_PASS=""
    for i in $(seq 1 30); do
        TEMP_PASS=$(docker logs qbittorrent 2>&1 | grep "temporary password" | awk '{print $NF}' | tail -1)
        [ -n "$TEMP_PASS" ] && break
        sleep 2
    done

    if [ -n "$TEMP_PASS" ]; then
        curl -s -c /tmp/qb_sid.txt \
            -d "username=admin&password=$TEMP_PASS" \
            "http://localhost:8080/api/v2/auth/login" > /dev/null

        curl -s -b /tmp/qb_sid.txt \
            -d "json={\"web_ui_password\":\"$QB_PASS\"}" \
            "http://localhost:8080/api/v2/app/setPreferences" > /dev/null

        rm -f /tmp/qb_sid.txt

        echo "{\"qb_user\":\"admin\",\"qb_pass\":\"$QB_PASS\"}" > "$SCRIPT_DIR/bot/creds.json"
        echo "$MSG_QB_PASS_SET"
    else
        echo "$MSG_QB_PASS_FAIL"
    fi
fi

echo ""
echo "$MSG_DONE"
echo "Jellyfin:    http://$SERVER_IP:8096"
echo "qBittorrent: http://$SERVER_IP:8080"
