import os, json, re, urllib.request, urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler,
    CommandHandler, MessageHandler, filters, ContextTypes,
)
import qbittorrentapi
from lang import ru, en

BOT_TOKEN  = os.environ["BOT_TOKEN"]
ALLOWED    = frozenset(int(x.strip()) for x in os.environ["ALLOWED_USER"].split(","))
QB_HOST    = os.environ["QB_HOST"]
PROXY_URL  = os.environ.get("PROXY_URL")
JF_URL     = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096")
SERVER_IP  = os.environ.get("SERVER_IP", "")
JF_KEY     = os.environ.get("JELLYFIN_API_KEY", "")
LANG_FILE  = "/app/lang.json"
CREDS_FILE = "/app/creds.json"
CATS_FILE  = "/app/categories.json"

DEFAULT_CATS = [
    {"name": "Movies", "path": "/media/movies", "jf_type": "movies"},
    {"name": "Series", "path": "/media/series", "jf_type": "tvshows"},
]

QB_USER = os.environ.get("QB_USER", "admin")
QB_PASS = os.environ.get("QB_PASS", "adminadmin")
LANGS   = {"ru": ru.M, "en": en.M}
LANG    = "ru"

ICONS = {
    "downloading": "⬇️", "stalledDL": "⏸", "uploading": "⬆️",
    "seeding": "🌱", "pausedDL": "⏸", "pausedUP": "✅", "error": "❌",
}
DONE_STATES = {"pausedUP", "uploading", "seeding", "stalledUP", "forcedUP"}


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


def load_cats():
    try:
        with open(CATS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_CATS.copy()


def save_cats(cats):
    with open(CATS_FILE, "w") as f:
        json.dump(cats, f, ensure_ascii=False, indent=2)


def jf(method, path, body=None):
    if not JF_KEY:
        return None
    req = urllib.request.Request(
        f"{JF_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Emby-Token": JF_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else True
    except Exception:
        return None


def jf_add_library(name, path, lib_type):
    params = urllib.parse.urlencode({"name": name, "collectionType": lib_type, "refreshLibrary": "true"})
    jf("POST", f"/Library/VirtualFolders?{params}", {"LibraryOptions": {"PathInfos": [{"Path": path}]}})


def list_text(torrents):
    lines = []
    for i, tor in enumerate(torrents, 1):
        icon = ICONS.get(tor.state, "❓")
        pct = f" {tor.progress * 100:.0f}%" if tor.progress < 1 else ""
        size = f"{tor.size / 1024**3:.1f} GB"
        lines.append(f"{i}. {icon} {tor.name[:35]}{pct} — {size}")
    return f"*{t('list_title')}* ({len(torrents)})\n\n" + "\n".join(lines)


def list_normal_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t("list_edit_btn"), callback_data="list:edit"),
        InlineKeyboardButton("🔄", callback_data="list:view"),
    ]])


def list_edit_kb(torrents):
    cats = load_cats()
    buttons = []
    for i, tor in enumerate(torrents):
        row = [InlineKeyboardButton(f"🗑 {i + 1}", callback_data=f"del:{tor.hash}")]
        if cats:
            row.append(InlineKeyboardButton(f"📁 {i + 1}", callback_data=f"move:{tor.hash}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="list:view")])
    return InlineKeyboardMarkup(buttons)


def move_cats_kb(torrent_hash):
    cats = load_cats()
    buttons = [[InlineKeyboardButton(c["name"], callback_data=f"moveto:{torrent_hash}:{i}")] for i, c in enumerate(cats)]
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="list:edit")])
    return InlineKeyboardMarkup(buttons)


def qb():
    c = qbittorrentapi.Client(host=QB_HOST, username=QB_USER, password=QB_PASS)
    c.auth_log_in()
    return c


