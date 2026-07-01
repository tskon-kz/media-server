# Media Server

> [Русская версия](README.ru.md)

Jellyfin + qBittorrent + Telegram Bot on a single server.

## Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/install.sh)
```

The script starts by asking for the interface language, then installs Docker if missing, downloads the necessary files to `~/media-server/`, asks for credentials, configures qBittorrent and Jellyfin, and starts all containers.

### What the installer asks for

| Prompt | Description |
|--------|-------------|
| Language | English or Russian |
| Telegram Bot Token | From [@BotFather](https://t.me/BotFather) |
| Your Telegram ID | From [@userinfobot](https://t.me/userinfobot). Comma-separated for multiple users |
| Server IP | External IP for web UI links in the bot |
| Media path | Host path mounted as `/media` (default: `./media`). Use a mounted disk path, e.g. `/mnt/disk2` |
| Jellyfin admin username / password | Created on first run |
| Jellyfin server name | Optional, defaults to `Media Server` |
| Telegram proxy | Optional, e.g. `socks5://user:pass@host:port` |
| Custom ports | Optional — press `n` to use defaults (Jellyfin: 8096, qBittorrent: 8080) |

### Manual setup

If you prefer not to use the installer:

```bash
git clone https://github.com/tskon-kz/media-server ~/media-server
cd ~/media-server
cp /dev/null .env
```

Add to `.env`:

```dotenv
BOT_TOKEN=...          # from @BotFather
ALLOWED_USER=123456789 # from @userinfobot; comma-separated for multiple users
WATCHTOWER_TOKEN=...   # any random string, e.g.: openssl rand -hex 16

# Optional — uncomment to override defaults
# JELLYFIN_PORT=8096
# QB_PORT=8080
# MEDIA_PATH=./media
```

Then seed the database with values `install.sh` would normally collect:

```bash
DB=bot-data/media_server.db
mkdir -p bot-data
python3 -c "
import sqlite3, sys
db = sqlite3.connect('$DB')
db.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
db.executemany('INSERT OR REPLACE INTO config VALUES (?,?)', [
    ('server_ip',  'YOUR_SERVER_IP'),
    ('lang',       'en'),
    ('proxy_url',  ''),           # optional: socks5://user:pass@host:port
])
db.commit()
"
docker compose up -d
```

After containers start, configure qBittorrent and Jellyfin manually via their web UIs, then store the credentials:

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('$DB')
db.executemany('INSERT OR REPLACE INTO config VALUES (?,?)', [
    ('qb_user',          'admin'),
    ('qb_pass',          'YOUR_QB_WEBUI_PASSWORD'),  # from qBittorrent WebUI → Tools → Options → Web UI
    ('jellyfin_api_key', 'YOUR_JELLYFIN_API_KEY'),
])
db.commit()
"
```

Jellyfin API key: Dashboard → API Keys → +.

## Bot usage

### Adding torrents

Send a **magnet link** or a **.torrent file** — the bot will ask which category to save it to. When the download finishes, you get a notification and Jellyfin scans the library automatically.

### Commands

| Command | Action |
|---------|--------|
| `/list` | Torrent list with status icons and buttons |
| `/status` | Current download / upload speeds |
| `/scan` | Trigger a Jellyfin library scan |
| `/settings` | Settings menu |

### `/list`

- Status icons: ⬇️ downloading, ✅ done, ⏸ paused, 🌱 seeding, ❌ error
- **Edit mode** — per-torrent buttons: 🗑 delete with files, 📁 move to category

### `/settings`

| Section | What you can do |
|---------|-----------------|
| Categories | Add, rename, delete. Each category maps to a folder and a Jellyfin library |
| Language | Switch between Russian and English |
| Jellyfin users | Add and delete Jellyfin accounts |
| Update | Check for updates and apply with one tap |
| Quick links | Open qBittorrent / Jellyfin web UI directly from the menu |

### Updates

The bot checks for a new version every 6 hours and sends a notification. To update manually: `/settings` → **Update** → **Update now**. The bot restarts automatically within ~1 minute.

### Categories

Default: **Movies** (`/media/movies`) and **Series** (`/media/series`).

Adding a category creates a Jellyfin library. Deleting it removes the library. Available types: Movies, TV Shows, Music, Mixed.

## CI/CD

Two workflows run on push to `main` when `bot/`, `lang/`, or `pyproject.toml` change:

**`build-push.yml`** — builds a Docker image and pushes it to `ghcr.io` with `:latest` and `:<version>` tags. No secrets required beyond the default `GITHUB_TOKEN`.

**`dev-deploy.yml`** — triggers after a successful build and SSHes into the server to call the Watchtower HTTP API. This is for the repo maintainer's own server; forks can ignore or delete this file. Requires these repository secrets:

| Secret | Value |
|--------|-------|
| `SERVER_HOST` | Server IP |
| `SERVER_USER` | SSH username |
| `SERVER_SSH_KEY` | Private SSH key |
| `SSH_PORT` | SSH port |

Both workflows can also be triggered manually via **Actions → Run workflow**.

## Moving the media library

```bash
bash migrate-media.sh
```

Stops containers, copies all media to the new path with rsync (shows progress), updates `MEDIA_PATH` in `.env`, restarts containers. Checks free space before starting.

## Teardown

```bash
bash teardown.sh
```

Stops all containers (optionally removes Docker images), deletes `data/`, `bot-data/`, and `.env`. Optionally deletes `media/`.

## Access

- Jellyfin: `http://SERVER_IP:8096`
- qBittorrent: `http://SERVER_IP:8080`
