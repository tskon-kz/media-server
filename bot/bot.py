import os, json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler,
    CommandHandler, MessageHandler, filters, ContextTypes,
)
import qbittorrentapi
from lang import ru, en

BOT_TOKEN  = os.environ["BOT_TOKEN"]
ALLOWED    = int(os.environ["ALLOWED_USER"])
QB_HOST    = os.environ["QB_HOST"]
PROXY_URL  = os.environ.get("PROXY_URL")  # e.g. socks5://user:pass@host:port
LANG_FILE  = "/app/lang.json"
CREDS_FILE = "/app/creds.json"

QB_USER = os.environ.get("QB_USER", "admin")
QB_PASS = os.environ.get("QB_PASS", "adminadmin")
LANGS   = {"ru": ru.M, "en": en.M}
LANG    = "ru"

ICONS = {
    "downloading": "⬇️", "stalledDL": "⏸", "uploading": "⬆️",
    "seeding": "🌱", "pausedDL": "⏸", "pausedUP": "✅", "error": "❌",
}


def t(key, **kw):
    s = LANGS[LANG][key]
    return s.format(**kw) if kw else s


def set_lang(code):
    global LANG
    LANG = code
    with open(LANG_FILE, "w") as f:
        json.dump({"lang": code}, f)


def save_creds(user, password):
    global QB_USER, QB_PASS
    QB_USER, QB_PASS = user, password
    with open(CREDS_FILE, "w") as f:
        json.dump({"qb_user": user, "qb_pass": password}, f)


def qb():
    c = qbittorrentapi.Client(host=QB_HOST, username=QB_USER, password=QB_PASS)
    c.auth_log_in()
    return c


def auth(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ALLOWED:
            await update.message.reply_text(t("no_access"))
            return
        await func(update, ctx)
    return wrapper


@auth
async def cmd_start(update, ctx):
    await update.message.reply_text(t("start"), parse_mode="Markdown")


@auth
async def cmd_lang(update, ctx):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton("🇬🇧 English",  callback_data="lang:en"),
    ]])
    await update.message.reply_text(t("lang_pick"), reply_markup=kb)


@auth
async def cmd_setpass(update, ctx):
    if not ctx.args:
        await update.message.reply_text(t("setpass_usage"))
        return
    new_pass = ctx.args[0]
    try:
        client = qb()
        client.app_set_preferences({"web_ui_password": new_pass})
        save_creds(QB_USER, new_pass)
        await update.message.delete()
        await update.effective_chat.send_message(t("setpass_ok"))
    except Exception as e:
        await update.message.reply_text(t("setpass_error", e=e))


@auth
async def cmd_list(update, ctx):
    try:
        torrents = qb().torrents_info()
    except Exception as e:
        await update.message.reply_text(t("qb_error", e=e))
        return

    if not torrents:
        await update.message.reply_text(t("empty"))
        return

    for tor in torrents:
        pct = tor.progress * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        text = f"{ICONS.get(tor.state, '❓')} *{tor.name[:40]}*\n`{bar}` {pct:.0f}%\n💾 {tor.size/1024**3:.1f} GB"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(t("del_btn"), callback_data=f"del:{tor.hash}")]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


@auth
async def cmd_status(update, ctx):
    try:
        info = qb().transfer_info()
        msg = t("status_ok", dl=f"{info.dl_info_speed/1024:.0f}", ul=f"{info.up_info_speed/1024:.0f}")
    except Exception:
        msg = t("status_err")
    await update.message.reply_text(msg, parse_mode="Markdown")


@auth
async def on_message(update, ctx):
    text = update.message.text or ""
    if text.startswith("magnet:"):
        try:
            qb().torrents_add(urls=text, save_path="/media/downloads")
            await update.message.reply_text(t("added"))
        except Exception as e:
            await update.message.reply_text(t("add_error", e=e))
    else:
        await update.message.reply_text(t("hint"))


async def on_callback(update, ctx):
    query = update.callback_query
    if update.effective_user.id != ALLOWED:
        await query.answer(t("no_access"))
        return
    await query.answer()

    action, value = query.data.split(":", 1)
    if action == "lang":
        set_lang(value)
        await query.edit_message_text(t("lang_set"))
    elif action == "del":
        try:
            qb().torrents_delete(delete_files=True, torrent_hashes=value)
            await query.edit_message_text(t("deleted"))
        except Exception as e:
            await query.edit_message_text(t("add_error", e=e))


def main():
    global LANG, QB_USER, QB_PASS

    try:
        with open(LANG_FILE) as f:
            LANG = json.load(f).get("lang", "ru")
    except (FileNotFoundError, json.JSONDecodeError):
        set_lang(LANG)

    try:
        with open(CREDS_FILE) as f:
            data = json.load(f)
            QB_USER = data.get("qb_user", QB_USER)
            QB_PASS = data.get("qb_pass", QB_PASS)
    except (FileNotFoundError, json.JSONDecodeError):
        save_creds(QB_USER, QB_PASS)

    builder = ApplicationBuilder().token(BOT_TOKEN)
    if PROXY_URL:
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)
    app = builder.build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("lang",    cmd_lang))
    app.add_handler(CommandHandler("setpass", cmd_setpass))
    app.add_handler(CommandHandler("list",    cmd_list))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
