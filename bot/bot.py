import os, json, urllib.request, urllib.parse
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
PROXY_URL  = os.environ.get("PROXY_URL")
JF_URL     = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096")
JF_KEY     = os.environ.get("JELLYFIN_API_KEY", "")
LANG_FILE  = "/app/lang.json"
CREDS_FILE = "/app/creds.json"
CATS_FILE  = "/app/categories.json"

DEFAULT_CATS = [
    {"name": "🎬 Фильмы",  "path": "/media/movies", "jf_type": "movies"},
    {"name": "📺 Сериалы", "path": "/media/series", "jf_type": "tvshows"},
]

QB_USER = os.environ.get("QB_USER", "admin")
QB_PASS = os.environ.get("QB_PASS", "adminadmin")
LANGS   = {"ru": ru.M, "en": en.M}
LANG    = "ru"

ICONS = {
    "downloading": "⬇️", "stalledDL": "⏸", "uploading": "⬆️",
    "seeding": "🌱", "pausedDL": "⏸", "pausedUP": "✅", "error": "❌",
}


# ── translations ──────────────────────────────────────────────────────────────

def t(key, **kw):
    s = LANGS[LANG][key]
    return s.format(**kw) if kw else s


def set_lang(code):
    global LANG
    LANG = code
    with open(LANG_FILE, "w") as f:
        json.dump({"lang": code}, f)


# ── persistence ───────────────────────────────────────────────────────────────

def save_creds(user, password):
    global QB_USER, QB_PASS
    QB_USER, QB_PASS = user, password
    with open(CREDS_FILE, "w") as f:
        json.dump({"qb_user": user, "qb_pass": password}, f)


def load_cats():
    try:
        with open(CATS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_CATS.copy()


def save_cats(cats):
    with open(CATS_FILE, "w") as f:
        json.dump(cats, f, ensure_ascii=False, indent=2)


# ── jellyfin ──────────────────────────────────────────────────────────────────

def jf(method, path, body=None):
    if not JF_KEY:
        return False
    req = urllib.request.Request(
        f"{JF_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Emby-Token": JF_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def jf_add_library(name, path, lib_type):
    params = urllib.parse.urlencode({"name": name, "collectionType": lib_type, "refreshLibrary": "true"})
    jf("POST", f"/Library/VirtualFolders?{params}", {"LibraryOptions": {"PathInfos": [{"Path": path}]}})


def jf_del_library(name):
    params = urllib.parse.urlencode({"name": name, "refreshLibrary": "true"})
    jf("DELETE", f"/Library/VirtualFolders?{params}")


def jf_scan():
    return jf("POST", "/Library/Refresh")


# ── qbittorrent ───────────────────────────────────────────────────────────────

def qb():
    c = qbittorrentapi.Client(host=QB_HOST, username=QB_USER, password=QB_PASS)
    c.auth_log_in()
    return c


# ── helpers ───────────────────────────────────────────────────────────────────

def auth(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ALLOWED:
            await update.message.reply_text(t("no_access"))
            return
        await func(update, ctx)
    return wrapper


def settings_view(cats):
    lines = "\n".join(f"• {c['name']} → `{c['path']}`" for c in cats) if cats else t("no_cats")
    text = f"{t('settings_title')}\n\n{lines}"
    buttons = [[InlineKeyboardButton(f"🗑 {c['name']}", callback_data=f"delcat:{i}")] for i, c in enumerate(cats)]
    buttons.append([InlineKeyboardButton(t("cat_add_btn"), callback_data="addcat")])
    return text, InlineKeyboardMarkup(buttons)


def type_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 " + t("jf_movies"),  callback_data="cattype:movies"),
         InlineKeyboardButton("📺 " + t("jf_tvshows"), callback_data="cattype:tvshows")],
        [InlineKeyboardButton("🎵 " + t("jf_music"),   callback_data="cattype:music"),
         InlineKeyboardButton("📦 " + t("jf_mixed"),   callback_data="cattype:mixed")],
    ])


# ── commands ──────────────────────────────────────────────────────────────────

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
async def cmd_settings(update, ctx):
    text, kb = settings_view(load_cats())
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


@auth
async def cmd_scan(update, ctx):
    await update.message.reply_text(t("scan_ok") if jf_scan() else t("scan_error"))


