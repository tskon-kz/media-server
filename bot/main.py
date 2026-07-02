import os
from telegram import BotCommand
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler,
    CommandHandler, MessageHandler, filters,
)
from config import BOT_TOKEN, APP_VERSION, ALLOWED
import store
import handlers as h
import keyboards as kb
from api import remote_version


async def _post_init(app):
    await app.bot.set_my_commands([
        BotCommand("list",     "Список торрентов"),
        BotCommand("status",   "Статус сети"),
        BotCommand("scan",     "Сканировать Jellyfin"),
        BotCommand("settings", "Настройки"),
    ])

    if store.get_config("update_pending"):
        store.set_config("update_pending", "")
        remote = remote_version()
        if remote is None:
            msg = store.t("update_success_nocheck", v=APP_VERSION)
        elif APP_VERSION == remote:
            msg = store.t("update_success", v=APP_VERSION)
        else:
            msg = store.t("update_failed_ver", v=APP_VERSION)
        for uid in ALLOWED:
            try:
                await app.bot.send_message(uid, msg, parse_mode="Markdown")
            except Exception:
                pass

    for job in store.get_pending_rename_jobs():
        if os.path.exists(job["src_path"]):
            filename = os.path.basename(job["src_path"])
            for uid in ALLOWED:
                try:
                    await app.bot.send_message(
                        uid,
                        store.t("rename_failed_parse", filename=filename),
                        parse_mode="Markdown",
                        reply_markup=kb.rename_manual_kb(job["id"]),
                    )
                except Exception:
                    pass


def main():
    store.init()

    proxy_url = store.get_config("proxy_url")
    builder = ApplicationBuilder().token(BOT_TOKEN).post_init(_post_init)
    if proxy_url:
        builder = builder.proxy(proxy_url).get_updates_proxy(proxy_url)
    app = builder.build()

    app.add_handler(CommandHandler("start",    h.cmd_start))
    app.add_handler(CommandHandler("list",     h.cmd_list))
    app.add_handler(CommandHandler("status",   h.cmd_status))
    app.add_handler(CommandHandler("scan",     h.cmd_scan))
    app.add_handler(CommandHandler("settings", h.cmd_settings))
    app.add_handler(CallbackQueryHandler(h.on_callback))
    app.add_handler(MessageHandler(filters.Document.FileExtension("torrent"), h.on_torrent_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h.on_message))
    app.job_queue.run_repeating(h.job_check_done,   interval=30,     first=10)
    app.job_queue.run_once(h.job_check_update, when=30)
    app.job_queue.run_repeating(h.job_check_update, interval=6*3600, first=6*3600)

    print(f"Bot started (v{APP_VERSION})")
    app.run_polling()


if __name__ == "__main__":
    main()
