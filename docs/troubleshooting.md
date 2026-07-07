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

> **Note:** This updates the infrastructure (compose file, images) and syncs
> `BOT_IMAGE_TAG` in `.env` with the tag the bot last self-updated to (stored in
> the DB, default `stable`). The bot itself normally updates via `/settings` →
> Update (see below); Watchtower remains only as a weekly safety net.

---

## Updating the bot — `/settings` → Update

The bot updates **itself**, locally, through the Docker socket it mounts — no
GitHub secrets, no per-install configuration. `/settings` → Update offers a
**channel switcher** (Stable / Edge):

- **⬆️ Update to `vX.Y.Z`** — shown when a newer published release exists.
  Pulls the `:stable` image and replaces the bot container.
- **Switch to Edge** — switches to the `:edge` channel (latest `main`, unreleased).
  Requires a confirmation tap. Use for testing a fix before it's tagged.
- **Switch to Stable** — shown when on Edge; switches back to `:stable`.
- **🔄 Refresh Edge** — shown when on Edge; re-pulls the latest `:edge` build.

The bot starts the replacement container *before* stopping the old one, so a bad
pull leaves the running bot untouched and reports the failure. On success it
messages "Bot restarted and running …" once the new container boots.

The passive check polls the GitHub Releases API every 6h and notifies you when a
newer release tag is available.

---

## Rolling back to a specific version

Every release also pushes an immutable `:vX.Y.Z` tag. If a release is bad and the
in-bot flow is unavailable (e.g. the bot won't start), roll back manually on the
server:

```bash
cd ~/media-server
# 1. point compose at the known-good version
sed -i 's/^BOT_IMAGE_TAG=.*/BOT_IMAGE_TAG=v1.4.0/' .env   # or add the line if absent
# 2. also record it as the runtime default so update.sh won't undo it
python3 -c "import sqlite3; d=sqlite3.connect('bot-data/media_server.db'); \
d.execute(\"INSERT OR REPLACE INTO config VALUES ('bot_image_tag','v1.4.0')\"); d.commit()"
# 3. pull and restart just the bot
docker compose pull telegram-bot
docker compose up -d telegram-bot
```

Once a fixed release is out, update normally via `/settings` → Update (or set the
tag back to `stable` and repeat the steps above).

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
