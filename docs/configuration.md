# Configuration

## `.env` variables

`.env` only contains what docker-compose needs at container startup. Most runtime config is stored in the SQLite database.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | — | Telegram bot token from @BotFather |
| `ALLOWED_USER` | Yes | — | Comma-separated Telegram user IDs |
| `WATCHTOWER_TOKEN` | Yes | — | Shared secret for Watchtower HTTP API (any random string) |
| `MEDIA_PATH` | No | `./media` | Host path mounted as `/media` in all containers |
| `JELLYFIN_PORT` | No | `8096` | Jellyfin web UI port |
| `QB_PORT` | No | `8080` | qBittorrent web UI port |
| `JACKETT_PORT` | No | `9117` | Jackett web UI port |
| `BOT_IMAGE_TAG` | No | `stable` | Bot image tag used at cold start (`docker compose up -d`) |
| `WATCHTOWER_PORT` | No | `9080` | Watchtower HTTP API port (bound to `127.0.0.1` only) |
| `WEBAPP_DOMAIN` | No | — | Own domain for the Mini App (e.g. `media.example.com`). Set → Caddy serves it with auto-HTTPS (needs inbound **TCP 80 + 443** open and a DNS A record) and the Cloudflare quick tunnel is switched off; the bot's `WEBAPP_URL` is derived as `https://<domain>`. Leave empty to use the quick tunnel. |
| `CADDY_HTTP_PORT` | No | `80` | Own-domain mode only. Host port mapped to Caddy's internal HTTP/ACME port. Set to a free host port when the host's 80 is occupied; external 80 must still route here (directly or via NAT forward) for cert issuance/renewal. |
| `CADDY_HTTPS_PORT` | No | `443` | Own-domain mode only. Host port mapped to Caddy's internal HTTPS port. Set to a free host port when the host's 443 is occupied; external 443 must still route here for the Mini App over HTTPS. |

Generate `WATCHTOWER_TOKEN`: `openssl rand -hex 16`

**`BOT_IMAGE_TAG`** selects which bot image `docker compose` pulls at container
creation: `stable` (latest release, the default), `edge` (unreleased `main`), or
a pinned `vX.Y.Z`. It's only read on cold starts; runtime switches happen via the
Mini App → Settings → Update (or `/update`), which writes the tag to the DB (`bot_image_tag`).
`install.sh`/`update.sh` resolve the DB value into this variable so the two never
drift. See `docs/releases.md`.

---

## Runtime config (SQLite)

Stored in `/app/data/media_server.db` (host bind-mount: `./bot-data/media_server.db`). Managed via the Mini App → Settings and written by `install.sh`.

| Key | Description |
|-----|-------------|
| `lang` | `"ru"` or `"en"` |
| `server_ip` | Public IP shown in bot web UI links |
| `proxy_url` | SOCKS5 proxy for Telegram, e.g. `socks5://user:pass@host:port` |
| `jellyfin_api_key` | Jellyfin API key |
| `qb_user` / `qb_pass` | qBittorrent WebUI credentials |
| `qb_pass_is_perm` | `"1"` if password was explicitly set (vs auto-generated temp) |
| `qb_conn_status` | `"unknown"` / `"ok"` / `"error"` — connection health |
| `rename_mode` | `"flat"` (original structure) or `"pretty"` (smart Jellyfin names) — controls what happens on download completion |
| `cats_init` | `"1"` once categories table is initialized with defaults |
| `bot_image_tag` | Image tag the bot last self-updated to (`stable` / `edge` / `vX.Y.Z`); source of truth for `BOT_IMAGE_TAG` |
| `update_pending` | `"1"` while a self-update restart is in flight; the new container clears it and reports success |
| `webapp_url` | The current cloudflared `trycloudflare.com` URL; written by the background `job_check_webapp_url` job; used to set the Telegram Menu Button |

---

## Categories

Each category maps 1:1 to:
- A filesystem folder: `/media/<slug>`
- A Jellyfin library
- A qBittorrent download path: `/media/.downloads/<slug>`

Files download to `/media/.downloads/<slug>`, then hardlinks are created in `/media/<slug>`. Jellyfin never sees partially-downloaded files.

**Default categories:**
- Movies → `/media/movies`
- Series → `/media/series`

**Available library types:**

| Type | Jellyfin library type |
|------|-----------------------|
| Movies | Movie |
| TV Shows | TV Shows |
| Music | Music |
| Mixed | Mixed Movies and Shows |

Creating a category via Mini App → Settings → Categories creates the Jellyfin library automatically. Deleting it removes the library.

---

## Language

Switch via Mini App → Settings → Language. Affects all bot messages. Supported: Russian, English. Default: English (the installer sets the language you pick at install time).

Also affects `install.sh`, `teardown.sh`, and `migrate-media.sh` (shell-level localization).

---

## Telegram proxy

If your server doesn't have direct access to Telegram, set a SOCKS5 proxy (not exposed in the Mini App — set during install or directly in the database):

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('bot-data/media_server.db')
db.execute(\"INSERT OR REPLACE INTO config VALUES ('proxy_url', 'socks5://user:pass@host:port')\")
db.commit()
"
```

Then restart the bot container: `docker compose restart telegram-bot`.

---

## Multiple users

Add comma-separated Telegram IDs to `ALLOWED_USER` in `.env`:

```dotenv
ALLOWED_USER=123456789,987654321
```

All listed users share the same bot and receive download notifications.
