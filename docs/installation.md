# Installation

## Quick install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/install.sh)
```

The script:
1. Asks for the interface language (English / Russian)
2. Installs Docker if it's not present
3. Downloads project files to `~/media-server/`
4. Prompts for credentials and configuration
5. Configures qBittorrent and Jellyfin automatically
6. Starts all containers

### What the installer asks for

| Prompt | Description |
|--------|-------------|
| Language | English or Russian |
| Telegram Bot Token | From [@BotFather](https://t.me/BotFather) |
| Your Telegram ID | From [@userinfobot](https://t.me/userinfobot). Comma-separated for multiple users |
| Server IP | External IP used for web UI links in the bot |
| Media path | Host path mounted as `/media` (default: `./media`). Use a mounted disk path, e.g. `/mnt/disk2` |
| Jellyfin admin username / password | Created on first run |
| Jellyfin server name | Optional, defaults to `Media Server` |
| Jackett admin password | Optional — protects the Jackett web UI; leave empty for no password |
| Telegram proxy | Optional, e.g. `socks5://user:pass@host:port` |
| Named Cloudflare tunnel | Optional — see [Mini App URL](#mini-app-url--cloudflare-tunnel) below |
| Custom ports | Optional — press `n` to use defaults (Jellyfin: 8096, qBittorrent: 8080, Jackett: 9117) |

After the installer completes, the bot is live in your Telegram chat.

---

## Mini App URL — Cloudflare Tunnel

The Mini App (web UI in Telegram) is served over HTTPS via a Cloudflare Tunnel. Two modes are supported:

### Quick tunnel (default, no account required)

The installer starts a `cloudflared` container that opens an ephemeral `*.trycloudflare.com` HTTPS URL. The bot detects it automatically and sets the Menu Button in Telegram. No configuration needed — just press `n` at the named tunnel prompt.

**Limitation:** the URL changes every time the `cloudflared` container restarts. The bot updates the Menu Button automatically within ~60 s, so there is no manual action required — but the URL is not static, so the bot cannot be registered in BotFather with a fixed Mini App URL (no OPEN button in the Telegram chat list).

### Named tunnel (static URL, requires Cloudflare account)

A named tunnel gives the Mini App a permanent `https://app.yourdomain.com` address. This enables the **OPEN** button in the Telegram chat list and allows registering the bot in BotFather with a fixed URL.

#### Before running the installer

1. Log in to [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → **Networks → Tunnels → Create a tunnel**
2. Name the tunnel (e.g. `media-server`) → copy the **tunnel token**
3. Under **Public Hostnames**, add:
   - **Subdomain / Domain:** `app.yourdomain.com` (any subdomain on your CF-managed domain)
   - **Service:** `http://telegram-bot:8081`

#### During the installer

When asked `Named Cloudflare tunnel? [y/n]` — press `y`, then enter:
- The tunnel token
- Your static URL (e.g. `https://app.yourdomain.com`)

The installer writes both to `.env` and the bot uses the static URL from the first start.

#### Switching from quick tunnel to named tunnel after install

Edit `.env` on the server and add:

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=eyJ...your-token...
WEBAPP_URL=https://app.yourdomain.com
```

Then restart:

```bash
docker compose up -d cloudflared telegram-bot
```

The bot picks up `WEBAPP_URL` on next start and updates the Menu Button immediately.

---

## Manual setup

If you prefer not to use the installer:

### 1. Clone and configure `.env`

```bash
git clone https://github.com/tskon-kz/media-server ~/media-server
cd ~/media-server
cp /dev/null .env
```

Add to `.env`:

```dotenv
BOT_TOKEN=...           # from @BotFather
ALLOWED_USER=123456789  # from @userinfobot; comma-separated for multiple users
WATCHTOWER_TOKEN=...    # any random string, e.g.: openssl rand -hex 16

# Optional — uncomment to override defaults
# JELLYFIN_PORT=8096
# QB_PORT=8080
# MEDIA_PATH=./media
```

### 2. Seed the database

```bash
DB=bot-data/media_server.db
mkdir -p bot-data
python3 -c "
import sqlite3
db = sqlite3.connect('$DB')
db.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
db.executemany('INSERT OR REPLACE INTO config VALUES (?,?)', [
    ('server_ip', 'YOUR_SERVER_IP'),
    ('lang',      'en'),
    ('proxy_url', ''),
])
db.commit()
"
```

### 3. Start containers

```bash
docker compose up -d
```

### 4. Configure services

Open the web UIs and complete initial setup:
- qBittorrent: `http://SERVER_IP:8080` — note the auto-generated password from container logs
- Jellyfin: `http://SERVER_IP:8096` — complete the setup wizard

Then store credentials in the database:

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('$DB')
db.executemany('INSERT OR REPLACE INTO config VALUES (?,?)', [
    ('qb_user',          'admin'),
    ('qb_pass',          'YOUR_QB_WEBUI_PASSWORD'),
    ('jellyfin_api_key', 'YOUR_JELLYFIN_API_KEY'),
])
db.commit()
"
```

Jellyfin API key: Dashboard → API Keys → +.

---

## Accessing the stack

| Service | URL |
|---------|-----|
| Jellyfin | `http://SERVER_IP:8096` |
| qBittorrent | `http://SERVER_IP:8080` |
| Jackett | `http://SERVER_IP:9117` |
| Telegram bot | Find by username in Telegram |

Normal usage goes entirely through the Telegram bot — web UIs are only needed for advanced configuration.

---

## Setting up Jackett (torrent search)

Jackett starts automatically with the stack. After installation:

1. Open `http://SERVER_IP:9117` and add your indexers (trackers) via the Jackett web UI.
2. Use `/search <query>` in the bot to search all configured indexers.

The Jackett API key is read automatically from the mounted config file — no manual copy/paste needed.

> **Security:** The Jackett web UI is publicly accessible on the configured port. The installer prompts you to set an admin password during setup. You can also change or remove it later via `/settings` → Jackett → 🔒 Change admin password.
