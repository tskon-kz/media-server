"""Internal HTTP server for the Telegram Mini App.

Runs inside the same asyncio event loop as the PTB bot (started from
`main._post_init`). It serves the React SPA as static files under `/` and the
JSON API under `/api/*`. It is never published to the host — only the
`cloudflared` sidecar reaches it over the internal compose network, which is
what gives it a public HTTPS `trycloudflare.com` URL.

The SPA is built at Docker image build time into `/app/webapp-dist` (see
`bot/Dockerfile`). When that directory is absent (e.g. running the bot outside
Docker for local dev, where the frontend runs under Vite instead) a small
placeholder is served at `/`.
"""
import logging
from pathlib import Path

from aiohttp import web

from config import WEBAPP_PORT
from .auth import auth_middleware
from .routes import routes

log = logging.getLogger(__name__)

# /app/webapp/server.py -> /app/webapp-dist (built React SPA).
_DIST = Path(__file__).resolve().parent.parent / "webapp-dist"

_PLACEHOLDER = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Media Server</title></head>
<body style="font-family:system-ui,sans-serif;padding:2rem;text-align:center">
<h1>🎬 Media Server</h1>
<p>The Mini App is being set up. Check back soon.</p>
</body></html>"""

# Keep a module-level handle so post_shutdown can tear the server down cleanly.
_runner: web.AppRunner | None = None


async def _placeholder(_request: web.Request) -> web.Response:
    return web.Response(text=_PLACEHOLDER, content_type="text/html")


async def _spa(request: web.Request) -> web.Response:
    """Serve a built asset if it exists, otherwise index.html (SPA fallback).

    Registered after the API routes, so `/api/*` always resolves first. The
    resolved path is confined to the dist dir to block traversal.
    """
    rel = request.match_info.get("tail", "")
    if rel:
        candidate = (_DIST / rel).resolve()
        if candidate.is_file() and str(candidate).startswith(str(_DIST)):
            return web.FileResponse(candidate)
    return web.FileResponse(_DIST / "index.html")


def create_app() -> web.Application:
    app = web.Application(middlewares=[auth_middleware])
    app.add_routes(routes)
    if _DIST.is_dir():
        app.router.add_get("/", _spa)
        app.router.add_get("/{tail:.*}", _spa)
    else:
        log.warning("webapp-dist not found at %s — serving placeholder", _DIST)
        app.router.add_get("/", _placeholder)
    return app


async def start_webapp() -> None:
    """Bind the aiohttp server to 0.0.0.0:WEBAPP_PORT on the running loop.

    Non-blocking: schedules the server on the current event loop and returns.
    PTB's `run_polling` keeps the loop alive, so the server stays up alongside
    the bot.
    """
    global _runner
    if _runner is not None:
        return
    _runner = web.AppRunner(create_app())
    await _runner.setup()
    site = web.TCPSite(_runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    log.info("Web App server listening on 0.0.0.0:%s", WEBAPP_PORT)


async def stop_webapp() -> None:
    global _runner
    if _runner is not None:
        await _runner.cleanup()
        _runner = None