def auth(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ALLOWED:
            await update.message.reply_text(t("no_access"))
            return
        await func(update, ctx)
    return wrapper


async def edit(query, text, kb=None):
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


def settings_kb():
    buttons = [
        [InlineKeyboardButton(t("settings_cats"), callback_data="settings:cats")],
        [InlineKeyboardButton(t("settings_lang"), callback_data="settings:lang"),
         InlineKeyboardButton(t("settings_pass"), callback_data="settings:pass")],
    ]
    if JF_KEY:
        buttons.append([InlineKeyboardButton(t("jf_users_btn"), callback_data="settings:jf_users")])
    if SERVER_IP:
        buttons.append([
            InlineKeyboardButton("qBittorrent ↗", url=f"http://{SERVER_IP}:8080"),
            InlineKeyboardButton("Jellyfin ↗",    url=f"http://{SERVER_IP}:8096"),
        ])
    return InlineKeyboardMarkup(buttons)


def jf_users_view(users):
    body = "\n".join(f"• {u['Name']}" for u in users) if users else t("jf_no_users")
    buttons = [[InlineKeyboardButton(f"🗑 {u['Name']}", callback_data=f"jf_deluser:{u['Id']}")] for u in users]
    buttons += [
        [InlineKeyboardButton(t("jf_add_user_btn"), callback_data="jf_adduser")],
        [InlineKeyboardButton(t("back_btn"), callback_data="settings:menu")],
    ]
    return f"{t('jf_users_title')}\n\n{body}", InlineKeyboardMarkup(buttons)


def cats_view(cats):
    type_label = {"movies": t("jf_movies"), "tvshows": t("jf_tvshows"), "music": t("jf_music"), "mixed": t("jf_mixed")}
    lines = "\n".join(f"• {c['name']} ({type_label.get(c.get('jf_type',''), '?')}) → `{c['path']}`" for c in cats) if cats else t("no_cats")
    buttons = [
        [InlineKeyboardButton(f"✏️ {c['name']}", callback_data=f"editcat:{i}"),
         InlineKeyboardButton("🗑", callback_data=f"delcat:{i}")]
        for i, c in enumerate(cats)
    ]
    buttons += [
        [InlineKeyboardButton(t("cat_add_btn"), callback_data="addcat")],
        [InlineKeyboardButton(t("back_btn"), callback_data="settings:menu")],
    ]
    return f"{t('settings_title')}\n\n{lines}", InlineKeyboardMarkup(buttons)


def type_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 " + t("jf_movies"),  callback_data="cattype:movies"),
         InlineKeyboardButton("📺 " + t("jf_tvshows"), callback_data="cattype:tvshows")],
        [InlineKeyboardButton("🎵 " + t("jf_music"),   callback_data="cattype:music"),
         InlineKeyboardButton("📦 " + t("jf_mixed"),   callback_data="cattype:mixed")],
    ])


@auth
async def cmd_start(update, ctx):
    await update.message.reply_text(t("start"), parse_mode="Markdown")


@auth
async def cmd_scan(update, ctx):
    await update.message.reply_text(t("scan_ok") if jf("POST", "/Library/Refresh") else t("scan_error"))