@auth
async def cmd_setpass(update, ctx):
    if not ctx.args:
        await update.message.reply_text(t("setpass_usage"))
        return
    try:
        qb().app_set_preferences({"web_ui_password": ctx.args[0]})
        save_creds(QB_USER, ctx.args[0])
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
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(t("del_btn"),  callback_data=f"del:{tor.hash}"),
            InlineKeyboardButton(t("move_btn"), callback_data=f"move:{tor.hash}"),
        ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


@auth
async def cmd_status(update, ctx):
    try:
        info = qb().transfer_info()
        msg = t("status_ok", dl=f"{info.dl_info_speed/1024:.0f}", ul=f"{info.up_info_speed/1024:.0f}")
    except Exception:
        msg = t("status_err")
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── message handler ───────────────────────────────────────────────────────────

@auth
async def on_message(update, ctx):
    text  = update.message.text or ""
    state = ctx.user_data.get("state")

    if state == "await_cat_name":
        ctx.user_data["pending_cat_name"] = text
        ctx.user_data["state"] = "await_cat_path"
        await update.message.reply_text(t("cat_add_path"))
        return

    if state == "await_cat_path":
        ctx.user_data["pending_cat_path"] = text
        ctx.user_data.pop("state", None)
        await update.message.reply_text(t("cat_pick_type"), reply_markup=type_keyboard())
        return

    if text.startswith("magnet:"):
        cats = load_cats()
        if not cats:
            try:
                qb().torrents_add(urls=text, save_path="/media/downloads")
                await update.message.reply_text(t("added"))
            except Exception as e:
                await update.message.reply_text(t("add_error", e=e))
            return
        ctx.user_data["pending_magnet"] = text
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(c["name"], callback_data=f"addmagnet:{i}")] for i, c in enumerate(cats)])
        await update.message.reply_text(t("pick_cat"), reply_markup=kb)
    else:
        await update.message.reply_text(t("hint"))


# ── callback handler ──────────────────────────────────────────────────────────

async def on_callback(update, ctx):
    query = update.callback_query
    if update.effective_user.id != ALLOWED:
        await query.answer(t("no_access"))
        return
    await query.answer()

    action, _, value = query.data.partition(":")

    if action == "lang":
        set_lang(value)
        await query.edit_message_text(t("lang_set"))

    elif action == "del":
        try:
            qb().torrents_delete(delete_files=True, torrent_hashes=value)
            await query.edit_message_text(t("deleted"))
        except Exception as e:
            await query.edit_message_text(t("add_error", e=e))

    elif action == "addmagnet":
        magnet = ctx.user_data.pop("pending_magnet", None)
        if not magnet:
            await query.edit_message_text(t("add_error", e="magnet expired"))
            return
        cat = load_cats()[int(value)]
        try:
            qb().torrents_add(urls=magnet, save_path=cat["path"])
            await query.edit_message_text(t("added"))
        except Exception as e:
            await query.edit_message_text(t("add_error", e=e))

    elif action == "move":
        cats = load_cats()
        if not cats:
            await query.answer(t("no_cats"))
            return
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(c["name"], callback_data=f"moveto:{value}:{i}")] for i, c in enumerate(cats)])
        await query.edit_message_reply_markup(reply_markup=kb)

    elif action == "moveto":
        torrent_hash, _, cat_idx = value.partition(":")
        cat = load_cats()[int(cat_idx)]
        try:
            qb().torrents_set_location(torrent_hashes=torrent_hash, location=cat["path"])
            await query.edit_message_text(t("moved", name=cat["name"]))
        except Exception as e:
            await query.edit_message_text(t("add_error", e=e))

    elif action == "delcat":
        cats = load_cats()
        cat = cats.pop(int(value))
        save_cats(cats)
        jf_del_library(cat["name"])
        text, kb = settings_view(cats)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif action == "cattype":
        name = ctx.user_data.pop("pending_cat_name", "")
        path = ctx.user_data.pop("pending_cat_path", "")
        cats = load_cats()
        cats.append({"name": name, "path": path, "jf_type": value})
        save_cats(cats)
        jf_add_library(name, path, value)
        await query.edit_message_text(t("cat_added"))

    elif query.data == "addcat":
        ctx.user_data["state"] = "await_cat_name"
        await query.edit_message_text(t("cat_add_name"))


# ── main ──────────────────────────────────────────────────────────────────────

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

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("lang",     cmd_lang))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("scan",     cmd_scan))
    app.add_handler(CommandHandler("setpass",  cmd_setpass))
    app.add_handler(CommandHandler("list",     cmd_list))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
