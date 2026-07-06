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

Three image tracks, each backed by a git ref (path filters: `bot/**`, `lang/**`, `pyproject.toml`, `docker-compose.yml`). Full description in `CLAUDE.md` and the maintainer runbook in `docs/releases.md`.

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `build-dev.yml` | push to `dev` | Builds `:dev`, then triggers `dev-deploy.yml` |
| `build-edge.yml` | push to `main` | Builds `:edge` (no deploy) |
| `build-release.yml` | published GitHub Release | Builds `:vX.Y.Z` + `:stable` + `:latest` (no deploy) |
| `dev-deploy.yml` | after `build-dev.yml` | SSHes into the maintainer's dev VM (Tailscale) and calls the Watchtower HTTP API |

`dev-deploy.yml` is for the repo maintainer's own dev VM (whose `.env` pins `BOT_IMAGE_TAG=dev`). In forks, the deploy step is a no-op if the server `.env` is absent.

Required secrets for `dev-deploy.yml`:

| Secret | Value |
|--------|-------|
| `DEV_SERVER_HOST` | Dev VM Tailscale host/IP |
| `DEV_SERVER_USER` | SSH username |
| `DEV_SERVER_SSH_KEY` | Private SSH key |
| `DEV_SSH_PORT` | SSH port |
| `TS_OAUTH_CLIENT_ID` / `TS_OAUTH_CLIENT_SECRET` | Tailscale OAuth for the CI node |

Workflows can also be triggered manually via Actions → Run workflow.

## Releasing a new version

The git tag on a GitHub Release **is** the version (`pyproject.toml` version is frozen at `0.0.0` and never bumped). To cut a release: merge `dev → main` (builds `:edge`), then GitHub → Releases → create a new release with tag `vX.Y.Z` targeting `main` (builds `:stable`/`:vX.Y.Z`). Prod bots pick it up via `/settings` → Update. See `docs/releases.md`.
