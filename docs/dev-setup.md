# Dev Setup

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Running qBittorrent instance (local or remote)
- Running Jellyfin instance (local or remote)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Running the bot locally

All env vars from `.env.example` must be set. When running outside Docker, also set `QB_HOST`:

```bash
cp .env.example .env
# fill in .env values

export QB_HOST=http://localhost:8080  # or wherever qBittorrent is running
```

Install dependencies and run:

```bash
uv pip install --system .
cd bot && python main.py
```

The bot connects to Telegram and starts polling. qBittorrent and Jellyfin must be reachable at the configured addresses.

## Building the Docker image

```bash
docker build -f bot/Dockerfile -t media-server-bot --build-arg VERSION=dev .
```

The `VERSION` build arg sets the `APP_VERSION` env var inside the container. It's used for version checks — bots with `VERSION=dev` will never report an available update.

## Running the full stack locally

```bash
cp .env.example .env  # fill in values
docker compose up -d
```

This starts Jellyfin, qBittorrent, the bot, and Watchtower.

## Project structure

```
.
├── bot/
│   ├── main.py         # PTB ApplicationBuilder setup, job scheduling
│   ├── handlers/       # Command/message/callback handlers + background jobs
│   │   ├── commands.py # /start /list /status /scan /settings
│   │   ├── messages.py # Magnet link and .torrent file handlers
│   │   ├── callbacks.py# Inline keyboard callback dispatcher
│   │   ├── jobs.py     # Background jobs (done-check, update-check, qb-restart-check)
│   │   └── _utils.py   # guard decorator, shared helpers
│   ├── api.py          # Jellyfin + qBittorrent + Watchtower + Docker socket calls
│   ├── keyboards.py    # Inline keyboard builders and text renderers
│   ├── config.py       # Env vars and constants
│   ├── store.py        # SQLite persistence
│   ├── parser/         # Package: filenames, naming, fsops, linker (+ __init__ re-exports)
│   └── Dockerfile
├── lang/
│   ├── ru.py / en.py   # Bot message strings
│   └── ru.sh / en.sh   # Shell message strings (for install.sh)
├── docker-compose.yml
├── install.sh
├── update.sh
├── migrate-media.sh
└── teardown.sh
```

## CI/CD

Two GitHub Actions workflows trigger on changes to `bot/`, `lang/`, or `pyproject.toml` on `main`:

| Workflow | What it does |
|----------|-------------|
| `build-push.yml` | Builds and pushes bot image to `ghcr.io` with `:latest` and `:<version>` tags |
| `dev-deploy.yml` | SSHes into the maintainer's server and calls Watchtower HTTP API to update |

`dev-deploy.yml` is for the repo maintainer's own server. In forks, the deploy step is skipped automatically if `SERVER_HOST` secret is not set.

Required secrets for `dev-deploy.yml`:

| Secret | Value |
|--------|-------|
| `SERVER_HOST` | Server IP |
| `SERVER_USER` | SSH username |
| `SERVER_SSH_KEY` | Private SSH key |
| `SSH_PORT` | SSH port |

Both workflows can also be triggered manually via Actions → Run workflow.

## Bumping the version

Version is read from `pyproject.toml → [project].version`. Bumping it triggers an update notification to all bot users (the bot checks `pyproject.toml` on GitHub every 6 hours).
