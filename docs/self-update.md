# In-bot stack updates (updater container)

How the `/settings → Update` channel switcher (and the Mini App update
action) brings a real install to a new release — including compose topology
changes (new sidecars like `cloudflared`), not just the bot image.

## The problem

`docker compose` reconciliation must run on the host, but the bot runs in a
container with only the Docker socket — no compose CLI, no compose file, no
repo. The old `self_update` therefore only blue/green-swapped the **bot**
container from its own live config; it could not create a brand-new service
(e.g. `cloudflared`) or apply a changed `docker-compose.yml`.

Naively shelling out to `update.sh` is impossible/unsafe:

1. `update.sh` lives on the host; its files aren't mounted into the bot.
2. `update.sh` runs `docker compose down`, which stops the bot — i.e. it would
   SIGKILL the very process running the script, leaving the stack half-down.

The fix is a process that **outlives** the bot's recreation.

## The mechanism

The bot launches an **ephemeral updater container** via the Docker socket it
already mounts. The updater is **not** part of the compose project, so
`docker compose up -d` recreating the bot never touches it.

- Image: `docker:cli` (ships the compose plugin; a `docker-cli-compose` apk
  fallback is attempted if missing).
- The bot passes the updater script inline (`sh -c <bot/updater.sh>`), so the
  script is a single source of truth baked into the bot image — nothing to
  deliver to the host separately.
- Mounts: the Docker socket, and the **host project directory** at `/project`.
  The bot derives the host project dir from its own `/app/data` bind mount
  (host side of `./bot-data`, minus the `bot-data` leaf).
- `COMPOSE_PROJECT_NAME` is passed explicitly (host project-dir basename) so
  compose manages the **existing** stack rather than spawning a duplicate under
  a different project name.

The updater then mirrors `update.sh`: downloads the latest `docker-compose.yml`
+ `lang/*.sh`, pins `BOT_IMAGE_TAG` in `.env`, `docker compose pull`, and
`docker compose up -d --remove-orphans`.

### BOT_IMAGE_TAG passing (chosen strategy)

The bot reads the target tag in Python (it already has DB access) and passes it
to the updater as the `BOT_IMAGE_TAG` env var; the updater writes it into
`.env`. The `docker:cli` image has no python/sqlite, so the tag is **never**
re-read from the DB container-side — a single authoritative read where DB
access is native, no fragile duplication of the store logic in shell. The bot
also persists the tag to `store.set_config("bot_image_tag", …)` so cold starts
and `update.sh` agree.

## Success/failure notification

`update_pending` is a flag in SQLite on the shared `bot-data` volume, so it
survives any restart mechanism. Two completion cases:

- **Bot image changed** → compose recreates the bot; the old process (and its
  watcher task) dies mid-flight; the fresh bot's `_post_init` reads the flag and
  reports success. `_post_init` sends this **before** `start_webapp()`, and
  `start_webapp()` is wrapped so a Mini App startup hiccup can never swallow the
  notification.
- **Only sidecars changed** (bot not recreated) → the launching process stays
  alive, watches the updater to completion, clears the flag and reports the
  outcome itself.

On launch failure (can't reach Docker, can't locate the project dir, image
pull fails) nothing destructive has happened: the old bot keeps running and
reports the error.

## One-time bootstrap (transition to this system)

Existing installs don't yet have the bot code that launches the updater, so the
**first** hop to the release that introduces this must be done by the only actor
that exists on the host today:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/update.sh)
```

That run delivers the new bot image (which carries the updater logic) and the
new compose (with `cloudflared`). **After this one host-run, every subsequent
update goes through the in-bot button** — the updater container handles the
rest. Communicate this one-time step in the release notes for the release that
ships the Mini App.

### Named Cloudflare tunnel note

The updater path is self-contained and works for both quick-tunnel (default)
and named-tunnel installs, because it re-runs full `docker compose up -d`
against the host's own `.env` — it does not need to know the tunnel token
(unlike the old socket-only approach, which could not).