@auth
async def cmd_settings(update, ctx):
    await update.message.reply_text(t("settings_main"), reply_markup=settings_kb())


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
    await update.message.reply_text(
        list_text(torrents), parse_mode="Markdown", reply_markup=list_normal_kb()
    )


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
    text  = update.message.text or ""
    state = ctx.user_data.get("state")

    if state == "await_new_pass":
        ctx.user_data.pop("state", None)
        try:
            qb().app_set_preferences({"web_ui_password": text})
            save_creds(QB_USER, text)
            await update.message.delete()
            await update.effective_chat.send_message(t("setpass_ok"))
        except Exception as e:
            await update.message.reply_text(t("setpass_error", e=e))
        return

    if state == "await_cat_rename":
        ctx.user_data.pop("state", None)
        idx = ctx.user_data.pop("pending_cat_idx", None)
        if idx is not None:
            cats = load_cats()
            if 0 <= idx < len(cats):
                cats[idx]["name"] = text
                save_cats(cats)
        text_msg, kb = cats_view(load_cats())
        await update.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=kb)
        return

    if state == "await_jf_user_name":
        ctx.user_data.pop("state", None)
        ctx.user_data["pending_jf_user_name"] = text
        ctx.user_data["state"] = "await_jf_user_pass"
        await update.message.reply_text(t("jf_add_user_pass", name=text), parse_mode="Markdown")
        return

    if state == "await_jf_user_pass":
        ctx.user_data.pop("state", None)
        name = ctx.user_data.pop("pending_jf_user_name", "")
        user = jf("POST", "/Users/New", {"Name": name})
        if isinstance(user, dict) and "Id" in user:
            jf("POST", f"/Users/{user['Id']}/Password", {"NewPw": text})
            await update.message.delete()
            await update.effective_chat.send_message(t("jf_user_added", name=name), parse_mode="Markdown")
        else:
            await update.message.reply_text(t("jf_user_error"))
        return

    if state == "await_cat_name":
        ctx.user_data["pending_cat_name"] = text
        ctx.user_data["state"] = "await_cat_path"
        slug = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE).strip().lower().replace(' ', '_')
        suggested = f"/media/{slug}" if slug else "/media/"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(suggested, callback_data=f"catpath:{suggested}")]])
        await update.message.reply_text(t("cat_add_path"), reply_markup=kb)
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


@auth
async def on_torrent_file(update, ctx):
    file = await (await update.message.document.get_file()).download_as_bytearray()
    cats = load_cats()
    if not cats:
        try:
            qb().torrents_add(torrent_files=bytes(file), save_path="/media/downloads")
            await update.message.reply_text(t("added"))
        except Exception as e:
            await update.message.reply_text(t("add_error", e=e))
        return
    ctx.user_data["pending_torrent"] = bytes(file)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(c["name"], callback_data=f"addtorrent:{i}")] for i, c in enumerate(cats)])
    await update.message.reply_text(t("pick_cat"), reply_markup=kb)


