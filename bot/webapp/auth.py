"""Telegram Mini App auth for the `/api/*` surface.

Validates the `initData` blob that Telegram signs with the bot token, extracts
the user id, and checks it against `config.ALLOWED` — the same gate the bot
command handlers use. There is no separate login and no fallback auth.

The one exception is `WEBAPP_DEV_MODE` (env, off in prod): when set, validation
is skipped and requests act as the configured ALLOWED user, so the frontend can
run in a plain browser (Vite dev server) with no Telegram context.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from aiohttp import web

from config import BOT_TOKEN, ALLOWED, WEBAPP_DEV_MODE

# initData is signed at open time and may be reused for the session; reject
# anything older than this to bound replay of a leaked blob.
_MAX_AGE = 24 * 3600


def validate_init_data(init_data: str) -> dict | None:
    """Return the parsed initData (with `user` decoded to a dict) if the HMAC
    signature is valid and fresh, else None.

    Algorithm (Telegram Mini Apps): build a data-check-string of all fields
    except `hash`, sorted by key and joined by newlines as `key=value`; the
    secret key is HMAC-SHA256(key="WebAppData", msg=bot_token); the expected
    hash is HMAC-SHA256(key=secret, msg=data_check_string), hex-encoded.
    """
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if auth_date and time.time() - auth_date > _MAX_AGE:
        return None

    if pairs.get("user"):
        try:
            pairs["user"] = json.loads(pairs["user"])
        except Exception:
            pairs["user"] = None
    return pairs


def _dev_user_id() -> int:
    return next(iter(ALLOWED))


@web.middleware
async def auth_middleware(request: web.Request, handler):
    path = request.path
    # Static SPA and the health probe are public; everything else under /api is gated.
    if not path.startswith("/api/") or path == "/api/health":
        return await handler(request)

    if WEBAPP_DEV_MODE:
        request["user_id"] = _dev_user_id()
        return await handler(request)

    auth = request.headers.get("Authorization", "")
    init_data = auth[4:] if auth.startswith("tma ") else ""
    data = validate_init_data(init_data)
    user = data.get("user") if data else None
    if not user or user.get("id") not in ALLOWED:
        return web.json_response({"error": "unauthorized"}, status=401)

    request["user_id"] = user["id"]
    return await handler(request)
