# Dev Setup

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Node.js 20+ (for Mini App frontend development)
- Running qBittorrent instance (local or remote)
- Running Jellyfin instance (local or remote)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Running the bot locally (Python, no Docker)

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

---

## Deploying the dev stack on a dev server (from `dev` branch)

This is the recommended workflow for testing changes from `dev` before they reach `main`/`:stable`.

### 1. Initial install

Run `install.sh` from the `dev` branch on the dev server. This sets up Jellyfin, qBittorrent, Jackett, writes credentials to the SQLite DB, and generates `.env`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/dev/install.sh)
```

### 2. Switch to the `:dev` Docker image

After install, open `.env` and change (or add) the image tag:

```bash
nano .env   # set: BOT_IMAGE_TAG=dev
```

### 3. Download the dev-branch compose files

The files installed by `install.sh` come from `main`. Pull the dev versions:

```bash
curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/dev/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/dev/docker-compose.dev.yml -o docker-compose.dev.yml
```

### 4. Start the full dev stack

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

`docker-compose.dev.yml` does two things on top of the base compose:
- publishes port **8081** on the host so the Mac's Vite dev server can reach the API
- sets **`WEBAPP_DEV_MODE=1`** which disables Telegram `initData` auth (safe for dev only — never apply on a production install)

To pull a freshly built `:dev` image after new commits to `dev`:

```bash
docker compose pull telegram-bot && docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d telegram-bot
```

### Re-deploying after teardown

Same two commands — no need to re-run `install.sh` if `.env` and `bot-data/` still exist:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

---

## Mini App frontend (Vite hot-reload on Mac)

The React SPA lives in `webapp/`. In production it's built into the Docker image and served as static files. In dev, Vite runs on your local machine and proxies `/api` to the dev server.

**Requires:** the dev server is running with `docker-compose.dev.yml` applied (port 8081 published, `WEBAPP_DEV_MODE=1`), and the dev server is reachable from the Mac (e.g. via Tailscale).

### Setup (once)

```bash
cp webapp/.env.example webapp/.env
# edit webapp/.env — set VITE_DEV_API_BASE to the dev server's Tailscale address:
# VITE_DEV_API_BASE=http://<dev-tailscale-ip>:8081
```

### Start

```bash
make dev
# equivalent to: npm run dev --prefix webapp
```

Opens at `http://localhost:5173`. All `/api` requests are proxied to the dev server.

**What works in the browser vs. Telegram:**

| Feature | Browser (localhost:5173) | Telegram (via Menu Button) |
|---|---|---|
| API calls, screens, navigation | ✅ | ✅ |
| Telegram theme (dark/light) | ❌ (system default) | ✅ |
| MainButton / BackButton | ❌ | ✅ |
| Haptic feedback | ❌ | ✅ |

Use the browser for UI/API development. Use Telegram for final verification.

### Testing inside Telegram

The Menu Button in the Telegram chat points to the cloudflared `trycloudflare.com` URL, which serves the SPA built into the `:dev` Docker image (not the Vite dev server). To test in Telegram:

1. Ensure the dev server is running (step 4 above)
2. Wait ~60 s for the bot to detect the cloudflared URL and update the Menu Button
3. Tap the Menu Button in the Telegram chat

To check the resolved URL:

```bash
docker logs media-server-cloudflared 2>&1 | grep trycloudflare
```

---

## Building the Docker image manually

```bash
docker build -f bot/Dockerfile -t media-server-bot --build-arg VERSION=dev .
```

The `VERSION` build arg sets the `APP_VERSION` env var inside the container. Bots with `VERSION=dev` never report an available update.

---

## Project structure

