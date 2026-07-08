import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler,
    CommandHandler, MessageHandler, filters,
)
from config import BOT_TOKEN, APP_VERSION, ALLOWED, current_channel
import store
import handlers as h
from webapp import start_webapp, stop_webapp

log = logging.getLogger(__name__)


async def _post_init(app):
    await app.bot.set_my_commands([])

    # Report a completed update FIRST — before anything that could fail — so a
    # Mini App startup hiccup can never swallow the success notification. The flag
    # was set by the previous container's self_update swap; we're the fresh one.
    # Self-heal the persisted channel tag when running an :edge image: a host-side
    # switch (.env + docker compose up -d) doesn't touch the DB, leaving cold
    # starts / update.sh resolving the wrong tag. Only the edge case is healed —
    # a released image (vX.Y.Z) could be a deliberate rollback pin we must not
    # clobber back to "stable".
    if current_channel() == "edge" and store.get_config("bot_image_tag") != "edge":
        store.set_config("bot_image_tag", "edge")

    if store.get_config("update_pending"):
        store.set_config("update_pending", "")
        msg = store.t("update_success", v=APP_VERSION)
        for uid in ALLOWED:
            try:
                await app.bot.send_message(uid, msg, parse_mode="Markdown")
            except Exception:
                pass

    # Make sure qBittorrent's default save path is under /media (the hotio image
    # defaults to an ephemeral in-container path → free_space -1 + lost downloads).
    try:
        from api import ensure_qb_save_path
        await asyncio.to_thread(ensure_qb_save_path)
    except Exception:
        log.exception("ensure_qb_save_path failed; continuing")

    # Start the Mini App HTTP server in the same event loop. Non-blocking; the
    # cloudflared sidecar reaches it over the compose network. Isolated so a
    # failure here never crashes startup or blocks the notification above.
    try:
        await start_webapp()
    except Exception:
        log.exception("start_webapp failed; continuing without the Mini App")



async def _post_shutdown(app):
    await stop_webapp()


def main():
    store.init()

    proxy_url = store.get_config("proxy_url")
    builder = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
    )
    if proxy_url:
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)
    app = builder.build()

    app.add_handler(CommandHandler("start",  h.cmd_start))
    app.add_handler(CommandHandler("update", h.cmd_update))
    app.add_handler(CallbackQueryHandler(h.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h.on_message))
    app.job_queue.run_repeating(h.job_check_done,   interval=30,     first=10)
    app.job_queue.run_once(h.job_check_update, when=30)
    app.job_queue.run_repeating(h.job_check_update, interval=6*3600, first=6*3600)
    app.job_queue.run_repeating(h.job_check_webapp_url, interval=60, first=5)

    print(f"Bot started (v{APP_VERSION})")
    app.run_polling()


if __name__ == "__main__":
    main()
