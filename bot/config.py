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

SEARCH_RESULTS_LIMIT = 10

DATA_DIR       = "/app/data"
INCOMING_DIR   = "/media/.downloads"
WATCHTOWER_URL = "http://watchtower:8080"
REPO_SLUG      = "tskon-kz/media-server"

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
