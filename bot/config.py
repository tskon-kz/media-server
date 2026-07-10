import os

BOT_TOKEN        = os.environ["BOT_TOKEN"]
# Filter blanks so an empty/missing ALLOWED_USER yields an empty set (bot starts
# but admits no one) instead of crash-looping the whole process on int("").
ALLOWED          = frozenset(
    int(x) for x in os.environ.get("ALLOWED_USER", "").split(",") if x.strip()
)
QB_HOST          = os.environ["QB_HOST"]
JF_URL           = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096")
JF_PORT          = os.environ.get("JELLYFIN_PORT", "8096")
QB_PORT          = os.environ.get("QB_PORT", "8080")
JACKETT_URL      = os.environ.get("JACKETT_URL", "http://jackett:9117")
JACKETT_PORT     = os.environ.get("JACKETT_PORT", "9117")
APP_VERSION      = os.environ.get("APP_VERSION", "dev")
WATCHTOWER_TOKEN = os.environ.get("WATCHTOWER_TOKEN", "")


def current_channel() -> str:
    """Channel of the ACTUALLY-running image, read from the baked-in APP_VERSION
    (edge builds → `edge-<sha>`, releases → `vX.Y.Z`). This is the source of
    truth for the UI, immune to `bot_image_tag` drift when the image was switched
    from the host (`.env` + `docker compose up -d`) instead of via the bot.
    """
    return "edge" if APP_VERSION.startswith("edge") else "stable"


WEBAPP_PORT      = 8081  # internal-only (compose network); never published to the host
WEBAPP_URL       = os.environ.get("WEBAPP_URL", "")  # static override for named CF tunnel
# Dev-only auth bypass for the Mini App API. When enabled, /api/* skips Telegram
# initData validation and acts as the configured ALLOWED user — used when the
# frontend runs in a plain browser (Vite dev server) with no Telegram context.
# MUST stay off in production.
WEBAPP_DEV_MODE  = os.environ.get("WEBAPP_DEV_MODE", "").lower() in ("1", "true", "yes")

SEARCH_PAGE_SIZE  = 5
BOT_SEARCH_LIMIT  = 30

# Torznab categories sent to Jackett so search returns only video content:
# Movies (2000–2080) and TV (5000–5080).
SEARCH_CATEGORIES = [
    2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060, 2070, 2080,
    5000, 5010, 5020, 5030, 5040, 5045, 5050, 5060, 5070, 5080,
]

DATA_DIR       = "/app/data"
INCOMING_DIR   = "/media/.downloads"
BACKUP_DIR     = "/media/.backups"
WATCHTOWER_URL = "http://watchtower:8080"
REPO_SLUG      = "tskon-kz/media-server"
REPO_OWNER     = REPO_SLUG.split("/")[0]
BOT_IMAGE      = f"ghcr.io/{REPO_OWNER}/media-server-bot"
BOT_CONTAINER  = "media-server-telegram-bot"
CLOUDFLARED_CONTAINER = "media-server-cloudflared"

# Available upscalers offered to the user. `needs_gpu` ones require a Vulkan
# device (`/dev/dri`) in the upscaler container; without it the worker fails the
# job with a clear error. `cas` is the CPU-safe path (lanczos + FidelityFX CAS
# sharpen); `anime4k` runs the Anime4K neural shaders as a single GPU pass via
# ffmpeg's libplacebo filter — real-time even on an iGPU. The `id` is the
# contract with upscaler/runners.py.
UPSCALERS = [
    {"id": "cas",     "label": "Sharpen (CPU, fast)", "needs_gpu": False},
    {"id": "anime4k", "label": "Anime4K (GPU AI)",    "needs_gpu": True},
]
UPSCALER_IDS = frozenset(u["id"] for u in UPSCALERS)

# How hard to compress the re-encoded output. The `id` is the contract with
# upscaler/runners.py (which maps it to concrete libx264 CRF / VAAPI QP values);
# more levels/settings will be added here later. `balanced` is the default.
COMPRESSION_LEVELS = [
    {"id": "balanced",   "label": "Balanced"},
    {"id": "aggressive", "label": "Smaller file"},
]
COMPRESSION_IDS = frozenset(c["id"] for c in COMPRESSION_LEVELS)

DEFAULT_CATS = [
    {"name": "Movies", "path": "/media/movies", "jf_type": "movies"},
    {"name": "Series", "path": "/media/series", "jf_type": "tvshows"},
]

# qBittorrent 5.x renamed pausedDL/pausedUP -> stoppedDL/stoppedUP. Keep both so
# the bot works across qB 4.x and 5.x.
DONE_STATES = {"pausedUP", "stoppedUP", "uploading", "seeding", "stalledUP", "forcedUP"}

ICONS = {
    "downloading": "⬇️", "forcedDL": "⬇️",
    "stalledDL": "🔄", "metaDL": "🔍",
    "allocating": "💾",
    "checkingDL": "🔎", "checkingResumeData": "🔎", "checkingUP": "🔎",
    "queuedDL": "⏳", "queuedUP": "⏳",
    "uploading": "⬆️", "forcedUP": "⬆️",
    "stalledUP": "🌱", "seeding": "🌱",
    "pausedDL": "⏸", "pausedUP": "✅",
    "stoppedDL": "⏸", "stoppedUP": "✅",
    "moving": "📦", "missingFiles": "⚠️", "error": "❌", "unknown": "❓",
}
