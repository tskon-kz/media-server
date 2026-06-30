#!/bin/bash
# bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/install.sh)
set -e

REPO="tskon-kz/media-server"
RAW="https://raw.githubusercontent.com/$REPO/main"
INSTALL_DIR="$HOME/media-server"

echo "1) English"
echo "2) Русский"
printf "Select language / Выберите язык [1/2]: "
read -r LANG_CHOICE

TMP_LANG=$(mktemp -d)
trap 'rm -rf "$TMP_LANG"' EXIT

curl -fsSL "$RAW/lang/en.sh" -o "$TMP_LANG/en.sh"
curl -fsSL "$RAW/lang/ru.sh" -o "$TMP_LANG/ru.sh"

case "$LANG_CHOICE" in
    2) source "$TMP_LANG/ru.sh" ;;
    *) source "$TMP_LANG/en.sh" ;;
esac

echo ""
echo "$MSG_TITLE"
echo ""

if ! command -v docker &>/dev/null; then
    echo "$MSG_DOCKER_INSTALL"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "$MSG_DOCKER_DONE"
    exit 0
fi

if ! docker info &>/dev/null 2>&1; then
    sudo usermod -aG docker "$USER"
    echo "$MSG_DOCKER_GROUP"
    exit 1
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "$MSG_DOWNLOADING"
curl -fsSL "$RAW/docker-compose.yml" -o docker-compose.yml
mkdir -p lang
curl -fsSL "$RAW/lang/en.sh" -o lang/en.sh
curl -fsSL "$RAW/lang/ru.sh" -o lang/ru.sh
curl -fsSL "$RAW/teardown.sh"     -o teardown.sh     && chmod +x teardown.sh
curl -fsSL "$RAW/migrate-media.sh" -o migrate-media.sh && chmod +x migrate-media.sh

if [ -f "$INSTALL_DIR/.env" ]; then
    printf "%s" "$MSG_ENV_EXISTS"
    read -r OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
        echo "$MSG_SKIP_ENV"
        docker compose pull
        docker compose up -d
        exit 0
    fi
fi

echo "$MSG_ENTER_VALUES"
echo ""

printf "%s" "$MSG_ASK_TOKEN";      read -r BOT_TOKEN
printf "%s" "$MSG_ASK_USER_ID";    read -r ALLOWED_USER
printf "%s" "$MSG_ASK_SERVER_IP";  read -r SERVER_IP
printf "%s" "$MSG_ASK_MEDIA_PATH"; read -r MEDIA_PATH_INPUT
MEDIA_PATH="${MEDIA_PATH_INPUT:-./media}"
printf "%s" "$MSG_ASK_QB_PASS";   read -r QB_PASS
printf "%s" "$MSG_ASK_JF_USER";   read -r JF_USER
printf "%s" "$MSG_ASK_JF_PASS";   read -r JF_PASS
printf "%s" "$MSG_ASK_JF_NAME";   read -r JF_NAME
printf "%s" "$MSG_ASK_PROXY";     read -r PROXY_URL

JF_PORT=8096
QB_PORT=8080
printf "%s" "$MSG_ASK_PORTS"; read -r CUSTOM_PORTS
if [[ "$CUSTOM_PORTS" =~ ^[Yy]$ ]]; then
    printf "%s" "$MSG_ASK_JF_PORT"; read -r _JF_PORT
    printf "%s" "$MSG_ASK_QB_PORT"; read -r _QB_PORT
    [ -n "$_JF_PORT" ] && JF_PORT="$_JF_PORT"
    [ -n "$_QB_PORT" ] && QB_PORT="$_QB_PORT"
else
    echo "$MSG_PORTS_DEFAULT"
fi

WATCHTOWER_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null \
    || openssl rand -hex 16 2>/dev/null \
    || cat /proc/sys/kernel/random/uuid 2>/dev/null | tr -d '-' | head -c 32)

{
    echo "BOT_TOKEN=$BOT_TOKEN"
    echo "ALLOWED_USER=$ALLOWED_USER"
    echo "SERVER_IP=$SERVER_IP"
    echo "WATCHTOWER_TOKEN=$WATCHTOWER_TOKEN"
    [ -n "$PROXY_URL" ] && echo "PROXY_URL=$PROXY_URL"
    [ "$JF_PORT" != "8096" ] && echo "JELLYFIN_PORT=$JF_PORT"
    [ "$QB_PORT" != "8080" ] && echo "QB_PORT=$QB_PORT"
    [ "$MEDIA_PATH" != "./media" ] && echo "MEDIA_PATH=$MEDIA_PATH"
} > "$INSTALL_DIR/.env"

echo "$MSG_ENV_SAVED"

