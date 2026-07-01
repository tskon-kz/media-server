#!/bin/bash
# bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/install.sh)
set -e

REPO="tskon-kz/media-server"
RAW="https://raw.githubusercontent.com/$REPO/main"
INSTALL_DIR="$HOME/media-server"
LOG_FILE="$INSTALL_DIR/install.log"
DB_FILE="$INSTALL_DIR/bot-data/media_server.db"

mkdir -p "$INSTALL_DIR"
exec 3>>"$LOG_FILE"
echo "=== Install started: $(date '+%Y-%m-%d %H:%M:%S') ===" >&3

# ---- helpers ----

_bar() {   # _bar n total  →  [████░░░░░░░░░░░░░░░░]
    local n=$1 total=$2 width=20 bar=''
    local filled=$(( n * width / total ))
    for ((j=0; j<width; j++)); do
        [ $j -lt $filled ] && bar+='█' || bar+='░'
    done
    printf '[%s]' "$bar"
}

_spin() {  # _spin "label" cmd [args...]
    local msg="$1"; shift
    local -a fr=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local i=0
    printf "  %s %s" "${fr[0]}" "$msg"
    "$@" >&3 2>&3 &
    local pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  %s %s" "${fr[i % ${#fr[@]}]}" "$msg"
        i=$((i+1))
        sleep 0.1
    done
    if wait "$pid"; then
        printf "\r  ✓ %s\n" "$msg"
    else
        printf "\r  ✗ %s  (log: %s)\n" "$msg" "$LOG_FILE"
        return 1
    fi
}

_pull_progress() {  # pulls images one by one, shows [████░░░] n/total
    local -a svcs=(jellyfin qbittorrent telegram-bot watchtower)
    local total=${#svcs[@]}
    for ((i=0; i<total; i++)); do
        local svc="${svcs[i]}"
        printf "\r  %s %d/%d  %s...\033[K" "$(_bar "$i" "$total")" "$i" "$total" "$svc"
        docker compose pull "$svc" >&3 2>&3
    done
    printf "\r  %s %d/%d  done\033[K\n" "$(_bar "$total" "$total")" "$total" "$total"
}

# Write a key=value pair to the bot's SQLite DB.
# Safe for arbitrary values: passed as sys.argv, not interpolated into Python source.
_db_set() {  # _db_set key value
    python3 - "$DB_FILE" "$1" "$2" >&3 2>&3 << 'PYEOF'
import sqlite3, os, sys
db_path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db = sqlite3.connect(db_path)
db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
if val:
    db.execute("INSERT OR REPLACE INTO config VALUES (?, ?)", (key, val))
db.commit()
PYEOF
}

# Exit 0 if key exists in DB with a non-empty value, exit 1 otherwise.
_db_has() {  # _db_has key
    python3 - "$DB_FILE" "$1" >&3 2>&3 << 'PYEOF'
import sqlite3, os, sys
db_path, key = sys.argv[1], sys.argv[2]
if not os.path.exists(db_path):
    sys.exit(1)
row = sqlite3.connect(db_path).execute(
    "SELECT value FROM config WHERE key=? AND value IS NOT NULL AND value != ''", (key,)
).fetchone()
sys.exit(0 if row else 1)
PYEOF
}

# ---- language ----

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

# ---- docker check ----

if ! command -v docker &>/dev/null; then
    _spin "$MSG_DOCKER_INSTALL" bash -c 'curl -fsSL https://get.docker.com | sh'
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

_spin "$MSG_DOWNLOADING" bash -c "
    curl -fsSL '$RAW/docker-compose.yml'  -o docker-compose.yml
    mkdir -p lang
    curl -fsSL '$RAW/lang/en.sh'          -o lang/en.sh
    curl -fsSL '$RAW/lang/ru.sh'          -o lang/ru.sh
    curl -fsSL '$RAW/teardown.sh'         -o teardown.sh     && chmod +x teardown.sh
    curl -fsSL '$RAW/migrate-media.sh'    -o migrate-media.sh && chmod +x migrate-media.sh
"

if [ -f "$INSTALL_DIR/.env" ]; then
    printf "%s" "$MSG_ENV_EXISTS"
    read -r OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
        echo "$MSG_SKIP_ENV"
        _pull_progress
        _spin "$MSG_STARTING" docker compose up -d
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
while true; do
    printf "%s" "$MSG_ASK_QB_PASS"; read -rs QB_PASS; echo
    [ -n "$QB_PASS" ] && break
    echo "$MSG_QB_PASS_EMPTY"
done
while true; do
    printf "%s" "$MSG_ASK_JF_USER"; read -r JF_USER
    [ -n "$JF_USER" ] && break
    echo "$MSG_JF_USER_EMPTY"
done
while true; do
    printf "%s" "$MSG_ASK_JF_PASS"; read -rs JF_PASS; echo
    [ -n "$JF_PASS" ] && break
    echo "$MSG_QB_PASS_EMPTY"
done
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

# .env — only what docker-compose needs for infrastructure (ports, volumes, auth bootstrap)
{
    echo "BOT_TOKEN=$BOT_TOKEN"
    echo "ALLOWED_USER=$ALLOWED_USER"
    echo "WATCHTOWER_TOKEN=$WATCHTOWER_TOKEN"
    [ "$JF_PORT" != "8096" ] && echo "JELLYFIN_PORT=$JF_PORT"
    [ "$QB_PORT" != "8080" ] && echo "QB_PORT=$QB_PORT"
    [ "$MEDIA_PATH" != "./media" ] && echo "MEDIA_PATH=$MEDIA_PATH"
} > "$INSTALL_DIR/.env"

# Bot config that changes at runtime lives in the DB, not in .env.
# qb_pass and jellyfin_api_key are written later after successful verification.
mkdir -p "$INSTALL_DIR/bot-data"
_db_set "server_ip" "$SERVER_IP"
_db_set "proxy_url" "$PROXY_URL"
_db_set "lang"      "$([ "$LANG_CHOICE" = "2" ] && echo "ru" || echo "en")"

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
_pull_progress
_spin "$MSG_STARTING" docker compose up -d qbittorrent jellyfin watchtower

# ---- qBittorrent password setup ----

if ! _db_has "qb_pass"; then
    TEMP_PASS=""
    printf "  %s" "$MSG_QB_WAIT"
    for i in $(seq 1 30); do
        # Strip quotes and \r — some qBittorrent versions log the password as 'abc123'
        TEMP_PASS=$(docker logs qbittorrent 2>&1 | grep "temporary password" | awk '{print $NF}' | tail -1 | tr -d "'\"\r\n")
        [ -n "$TEMP_PASS" ] && break
        printf "."
        sleep 2
    done
    [ -n "$TEMP_PASS" ] && printf " ✓\n" || printf " ⚠️\n"
    echo "QB temp pass extracted: '$TEMP_PASS'" >&3

    if [ -n "$TEMP_PASS" ]; then
        # Temp pass appears in logs before the WebUI is ready — wait for it.
        # Run inside container (always port 8080) to avoid Host header mismatch when QB_PORT
        # is customized. Write cookie to /config/ (bind-mounted volume, always writable).
        sleep 3
        QB_COOKIE=/config/.qb_setup.tmp
        LOGIN_RESP=""
        for attempt in 1 2 3; do
            LOGIN_RESP=$(docker exec -e _TP="$TEMP_PASS" qbittorrent sh -c '
                curl -s -c /config/.qb_setup.tmp \
                    -d "username=admin&password=$_TP" \
                    "http://localhost:8080/api/v2/auth/login"
            ' 2>&3) || true
            echo "QB login attempt $attempt: '$LOGIN_RESP'" >&3
            [ "$LOGIN_RESP" = "Ok." ] && break
            [ "$attempt" -lt 3 ] && sleep 5
        done
        if [ "$LOGIN_RESP" = "Ok." ]; then
            docker exec -e _NP="$QB_PASS" qbittorrent sh -c '
                curl -s -b /config/.qb_setup.tmp \
                    -d "json={\"web_ui_password\":\"$_NP\"}" \
                    "http://localhost:8080/api/v2/app/setPreferences" > /dev/null
                rm -f /config/.qb_setup.tmp
            ' 2>&3 || true
            QB_VERIFY=$(docker exec -e _VP="$QB_PASS" qbittorrent sh -c '
                curl -s -d "username=admin&password=$_VP" "http://localhost:8080/api/v2/auth/login"
            ' 2>&3 || echo "")
            echo "QB verify: '$QB_VERIFY'" >&3
            if [ "$QB_VERIFY" = "Ok." ]; then
                _db_set "qb_user" "admin"
                _db_set "qb_pass" "$QB_PASS"
                echo "$MSG_QB_PASS_SET"
            else
                docker exec qbittorrent rm -f /config/.qb_setup.tmp 2>/dev/null || true
                echo "$MSG_QB_PASS_FAIL"
            fi
        else
            docker exec qbittorrent rm -f /config/.qb_setup.tmp 2>/dev/null || true
            echo "$MSG_QB_PASS_FAIL"
        fi
    else
        echo "$MSG_QB_PASS_FAIL"
    fi
fi

# ---- Jellyfin setup ----

if ! _db_has "jellyfin_api_key"; then
    printf "  %s" "$MSG_JF_WAIT"
    for i in $(seq 1 30); do
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$JF_PORT/System/Info/Public" 2>/dev/null || echo "000")
        [ "$STATUS" = "200" ] && break
        printf "."
        sleep 3
    done
    printf "\n"

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
        for i in $(seq 1 20); do
            WIZ_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$JF_PORT/Startup/User" 2>/dev/null || echo "000")
            case "$WIZ_STATUS" in 200|404) break ;; esac
            sleep 3
        done

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

        [ "$WZ" = "404" ] && echo "$MSG_JF_ALREADY_SET"

        for i in $(seq 1 20); do
            JF_TOKEN=$(_jf_auth "$JF_USER" "$JF_PASS")
            [ -n "$JF_TOKEN" ] && break
            sleep 3
        done
    fi

    if [ -n "$JF_TOKEN" ]; then
        curl -s -X POST "http://localhost:$JF_PORT/Auth/Keys?app=MediaServer" \
            -H "X-Emby-Token: $JF_TOKEN" > /dev/null

        JF_API_KEY=$(curl -s "http://localhost:$JF_PORT/Auth/Keys" \
            -H "X-Emby-Token: $JF_TOKEN" \
            | tr -d ' \t' | grep -o '"AccessToken":"[^"]*"' | tail -1 | cut -d'"' -f4)

        FINAL_KEY="${JF_API_KEY:-$JF_TOKEN}"
        _db_set "jellyfin_api_key" "$FINAL_KEY"

        curl -s -X POST \
            "http://localhost:$JF_PORT/Library/VirtualFolders?name=Movies&collectionType=movies&refreshLibrary=false" \
            -H "X-Emby-Token: $FINAL_KEY" -H "Content-Type: application/json" \
            -d '{"LibraryOptions":{"PathInfos":[{"Path":"/media/movies"}]}}' > /dev/null

        curl -s -X POST \
            "http://localhost:$JF_PORT/Library/VirtualFolders?name=Series&collectionType=tvshows&refreshLibrary=false" \
            -H "X-Emby-Token: $FINAL_KEY" -H "Content-Type: application/json" \
            -d '{"LibraryOptions":{"PathInfos":[{"Path":"/media/series"}]}}' > /dev/null

        echo "$MSG_JF_SETUP_OK"
    else
        echo "$MSG_JF_SETUP_FAIL"
    fi
fi

_spin "$MSG_STARTING" docker compose up -d telegram-bot

echo ""
echo "$MSG_DONE"
echo "Jellyfin:    http://$SERVER_IP:$JF_PORT"
echo "qBittorrent: http://$SERVER_IP:$QB_PORT"
echo ""
echo "=== Install finished: $(date '+%Y-%m-%d %H:%M:%S') ===" >&3
echo "Log: $LOG_FILE"
