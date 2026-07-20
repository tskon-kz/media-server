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
| Mini App exposure | Quick Cloudflare tunnel (default) or your own domain — see [Mini App URL](#mini-app-url--exposure) below |
| Custom ports | Optional — press `n` to use defaults (Jellyfin: 8096, qBittorrent: 8080, Jackett: 9117) |

After the installer completes, the bot is live in your Telegram chat.

---

## Mini App URL — exposure

The Mini App (web UI in Telegram) is served over HTTPS. Two modes are supported.

### Quick tunnel (default, no account required)

The installer starts a `cloudflared` container that opens an ephemeral `*.trycloudflare.com` HTTPS URL. The bot detects it automatically and sets the Menu Button in Telegram. No configuration needed — just pick option `1` at the exposure prompt.

> **Firewall / outbound ports:** `cloudflared` connects outbound — no inbound ports need to be opened. It uses **UDP 7844** (QUIC/HTTP3) for best performance and falls back to **TCP 443** if UDP is blocked. Allow outbound UDP 7844 for QUIC; TCP 443 alone is sufficient if QUIC is unavailable.

**Limitation:** the URL changes every time the `cloudflared` container restarts. The bot updates the Menu Button automatically within ~60 s, so no manual action is required — but the URL is not static, so the bot cannot be registered in BotFather with a fixed Mini App URL (no OPEN button in the Telegram chat list).

### Own domain, no Cloudflare (static URL)

Serve the Mini App from your own domain (e.g. `https://media.yourdomain.com`). A bundled **Caddy** container terminates TLS with an auto-issued Let's Encrypt certificate and proxies to the bot — no Cloudflare account. This gives a permanent URL (enables the **OPEN** button in the chat list and a fixed BotFather URL).

**Requirements:** a DNS **A record** for the domain pointing at this server.

> **Firewall / inbound ports:** Caddy needs **TCP 80** and **TCP 443** reachable from the internet — port 80 for the Let's Encrypt ACME HTTP challenge (certificate issuance/renewal), port 443 for the Mini App over HTTPS. Open both inbound on the server's firewall and forward them if the server is behind NAT. (Unlike the quick tunnel, which is outbound-only, own-domain mode terminates TLS locally and must accept inbound connections.)

#### During the installer

At the exposure prompt pick option `2` and enter your domain (e.g. `media.yourdomain.com`). The installer writes `WEBAPP_DOMAIN` to `.env`; Caddy issues the certificate on first start.

#### Switching from quick tunnel to own domain after install

Point the domain's DNS A record at the server, then edit `.env` and add:

```dotenv
WEBAPP_DOMAIN=media.yourdomain.com
```

Then re-run the updater (brings the stack down and back up with Caddy instead of the tunnel):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/update.sh)
```

`WEBAPP_DOMAIN` alone switches the Cloudflare tunnel off and sets the bot's Mini App URL (`https://<domain>`); the Menu Button updates immediately.

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
2. Use the Mini App → **Search** tab to search all configured indexers.

The Jackett API key is read automatically from the mounted config file — no manual copy/paste needed.

> **Security:** The Jackett web UI is publicly accessible on the configured port. The installer prompts you to set an admin password during setup. You can also change or remove it later via Mini App → Settings → Jackett → 🔒 Change admin password.

---

## Video upscaling (GPU)

The stack includes an `upscaler` worker container that upscales a torrent's video files in place (Mini App → Torrents → 🗂 → **Upscale**). It runs on the GPU via ffmpeg's libplacebo (Vulkan) and needs a render device:

- **AMD / Intel iGPU** — works out of the box; `docker-compose.yml` maps `/dev/dri` into the container.
- **No GPU** — leave the stack as-is; every other feature works, but upscale jobs fail with a clear "no GPU device" error. Comment out the `devices:` line for the `upscaler` service if the missing `/dev/dri` prevents the container from starting.
- **NVIDIA** — add a runtime override in `docker-compose.override.yml` exposing the NVIDIA runtime/devices to the `upscaler` service.

No installer prompt is involved — the container is created by `docker compose up -d` like the rest.
