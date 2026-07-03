# Troubleshooting & Maintenance Scripts

## `update.sh` — Update infrastructure files

Use when you want to pull the latest `docker-compose.yml` and shell scripts from the repo without reinstalling.

```bash
bash update.sh
# or remotely:
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/update.sh)
```

**What it does:**
1. Downloads the latest `docker-compose.yml`, `update.sh`, and `lang/` files
2. Stops all containers
3. Applies the new `docker-compose.yml`
4. Pulls the latest Docker images
5. Starts containers again

> **Note:** This updates the infrastructure (compose file, images). The bot itself updates automatically via Watchtower, or manually via `/settings` → Update in the bot.

---

## `teardown.sh` — Remove everything

Use when you want to fully uninstall the stack from the server.

```bash
bash teardown.sh
```

**Interactive prompts:**
1. Confirm teardown (Y/n)
2. Remove Docker images too? (Y/n) — removes downloaded images, freeing disk space
3. Remove media folder? (Y/n) — destructive: deletes all your media files

**What it removes:**
- All containers and their volumes
- `data/` — Jellyfin config and metadata
- `bot-data/` — SQLite database (settings, categories, torrent states)
- `.env` — credentials file
- `media/` — only if you confirm at the prompt

> **Warning:** This is irreversible. The bot will stop responding immediately. Media files are only deleted if you explicitly confirm.

---

## `migrate-media.sh` — Move media to a new path

Use when you want to move the media library to a different disk or directory (e.g., you attached a larger drive).

```bash
bash migrate-media.sh
```

**Interactive prompts:**
1. Select language
2. Shows the current media path
3. Enter new path (e.g. `/mnt/disk2`)
4. Shows transfer plan: source, destination, size, available space
5. Confirm (Y/n)
6. After copy: remove old media directory? (Y/n)

**What it does:**
1. Stops all containers
2. Copies media via `rsync -a --info=progress2` (shows progress)
3. Checks free space before starting — aborts if insufficient
4. Updates `MEDIA_PATH` in `.env`
5. Starts containers with the new path
6. Optionally removes the old directory

> **Note:** Containers are stopped during the copy. The bot is unavailable until the transfer completes.

---

## `migrate-jackett.sh` — Add Jackett to an existing installation

> **Temporary script** — will be removed from the repository once all existing installations have been updated.

Use this if you deployed the stack before Jackett support was added and want to add it without losing data.

```bash
bash migrate-jackett.sh
```

**What it does:**
1. Checks that `.env` and `docker-compose.yml` exist (exits with an error if not — use `install.sh` for a fresh install)
2. Skips silently if Jackett is already in `docker-compose.yml` (idempotent)
3. Downloads the latest `docker-compose.yml` (which includes the Jackett service)
4. Adds `JACKETT_PORT` comment to `.env` if it's missing
5. Runs `docker compose pull && docker compose up -d` — starts Jackett without touching existing services or data
6. Prints next steps: open Jackett UI, copy API key, configure via the bot

**What it does NOT touch:**
- `data/jellyfin`, `data/qbittorrent`, `bot-data/` — all data is preserved
- Media files and existing torrents — qBittorrent keeps seeding normally
- Any existing `.env` values

---

## Common issues

### Bot doesn't respond
- Check that `BOT_TOKEN` and `ALLOWED_USER` in `.env` are correct
- Check container logs: `docker compose logs telegram-bot`
- If you use a Telegram proxy, verify it's reachable

### qBittorrent auth error
The bot shows a connection error in `/list` or `/status`. This happens when the stored password doesn't match.

To recover: `/settings` → qBittorrent → Fetch temp password (reads the auto-generated password from container logs), then set a permanent password.

### Jellyfin library not updating
- Use `/scan` in the bot to trigger a manual scan
- Check that the category path exists: `/media/<slug>/`
- Verify the Jellyfin API key is still valid: Dashboard → API Keys

### Cross-device hardlink error (EXDEV)
Appears when qBittorrent download path and the category path are on different filesystems. Solution: ensure `MEDIA_PATH` (and therefore `/media`) is a single filesystem — don't mix local disk and mounted network paths.

### Bot update stuck
If the bot didn't restart after an update:
```bash
docker compose restart telegram-bot
```
