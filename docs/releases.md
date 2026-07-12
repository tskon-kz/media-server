# Release & deployment runbook (maintainer)

The bot ships as three independent image tracks on GHCR, each backed by a git ref.
The **git tag on a GitHub Release is the version** — `pyproject.toml`'s version is
frozen at `0.0.0` and never bumped.

| Track | Git ref | Image tag | Auto-deploys? |
|-------|---------|-----------|---------------|
| Dev | push to `dev` | `:dev` | Yes → maintainer's dev VM (Tailscale + Watchtower) |
| Edge | push to `main` | `:edge` | No — available on prod as "Force update" |
| Release | published GitHub Release | `:vX.Y.Z` + `:stable` (+ `:latest`) | No — deployed via Telegram |

## Normal workflow

1. **Work on `dev`.** Push freely — `build-dev.yml` builds `:dev` and `dev-deploy.yml`
   auto-deploys it to the dev VM. Nothing else is affected.
2. **When a change is ready for prod**, open a PR `dev → main` and merge it
   (`main` takes no direct pushes). Merging alone builds `:edge` — nothing
   auto-deploys, but the code is now installable on prod via "Force update" for
   final testing.
3. **Cut a release:** GitHub → **Releases → "Create a new release"** → choose a
   new tag `vX.Y.Z`, target `main`, publish. `build-release.yml` builds
   `:vX.Y.Z`, moves `:stable` to that digest, and refreshes `:latest`. This is
   the only thing the prod bots' passive update-check notifies about.
4. **Deploy to prod:** in Telegram, Mini App → Settings → Update (or `/update`) → **Update to `vX.Y.Z`**.
   The bot pulls `:stable` and blue/green-replaces its own container.

## Update actions in the bot

Mini App → Settings → Update (and the `/update` command) shows different controls depending on the active channel:

**On `:stable` (default):**
- **⬆️ Update to `vX.Y.Z`** — shown only when a newer published release exists.
  Deploys `:stable`. (`selfupdate:stable`)
- **Switch to Edge** — switches to the `:edge` channel (unreleased `main`);
  asks for a confirmation tap first. (`selfupdate:edge:confirm` → warning →
  `selfupdate:edge:go`)

**On `:edge`:**
- A beta notice is shown instead of a version comparison (local is an
  `edge-<sha>` string that will never equal a release tag).
- **🔄 Refresh Edge** — re-pulls the latest `:edge` build. (`selfupdate:edge:go`)
- **Switch to Stable** — switches back to `:stable`. (`selfupdate:stable`)

Both channel switches send a "restarting, back in ~1 minute" message *before* the
swap (the bot process is replaced mid-flow and can't reliably message afterward).
The freshly started container confirms itself on boot ("Bot restarted and running …").

## How self-update works (and why there's no CI deploy for prod)

This stack is installed independently by many people on their own servers, so
nothing in this repo's Actions can reach them (a repo secret only works for the
maintainer's own box). Deployment is therefore **100% local to each server**,
using the `docker.sock` the bot already mounts:

1. Pull `ghcr.io/<owner>/media-server-bot:<tag>`.
2. Inspect the running bot container (its ID is the in-container hostname) to
   clone env, mounts, network, restart policy and labels.
3. **New-before-old:** start a replacement under a temp name, confirm it stays
   `running` for a few seconds. A bad pull never stops the healthy bot.
4. Healthy → rename old aside, rename new to the canonical name, remove old.
   Unhealthy → remove the new one, leave the old running, report the failure.
5. Persist the tag to the DB (`bot_image_tag`) so cold starts agree.

**Only the bot container is touched.** qBittorrent/Jellyfin/Jackett/cloudflared
are never recreated by an in-bot update, so it can't reset qB auth or move the
tunnel URL. Infrastructure/topology changes (compose file, new sidecars, bumped
service digests) are applied deliberately on the host via `update.sh` — call them
out in the release notes when a release needs it. See `docs/self-update.md`.

## Manual follow-up (not automatable from this repo)

- **Branch protection:** in GitHub repo settings, protect `main` so it only
  accepts PRs from `dev` (or hotfix branches), never direct pushes.

## Rollback

See `docs/troubleshooting.md → Rolling back to a specific version`.
