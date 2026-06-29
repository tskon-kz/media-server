import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler,
    CommandHandler, filters, ContextTypes
)
import qbittorrentapi

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED = int(os.environ["ALLOWED_USER"])
QB_HOST = os.environ["QB_HOST"]
QB_USER = os.environ.get("QB_USER", "admin")
QB_PASS = os.environ.get("QB_PASS", "adminadmin")


def get_qb():
    c = qbittorrentapi.Client(host=QB_HOST, username=QB_USER, password=QB_PASS)
    c.auth_log_in()
    return c


def auth(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ALLOWED:
            await update.message.reply_text("⛔ Нет доступа")
            return
        await func(update, ctx)
    return wrapper


@auth
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Медиасервер*\n\n"
        "Отправь magnet-ссылку для загрузки\n\n"
        "Команды:\n"
        "/list — список торрентов\n"
        "/status — состояние серверов",
        parse_mode="Markdown"
    )


@auth
async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        torrents = get_qb().torrents_info()
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка подключения к qBittorrent: {e}")
        return

    if not torrents:
        await update.message.reply_text("📭 Список торрентов пуст")
        return

    for t in torrents:
        state_icon = {
            "downloading": "⬇️", "stalledDL": "⏸", "uploading": "⬆️",
            "seeding": "🌱", "pausedDL": "⏸", "pausedUP": "✅",
            "error": "❌",
        }.get(t.state, "❓")

        progress = t.progress * 100
        bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
        size_gb = t.size / 1024**3

        text = (
            f"{state_icon} *{t.name[:40]}*\n"
            f"`{bar}` {progress:.0f}%\n"
            f"💾 {size_gb:.1f} GB"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{t.hash}")
        ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


@auth
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qb = get_qb()
        info = qb.transfer_info()
        msg = (
            "📊 *Статус серверов*\n\n"
            f"qBittorrent: ✅\n"
            f"⬇️ {info.dl_info_speed / 1024:.0f} KB/s\n"
            f"⬆️ {info.up_info_speed / 1024:.0f} KB/s"
        )
    except Exception:
        msg = "qBittorrent: ❌ недоступен"

    await update.message.reply_text(msg, parse_mode="Markdown")


@auth
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    if text.startswith("magnet:"):
        try:
            get_qb().torrents_add(urls=text, save_path="/media/downloads")
            await update.message.reply_text("✅ Торрент добавлен в очередь")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    else:
        await update.message.reply_text(
            "Отправь magnet-ссылку или используй /list /status"
        )


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ALLOWED:
        await query.answer("⛔ Нет доступа")
        return

    await query.answer()
    data = query.data

    if data.startswith("delete:"):
        torrent_hash = data.split(":")[1]
        try:
            get_qb().torrents_delete(delete_files=True, torrent_hashes=torrent_hash)
            await query.edit_message_text("🗑 Торрент и файлы удалены")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