if [[ "$MEDIA_PATH" == /* ]]; then
    _media_abs="$MEDIA_PATH"
else
    _media_abs="$INSTALL_DIR/${MEDIA_PATH#./}"
fi
mkdir -p "$_media_abs/movies" "$_media_abs/series" \
    "$INSTALL_DIR/data/jellyfin/config" "$INSTALL_DIR/data/jellyfin/cache" \
    "$INSTALL_DIR/data/qbittorrent/config" \
    "$INSTALL_DIR/bot-data"
sudo chown -R "$USER:$USER" "$INSTALL_DIR" 2>/dev/null || true

echo ""
echo "$MSG_STARTING"
docker compose pull
docker compose up -d

if [ ! -f "$INSTALL_DIR/bot-data/creds.json" ]; then
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
            "http://localhost:$QB_PORT/api/v2/auth/login" > /dev/null
        curl -s -b /tmp/qb_sid.txt \
            -d "json={\"web_ui_password\":\"$QB_PASS\"}" \
            "http://localhost:$QB_PORT/api/v2/app/setPreferences" > /dev/null
        rm -f /tmp/qb_sid.txt
        echo "{\"qb_user\":\"admin\",\"qb_pass\":\"$QB_PASS\"}" > "$INSTALL_DIR/bot-data/creds.json"
        echo "$MSG_QB_PASS_SET"
    else
        echo "$MSG_QB_PASS_FAIL"
    fi
fi

if ! grep -q "JELLYFIN_API_KEY" "$INSTALL_DIR/.env" 2>/dev/null; then
    echo "$MSG_JF_WAIT"
    for i in $(seq 1 30); do
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$JF_PORT/System/Info/Public" 2>/dev/null || echo "000")
        [ "$STATUS" = "200" ] && break
        sleep 3
    done

    JF_AUTH_HEADER='X-Emby-Authorization: MediaBrowser Client="Setup", Device="Setup", DeviceId="setup-001", Version="1.0.0"'

    _jf_auth() {
        curl -s -X POST "http://localhost:$JF_PORT/Users/AuthenticateByName" \
            -H "Content-Type: application/json" \
            -H "$JF_AUTH_HEADER" \
            -d "{\"Username\":\"$1\",\"Pw\":\"$2\"}" \
            | tr -d ' \t' | grep -o '"AccessToken":"[^"]*"' | cut -d'"' -f4 || true
    }

    JF_TOKEN=$(_jf_auth "$JF_USER" "$JF_PASS")

    if [ -z "$JF_TOKEN" ]; then
        curl -s "http://localhost:$JF_PORT/Startup/User" > /dev/null
        curl -s -X POST "http://localhost:$JF_PORT/Startup/Configuration" \
            -H "Content-Type: application/json" \
            -d "{\"ServerName\":\"${JF_NAME:-Media Server}\",\"UICulture\":\"en-US\",\"MetadataCountryCode\":\"US\",\"PreferredMetadataLanguage\":\"en\"}" > /dev/null
        WZ=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:$JF_PORT/Startup/User" \
            -H "Content-Type: application/json" \
            -d "{\"Name\":\"$JF_USER\",\"Password\":\"$JF_PASS\"}")
        curl -s -X POST "http://localhost:$JF_PORT/Startup/Complete" > /dev/null

        for i in $(seq 1 30); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$JF_PORT/System/Info/Public" 2>/dev/null || echo "000")
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
        curl -s -X POST "http://localhost:$JF_PORT/Auth/Keys?app=MediaServer" \
            -H "X-Emby-Token: $JF_TOKEN" > /dev/null

        JF_API_KEY=$(curl -s "http://localhost:$JF_PORT/Auth/Keys" \
            -H "X-Emby-Token: $JF_TOKEN" \
            | tr -d ' \t' | grep -o '"AccessToken":"[^"]*"' | tail -1 | cut -d'"' -f4)

        FINAL_KEY="${JF_API_KEY:-$JF_TOKEN}"
        echo "JELLYFIN_API_KEY=$FINAL_KEY" >> "$INSTALL_DIR/.env"

        curl -s -X POST \
            "http://localhost:$JF_PORT/Library/VirtualFolders?name=Movies&collectionType=movies&refreshLibrary=false" \
            -H "X-Emby-Token: $FINAL_KEY" -H "Content-Type: application/json" \
            -d '{"LibraryOptions":{"PathInfos":[{"Path":"/media/movies"}]}}' > /dev/null

        curl -s -X POST \
            "http://localhost:$JF_PORT/Library/VirtualFolders?name=Series&collectionType=tvshows&refreshLibrary=false" \
            -H "X-Emby-Token: $FINAL_KEY" -H "Content-Type: application/json" \
            -d '{"LibraryOptions":{"PathInfos":[{"Path":"/media/series"}]}}' > /dev/null

        docker compose up -d telegram-bot
        echo "$MSG_JF_SETUP_OK"
    else
        echo "$MSG_JF_SETUP_FAIL"
    fi
fi

echo ""
echo "$MSG_DONE"
echo "Jellyfin:    http://$SERVER_IP:$JF_PORT"
echo "qBittorrent: http://$SERVER_IP:$QB_PORT"
