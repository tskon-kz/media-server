import os

BOT_TOKEN        = os.environ["BOT_TOKEN"]
ALLOWED          = frozenset(int(x) for x in os.environ["ALLOWED_USER"].split(","))
QB_HOST          = os.environ["QB_HOST"]
JF_URL           = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096")
JF_PORT          = os.environ.get("JELLYFIN_PORT", "8096")
QB_PORT          = os.environ.get("QB_PORT", "8080")
JACKETT_URL      = os.environ.get("JACKETT_URL", "http://jackett:9117")
JACKETT_PORT     = os.environ.get("JACKETT_PORT", "9117")
APP_VERSION      = os.environ.get("APP_VERSION", "dev")
WATCHTOWER_TOKEN = os.environ.get("WATCHTOWER_TOKEN", "")

SEARCH_RESULTS_LIMIT = 30
SEARCH_PAGE_SIZE     = 5

# Torznab categories sent to Jackett so search returns only video content:
# Movies (2000–2080) and TV (5000–5080).
SEARCH_CATEGORIES = [
    2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060, 2070, 2080,
    5000, 5010, 5020, 5030, 5040, 5045, 5050, 5060, 5070, 5080,
]

DATA_DIR       = "/app/data"
INCOMING_DIR   = "/media/.downloads"
WATCHTOWER_URL = "http://watchtower:8080"
REPO_SLUG      = "tskon-kz/media-server"
REPO_OWNER     = REPO_SLUG.split("/")[0]
BOT_IMAGE      = f"ghcr.io/{REPO_OWNER}/media-server-bot"
BOT_CONTAINER  = "media-server-telegram-bot"

DEFAULT_CATS = [
    {"name": "Movies", "path": "/media/movies", "jf_type": "movies"},
    {"name": "Series", "path": "/media/series", "jf_type": "tvshows"},
]

DONE_STATES = {"pausedUP", "uploading", "seeding", "stalledUP", "forcedUP"}

ICONS = {
    "downloading": "⬇️", "forcedDL": "⬇️",
    "stalledDL": "🔄", "metaDL": "🔍",
    "allocating": "💾",
    "checkingDL": "🔎", "checkingResumeData": "🔎", "checkingUP": "🔎",
    "queuedDL": "⏳", "queuedUP": "⏳",
    "uploading": "⬆️", "forcedUP": "⬆️",
    "stalledUP": "🌱", "seeding": "🌱",
    "pausedDL": "⏸", "pausedUP": "✅",
    "moving": "📦", "missingFiles": "⚠️", "error": "❌", "unknown": "❓",
}
