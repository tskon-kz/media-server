# Media Server

> [Русская версия](README.ru.md)

Jellyfin + qBittorrent + Telegram Bot on a single server.

## Quick start

```bash
git clone https://github.com/tskon-kz/mediaserver.git ~/media-server
cd ~/media-server
bash setup.sh
```

`setup.sh` installs Docker if missing, asks for all credentials, automatically configures qBittorrent and Jellyfin, and starts all containers. Run `bash setup.sh` again any time to reconfigure.

### What setup asks for

| Prompt | Description |
|--------|-------------|
| Telegram Bot Token | From [@BotFather](https://t.me/BotFather) |
| Your Telegram ID | From [@userinfobot](https://t.me/userinfobot). Comma-separated for multiple users |
| Server IP | External IP for web UI links in the bot |
| qBittorrent password | WebUI password (login: `admin`) |
| Jellyfin admin username / password | Created automatically on first run |
| Jellyfin server name | Optional, defaults to `Media Server` |
| Telegram proxy | Optional, e.g. `socks5://user:pass@host:port` |
| Custom ports | Optional — press `n` to skip all and use defaults (Jellyfin: 8096, qBittorrent: 8080) |

### .env reference

```dotenv
# Required
BOT_TOKEN=...
ALLOWED_USER=123456789          # comma-separated Telegram IDs
SERVER_IP=1.2.3.4

# Optional
PROXY_URL=socks5://user:pass@host:port
JELLYFIN_PORT=8096              # default
QB_PORT=8080                    # default
```

`JELLYFIN_API_KEY` is added automatically during setup and must not be set manually.

## Bot usage

### Adding torrents

Send a **magnet link** or a **.torrent file** in the chat — the bot will ask which category to save it to. When the download finishes, you get a notification and Jellyfin scans the library automatically.

### Commands

| Command | Action |
|---------|--------|
| `/list` | Torrent list with status icons and buttons |
| `/status` | Current download / upload speeds |
| `/scan` | Trigger a Jellyfin library scan |
| `/settings` | Settings menu |

### `/list` details

- Status icons: ⬇️ downloading, ✅ done, ⏸ paused, 🌱 seeding, ❌ error, and more
- **Edit mode** — shows per-torrent buttons: 🗑 delete (with files) and 📁 move to category

### `/settings` menu

| Section | What you can do |
|---------|-----------------|
| Categories | Add, rename, delete. Each category maps to a folder and a Jellyfin library |
| Language | Switch between Russian and English |
| qBittorrent password | Change WebUI password |
| Jellyfin users | Add and delete Jellyfin accounts |
| Quick links | Open qBittorrent / Jellyfin web UI directly from the menu |

### Categories

Default categories: **Movies** (`/media/movies`) and **Series** (`/media/series`).

Adding a category creates a matching Jellyfin library. Deleting a category removes the library from Jellyfin. Available library types: Movies, TV Shows, Music, Mixed.

## CI/CD

Add these secrets to the repository: **Settings → Secrets and variables → Actions**

| Secret | Value |
|--------|-------|
| `SERVER_HOST` | Server IP |
| `SERVER_USER` | SSH username |
| `SERVER_SSH_KEY` | Private SSH key |
| `SSH_PORT` | SSH port |

Every push to `main` pulls the latest code on the server and restarts the bot container.

## Teardown

```bash
bash teardown.sh
```

Stops all containers (optionally removes Docker images), deletes `data/`, `.env`, and bot config files (`creds.json`, `lang.json`, `categories.json`). Optionally deletes `media/`. Repository files are untouched.

## Access

- Jellyfin: `http://SERVER_IP:8096` (or custom `JELLYFIN_PORT`)
- qBittorrent: `http://SERVER_IP:8080` (or custom `QB_PORT`)
