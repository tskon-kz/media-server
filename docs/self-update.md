# In-bot updates (bot-only blue/green swap)

How the Mini App → Settings → Update channel switcher (Stable / Edge) and the `/update`
update action bring an install to a new bot version — **without touching any other
service**. Infrastructure/topology changes (compose file, new sidecars, bumping
Jellyfin/qBittorrent versions) are deliberately **not** done in-bot; they go
through `update.sh` on the host.

## Why bot-only

A routine update only needs a newer bot image. Recreating the whole compose stack
on every update is what made earlier versions unstable:

- `docker compose up -d` recreating **qBittorrent** churns its session temp
  password → the bot's stored credentials stop matching → empty torrent list.
- Recreating **cloudflared** (quick-tunnel) assigns a new `trycloudflare.com`
  URL → a 502 window until the bot re-scrapes it.

So the in-bot updater does the minimum: replace **only** the bot container. The
canonical container name is preserved, so cloudflared keeps resolving
`telegram-bot` and the tunnel never moves. qBittorrent/Jellyfin/Jackett are never
restarted.

## The mechanism (`api.self_update`)

Blue/green, new-before-old, via the Docker socket the bot already mounts:

1. Pull `ghcr.io/<owner>/media-server-bot:<tag>` (`tag` = `stable` or `edge`).
2. Inspect the running bot container (its ID is the in-container hostname) to
   clone its live config: env (dropping `APP_VERSION` so the new image's baked-in
   value wins), binds, labels, network, restart policy.
3. Start a replacement under a temp name (`…-telegram-bot-new`) and confirm it
   stays `running` for ~6 s. A bad pull/start never stops the healthy bot.
4. Healthy → rename the old container aside (`…-telegram-bot-old`), rename the new
   one to the canonical `media-server-telegram-bot`, persist the tag to the DB
   (`bot_image_tag`), then remove the old container (this stops the current
   process — state is already final).
5. Unhealthy → remove the replacement, leave the old bot running, return an error
   string that the still-alive bot reports.

## Success/failure notification

`update_pending` is a flag in SQLite on the shared `bot-data` volume, so it
survives the swap.

- **Success** → the old process is killed when its container is removed; the fresh
  bot's `_post_init` reads the flag, clears it, and sends "Bot restarted and
  running …". It is sent **before** `start_webapp()`, which is isolated so a Mini
  App startup hiccup can't swallow the notification.
- **Failure** → nothing destructive happened; `self_update` returns an error
  string, the launching coroutine clears the flag and reports why (the old bot is
  still running).

## Channels

The switcher persists the chosen tag to `bot_image_tag` in the DB and pulls that
tag. `install.sh` / `update.sh` resolve the DB value into `BOT_IMAGE_TAG` in
`.env`, so cold starts and in-bot switches never drift.

- **Stable** → `:stable` (latest published release).
- **Edge** → `:edge` (latest `main`, unreleased) — behind a confirmation, for
  beta-testing on your own server.

## Infrastructure updates (host `update.sh`)

Anything beyond the bot image — a new compose service (e.g. adding `cloudflared`),
a changed `docker-compose.yml`, or a bumped Jellyfin/qBittorrent digest — is
applied by running on the host:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/update.sh)
```

`update.sh` fetches the latest compose + scripts, pulls the bot image, and runs
`docker compose up -d`. This is deliberate and infrequent, done when you're
watching — not something a routine in-bot update triggers. Releases that require
it call it out in their notes.