async def on_callback(update, ctx):
    query = update.callback_query
    if update.effective_user.id not in ALLOWED:
        await query.answer(t("no_access"))
        return
    await query.answer()

    action, _, value = query.data.partition(":")

    if action == "list":
        try:
            torrents = qb().torrents_info()
        except Exception as e:
            await edit(query, t("qb_error", e=e))
            return
        if not torrents:
            await edit(query, t("empty"))
            return
        if value == "edit":
            await edit(query, list_text(torrents), list_edit_kb(torrents))
        else:
            await edit(query, list_text(torrents), list_normal_kb())

    elif action == "settings":
        if value == "menu":
            await edit(query, t("settings_main"), settings_kb())
        elif value == "cats":
            await edit(query, *cats_view(load_cats()))
        elif value == "lang":
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton("🇬🇧 English",  callback_data="lang:en"),
            ]])
            await edit(query, t("lang_pick"), kb)
        elif value == "pass":
            ctx.user_data["state"] = "await_new_pass"
            await edit(query, t("setpass_prompt"))
        elif value == "jf_users":
            await edit(query, *jf_users_view(jf("GET", "/Users") or []))

    elif action == "lang":
        set_lang(value)
        await edit(query, t("settings_main"), settings_kb())

    elif action == "del":
        try:
            qb().torrents_delete(delete_files=True, torrent_hashes=value)
        except Exception as e:
            await edit(query, t("add_error", e=e))
            return
        try:
            torrents = qb().torrents_info()
        except Exception as e:
            await edit(query, t("qb_error", e=e))
            return
        if not torrents:
            await edit(query, t("empty"))
            return
        await edit(query, list_text(torrents), list_edit_kb(torrents))

    elif action == "addmagnet":
        magnet = ctx.user_data.pop("pending_magnet", None)
        if not magnet:
            await edit(query, t("add_error", e="magnet expired"))
            return
        cat = load_cats()[int(value)]
        try:
            qb().torrents_add(urls=magnet, save_path=cat["path"])
            await edit(query, t("added"))
        except Exception as e:
            await edit(query, t("add_error", e=e))

    elif action == "addtorrent":
        torrent = ctx.user_data.pop("pending_torrent", None)
        if not torrent:
            await edit(query, t("add_error", e="file expired"))
            return
        cat = load_cats()[int(value)]
        try:
            qb().torrents_add(torrent_files=torrent, save_path=cat["path"])
            await edit(query, t("added"))
        except Exception as e:
            await edit(query, t("add_error", e=e))

    elif action == "move":
        cats = load_cats()
        if not cats:
            await query.answer(t("no_cats"))
            return
        await query.edit_message_reply_markup(reply_markup=move_cats_kb(value))

    elif action == "moveto":
        torrent_hash, _, cat_idx = value.partition(":")
        cat = load_cats()[int(cat_idx)]
        try:
            qb().torrents_set_location(torrent_hashes=torrent_hash, location=cat["path"])
        except Exception as e:
            await edit(query, t("add_error", e=e))
            return
        try:
            torrents = qb().torrents_info()
        except Exception as e:
            await edit(query, t("qb_error", e=e))
            return
        if not torrents:
            await edit(query, t("empty"))
            return
        await edit(query, list_text(torrents), list_normal_kb())

    elif action == "editcat":
        ctx.user_data["pending_cat_idx"] = int(value)
        ctx.user_data["state"] = "await_cat_rename"
        await edit(query, t("cat_rename_prompt"))

    elif action == "delcat":
        cats = load_cats()
        cat = cats.pop(int(value))
        save_cats(cats)
        params = urllib.parse.urlencode({"name": cat["name"], "refreshLibrary": "true"})
        jf("DELETE", f"/Library/VirtualFolders?{params}")
        await edit(query, *cats_view(cats))

    elif action == "catpath":
        ctx.user_data["pending_cat_path"] = value
        ctx.user_data.pop("state", None)
        await edit(query, t("cat_pick_type"), type_keyboard())

    elif action == "cattype":
        name = ctx.user_data.pop("pending_cat_name", "")
        path = ctx.user_data.pop("pending_cat_path", "")
        if path:
            os.makedirs(path, exist_ok=True)
        cats = load_cats()
        cats.append({"name": name, "path": path, "jf_type": value})
        save_cats(cats)
        jf_add_library(name, path, value)
        await edit(query, *cats_view(cats))

    elif action == "jf_deluser":
        if jf("DELETE", f"/Users/{value}") is not None:
            await edit(query, *jf_users_view(jf("GET", "/Users") or []))
        else:
            await query.answer(t("jf_user_error"))

    elif action == "jf_adduser":
        ctx.user_data["state"] = "await_jf_user_name"
        await edit(query, t("jf_add_user_name"))

    elif query.data == "addcat":
        ctx.user_data["state"] = "await_cat_name"
        await edit(query, t("cat_add_name"))


async def check_done(ctx: ContextTypes.DEFAULT_TYPE):
    known = ctx.bot_data.setdefault("states", {})
    if known and all(s in DONE_STATES for s in known.values()):
        return
    try:
        torrents = qb().torrents_info()
    except Exception:
        return
    for tor in torrents:
        prev = known.get(tor.hash)
        if prev and prev not in DONE_STATES and tor.state in DONE_STATES:
            for uid in ALLOWED:
                await ctx.bot.send_message(uid, t("download_done", name=tor.name))
            jf("POST", "/Library/Refresh")
        known[tor.hash] = tor.state
    for h in list(known):
        if h not in {tor.hash for tor in torrents}:
            del known[h]


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

    async def post_init(application):
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("list",     "Список торрентов"),
            BotCommand("status",   "Статус сети"),
            BotCommand("scan",     "Сканировать Jellyfin"),
            BotCommand("settings", "Настройки"),
        ])

    builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init)
    if PROXY_URL:
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)
    app = builder.build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("list",     cmd_list))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("scan",     cmd_scan))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.Document.FileExtension("torrent"), on_torrent_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.job_queue.run_repeating(check_done, interval=30, first=10)
    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
