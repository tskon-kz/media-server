import asyncio
import logging
import os
from telegram import BotCommand

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler,
    CommandHandler, MessageHandler, filters,
)
from config import BOT_TOKEN, APP_VERSION, ALLOWED
import store
import handlers as h
import keyboards as kb
from webapp import start_webapp, stop_webapp

log = logging.getLogger(__name__)


async def _post_init(app):
    await app.bot.set_my_commands([
        BotCommand("list",     "Список торрентов"),
        BotCommand("search",   "Поиск раздач через Jackett"),
        BotCommand("status",   "Статус сети"),
        BotCommand("scan",     "Сканировать Jellyfin"),
        BotCommand("settings", "Настройки"),
    ])

    # Report a completed update FIRST — before anything that could fail — so a
    # Mini App startup hiccup can never swallow the success notification. Set
    # when the updater recreated the *previous* container; we're the fresh one.
    if store.get_config("update_pending"):
        store.set_config("update_pending", "")
        try:
            from api import remove_updater
            await asyncio.to_thread(remove_updater)  # retire the ephemeral updater
        except Exception:
            pass
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

    app.add_handler(CommandHandler("start",    h.cmd_start))
    app.add_handler(CommandHandler("list",     h.cmd_list))
    app.add_handler(CommandHandler("search",   h.cmd_search))
    app.add_handler(CommandHandler("status",   h.cmd_status))
    app.add_handler(CommandHandler("scan",     h.cmd_scan))
    app.add_handler(CommandHandler("settings", h.cmd_settings))
    app.add_handler(CallbackQueryHandler(h.on_callback))
    app.add_handler(MessageHandler(filters.Document.FileExtension("torrent"), h.on_torrent_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h.on_message))
    app.job_queue.run_repeating(h.job_check_done,   interval=30,     first=10)
    app.job_queue.run_once(h.job_check_update, when=30)
    app.job_queue.run_repeating(h.job_check_update, interval=6*3600, first=6*3600)
    app.job_queue.run_repeating(h.job_check_webapp_url, interval=60, first=5)

    print(f"Bot started (v{APP_VERSION})")
    app.run_polling()


if __name__ == "__main__":
    main()
