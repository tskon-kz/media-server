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

Generate `WATCHTOWER_TOKEN`: `openssl rand -hex 16`

---

## Runtime config (SQLite)

Stored in `/app/data/media_server.db` (host bind-mount: `./bot-data/media_server.db`). Managed by the bot via `/settings` and written by `install.sh`.

| Key | Description |
|-----|-------------|
| `lang` | `"ru"` or `"en"` |
| `server_ip` | Public IP shown in bot web UI links |
| `proxy_url` | SOCKS5 proxy for Telegram, e.g. `socks5://user:pass@host:port` |
| `jellyfin_api_key` | Jellyfin API key |
| `qb_user` / `qb_pass` | qBittorrent WebUI credentials |
| `qb_pass_is_perm` | `"1"` if password was explicitly set (vs auto-generated temp) |
| `qb_conn_status` | `"unknown"` / `"ok"` / `"error"` — connection health |
| `jackett_api_key` | Jackett API key for `/search` (set via `/settings` → Jackett) |
| `cats_init` | `"1"` once categories table is initialized with defaults |
| `update_pending` | `"1"` between Watchtower trigger and bot restart |

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

Creating a category via `/settings` → Categories creates the Jellyfin library automatically. Deleting it removes the library.

---

## Language

Switch via `/settings` → Language. Affects all bot messages. Supported: Russian, English. Default: Russian.

Also affects `install.sh`, `teardown.sh`, and `migrate-media.sh` (shell-level localization).

---

## Telegram proxy

If your server doesn't have direct access to Telegram, set a SOCKS5 proxy in `/settings` → (not directly exposed — set during install or via database):

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