```
.
├── bot/
│   ├── main.py         # PTB ApplicationBuilder setup, job scheduling
│   ├── handlers/       # Command/message/callback handlers + background jobs
│   │   ├── commands.py # /start /update
│   │   ├── messages.py # Text handler (manual-rename state)
│   │   ├── callbacks.py# Inline keyboard callback dispatcher
│   │   ├── jobs.py     # Background jobs (done-check, update-check, qb-restart-check, webapp-url-check — polls cloudflared logs for trycloudflare.com URL)
│   │   └── _utils.py   # guard decorator, shared helpers
│   ├── api.py          # Jellyfin + qBittorrent + Watchtower + Docker socket calls; get_cloudflared_url()
│   ├── keyboards.py    # Inline keyboard builders and text renderers
│   ├── config.py       # Env vars and constants (WEBAPP_URL, WEBAPP_DEV_MODE, ...)
│   ├── store.py        # SQLite persistence
│   ├── parser/         # Package: filenames, naming, fsops, linker (+ __init__ re-exports)
│   ├── webapp/         # aiohttp server: server.py (runner), auth.py (initData HMAC), routes.py (REST API)
│   └── Dockerfile      # Multi-stage: node (SPA build) → python (final image)
├── webapp/             # React SPA (Vite + TypeScript) — built into the Docker image
│   ├── src/
│   │   ├── screens/            # TorrentList, AddTorrent, Search, Status, Settings
│   │   ├── components/         # Toast, Sheet, Collapse, Section, PageHeader, PromptSheet, CategoryPicker, ui.tsx
│   │   ├── store/              # Redux Toolkit store; slices: searchSlice, themeSlice
│   │   ├── locales/            # i18n strings: en.ts, ru.ts
│   │   ├── api.ts              # Typed fetch client (Authorization: tma <initData>)
│   │   ├── telegram.ts         # Thin wrapper over window.Telegram.WebApp
│   │   ├── i18n.ts             # react-i18next setup
│   │   ├── icons.tsx           # Lucide icon re-exports
│   │   └── styles/globals.scss # Telegram-native CSS variables (--tg-theme-*)
│   └── .env.example    # Copy to .env and set VITE_DEV_API_BASE
├── upscaler/           # GPU video-upscale worker (polls the shared upscale_jobs queue)
│   ├── main.py         # Queue poller loop
│   ├── runners.py      # ffmpeg/libplacebo backends (anime4k, fsr)
│   ├── db.py           # Shared SQLite access
│   └── Dockerfile      # jellyfin-ffmpeg + Anime4K shaders + Vulkan drivers
├── lang/
│   ├── ru.py / en.py   # Bot message strings
│   └── ru.sh / en.sh   # Shell message strings (for install.sh)
├── docker-compose.yml
├── docker-compose.dev.yml  # Dev overlay: publishes port 8081, enables WEBAPP_DEV_MODE
├── Makefile            # make dev → npm run dev --prefix webapp
├── install.sh
├── update.sh
├── migrate-media.sh
└── teardown.sh
```

---

## CI/CD

Three image tracks, each backed by a git ref (path filters: `bot/**`, `webapp/**`, `lang/**`, `pyproject.toml`, `docker-compose.yml`):

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `build-dev.yml` | push to `dev` | Builds `:dev`, then triggers `dev-deploy.yml` |
| `build-edge.yml` | push to `main` | Builds `:edge` (no deploy) |
| `build-release.yml` | published GitHub Release | Builds `:vX.Y.Z` + `:stable` + `:latest` (no deploy) |
| `dev-deploy.yml` | after `build-dev.yml` | SSHes into the maintainer's dev VM (Tailscale) and calls the Watchtower HTTP API |

`dev-deploy.yml` is for the repo maintainer's own dev VM (whose `.env` pins `BOT_IMAGE_TAG=dev`). In forks, the deploy step is a no-op if the secrets are absent.

Required secrets for `dev-deploy.yml`:

| Secret | Value |
|--------|-------|
| `DEV_SERVER_HOST` | Dev VM Tailscale host/IP |
| `DEV_SERVER_USER` | SSH username |
| `DEV_SERVER_SSH_KEY` | Private SSH key |
| `DEV_SSH_PORT` | SSH port |
| `TS_OAUTH_CLIENT_ID` / `TS_OAUTH_CLIENT_SECRET` | Tailscale OAuth for the CI node |

Workflows can also be triggered manually via Actions → Run workflow.

---

## Releasing a new version

The git tag on a GitHub Release **is** the version (`pyproject.toml` version is frozen at `0.0.0` and never bumped). To cut a release: merge `dev → main` (builds `:edge`), then GitHub → Releases → create a new release with tag `vX.Y.Z` targeting `main` (builds `:stable`/`:vX.Y.Z`). Prod bots pick it up via Mini App → Settings → Update (or `/update`). See `docs/releases.md`.
