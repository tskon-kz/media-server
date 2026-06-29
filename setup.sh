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
printf "%s" "$MSG_ASK_JF_USER";   read -r JF_USER
printf "%s" "$MSG_ASK_JF_PASS";   read -r JF_PASS
printf "%s" "$MSG_ASK_JF_NAME";   read -r JF_NAME
printf "%s" "$MSG_ASK_PROXY";     read -r PROXY_URL

{
    echo "BOT_TOKEN=$BOT_TOKEN"
    echo "ALLOWED_USER=$ALLOWED_USER"
    echo "SERVER_IP=$SERVER_IP"
    [ -n "$PROXY_URL" ] && echo "PROXY_URL=$PROXY_URL"
} > "$SCRIPT_DIR/.env"

echo "$MSG_ENV_SAVED"

# Dirs & start
cd "$SCRIPT_DIR"
mkdir -p media/movies media/series data/jellyfin/config data/jellyfin/cache data/qbittorrent/config

echo ""
echo "$MSG_STARTING"
docker compose pull
docker compose up -d

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

if ! grep -q "JELLYFIN_API_KEY" "$SCRIPT_DIR/.env" 2>/dev/null; then
    echo "$MSG_JF_WAIT"
    for i in $(seq 1 30); do
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8096/System/Info/Public" 2>/dev/null || echo "000")
        [ "$STATUS" = "200" ] && break
        sleep 3
    done

    JF_AUTH_HEADER='X-Emby-Authorization: MediaBrowser Client="Setup", Device="Setup", DeviceId="setup-001", Version="1.0.0"'

    _jf_auth() {
        curl -s -X POST "http://localhost:8096/Users/AuthenticateByName" \
            -H "Content-Type: application/json" \
            -H "$JF_AUTH_HEADER" \
            -d "{\"Username\":\"$1\",\"Pw\":\"$2\"}" \
            | tr -d ' \t' | grep -o '"AccessToken":"[^"]*"' | cut -d'"' -f4 || true
    }

    JF_TOKEN=$(_jf_auth "$JF_USER" "$JF_PASS")

    if [ -z "$JF_TOKEN" ]; then
        curl -s "http://localhost:8096/Startup/User" > /dev/null
        curl -s -X POST "http://localhost:8096/Startup/Configuration" \
            -H "Content-Type: application/json" \
            -d "{\"ServerName\":\"${JF_NAME:-Media Server}\",\"UICulture\":\"en-US\",\"MetadataCountryCode\":\"US\",\"PreferredMetadataLanguage\":\"en\"}" > /dev/null
        WZ=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:8096/Startup/User" \
            -H "Content-Type: application/json" \
            -d "{\"Name\":\"$JF_USER\",\"Password\":\"$JF_PASS\"}")
        curl -s -X POST "http://localhost:8096/Startup/Complete" > /dev/null

        for i in $(seq 1 30); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8096/System/Info/Public" 2>/dev/null || echo "000")
            [ "$STATUS" = "200" ] && break
            sleep 3
        done

        if [ "$WZ" = "404" ]; then
            echo "$MSG_JF_ALREADY_SET"
        else
            for i in $(seq 1 20); do
                JF_TOKEN=$(_jf_auth "$JF_USER" "$JF_PASS")
                [ -n "$JF_TOKEN" ] && break
                sleep 3
            done
        fi
    fi

    if [ -n "$JF_TOKEN" ]; then
        # Create a permanent API key (visible in Jellyfin Dashboard → API Keys)
        curl -s -X POST "http://localhost:8096/Auth/Keys?app=MediaServer" \
            -H "X-Emby-Token: $JF_TOKEN" > /dev/null

        JF_API_KEY=$(curl -s "http://localhost:8096/Auth/Keys" \
            -H "X-Emby-Token: $JF_TOKEN" \
            | tr -d ' \t' | grep -o '"AccessToken":"[^"]*"' | tail -1 | cut -d'"' -f4)

        FINAL_KEY="${JF_API_KEY:-$JF_TOKEN}"
        echo "JELLYFIN_API_KEY=$FINAL_KEY" >> "$SCRIPT_DIR/.env"

        curl -s -X POST \
            "http://localhost:8096/Library/VirtualFolders?name=Movies&collectionType=movies&refreshLibrary=false" \
            -H "X-Emby-Token: $FINAL_KEY" -H "Content-Type: application/json" \
            -d '{"LibraryOptions":{"PathInfos":[{"Path":"/media/movies"}]}}' > /dev/null

        curl -s -X POST \
            "http://localhost:8096/Library/VirtualFolders?name=Series&collectionType=tvshows&refreshLibrary=false" \
            -H "X-Emby-Token: $FINAL_KEY" -H "Content-Type: application/json" \
            -d '{"LibraryOptions":{"PathInfos":[{"Path":"/media/series"}]}}' > /dev/null

        docker compose restart telegram-bot
        echo "$MSG_JF_SETUP_OK"
    else
        echo "$MSG_JF_SETUP_FAIL"
    fi
fi

echo ""
echo "$MSG_DONE"
echo "Jellyfin:    http://$SERVER_IP:8096"
echo "qBittorrent: http://$SERVER_IP:8080"
