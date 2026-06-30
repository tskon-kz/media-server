from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import SERVER_IP, JF_PORT, QB_PORT, JF_KEY, ICONS
from store import t, load_cats


# --- Keyboards ---

def main_menu_kb():
    buttons = [
        [InlineKeyboardButton(t("settings_cats"), callback_data="settings:cats")],
        [InlineKeyboardButton(t("settings_lang"), callback_data="settings:lang"),
         InlineKeyboardButton(t("settings_pass"), callback_data="settings:pass")],
    ]
    if JF_KEY:
        buttons.append([InlineKeyboardButton(t("jf_users_btn"), callback_data="settings:jf_users")])
    buttons.append([InlineKeyboardButton(t("settings_update"), callback_data="settings:update")])
    if SERVER_IP:
        buttons.append([
            InlineKeyboardButton("qBittorrent ↗", url=f"http://{SERVER_IP}:{QB_PORT}"),
            InlineKeyboardButton("Jellyfin ↗",    url=f"http://{SERVER_IP}:{JF_PORT}"),
        ])
    return InlineKeyboardMarkup(buttons)


def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton("🇬🇧 English",  callback_data="lang:en"),
    ]])


def list_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t("list_edit_btn"),    callback_data="list:edit"),
        InlineKeyboardButton(t("list_refresh_btn"), callback_data="list:view"),
    ]])


def list_edit_kb(torrents):
    cats    = load_cats()
    buttons = []
    for i, tor in enumerate(torrents):
        row = [InlineKeyboardButton(f"🗑 {i+1}", callback_data=f"del:{tor.hash}")]
        if cats:
            row.append(InlineKeyboardButton(f"📁 {i+1}", callback_data=f"move:{tor.hash}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="list:view")])
    return InlineKeyboardMarkup(buttons)


def move_cats_kb(torrent_hash):
    cats    = load_cats()
    buttons = [[InlineKeyboardButton(c["name"], callback_data=f"moveto:{torrent_hash}:{i}")] for i, c in enumerate(cats)]
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="list:edit")])
    return InlineKeyboardMarkup(buttons)


def cats_pick_kb(cats, action):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(c["name"], callback_data=f"{action}:{i}")]
        for i, c in enumerate(cats)
    ])


def cats_menu_kb(cats):
    type_label = {
        "movies": t("jf_movies"), "tvshows": t("jf_tvshows"),
        "music":  t("jf_music"),  "mixed":   t("jf_mixed"),
    }
    buttons = [
        [InlineKeyboardButton(f"✏️ {c['name']} · {type_label.get(c.get('jf_type', ''), '?')}", callback_data=f"editcat:{i}"),
         InlineKeyboardButton("🗑", callback_data=f"delcat:{i}")]
        for i, c in enumerate(cats)
    ]
    buttons += [
        [InlineKeyboardButton(t("cat_add_btn"), callback_data="addcat")],
        [InlineKeyboardButton(t("back_btn"),    callback_data="settings:menu")],
    ]
    return InlineKeyboardMarkup(buttons)


def cat_type_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 " + t("jf_movies"),  callback_data="cattype:movies"),
         InlineKeyboardButton("📺 " + t("jf_tvshows"), callback_data="cattype:tvshows")],
        [InlineKeyboardButton("🎵 " + t("jf_music"),   callback_data="cattype:music"),
         InlineKeyboardButton("📦 " + t("jf_mixed"),   callback_data="cattype:mixed")],
    ])


def jf_users_kb(users):
    buttons = [[InlineKeyboardButton(f"🗑 {u['Name']}", callback_data=f"jf_deluser:{u['Id']}")] for u in users]
    buttons += [
        [InlineKeyboardButton(t("jf_add_user_btn"), callback_data="jf_adduser")],
        [InlineKeyboardButton(t("back_btn"),         callback_data="settings:menu")],
    ]
    return InlineKeyboardMarkup(buttons)


def update_kb(has_update):
    buttons = []
    if has_update:
        buttons.append([InlineKeyboardButton(t("update_btn"), callback_data="update:start")])
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="settings:menu")])
    return InlineKeyboardMarkup(buttons)


# --- View helpers (text + keyboard) ---

def cats_view(cats):
    lines = "\n".join(f"• {c['name']} → `{c['path'].removeprefix('/media/')}`" for c in cats) if cats else t("no_cats")
    return f"{t('settings_title')}\n\n{lines}", cats_menu_kb(cats)


def jf_users_view(users):
    body = "\n".join(f"• {u['Name']}" for u in users) if users else t("jf_no_users")
    return f"{t('jf_users_title')}\n\n{body}", jf_users_kb(users)


def update_view(local, remote):
    if remote is None:
        return t("update_check_fail", v=local), update_kb(False)
    if remote == local:
        return t("update_up_to_date", v=local), update_kb(False)
    return t("update_available", local=local, remote=remote), update_kb(True)


def list_text(torrents):
    lines = []
    for i, tor in enumerate(torrents, 1):
        icon = ICONS.get(tor.state, "❓")
        pct  = f" {tor.progress*100:.0f}%" if tor.progress < 1 else ""
        size = f"{tor.size/1024**3:.1f} GB"
        name = escape(tor.name[:35])
        lines.append(f"{i}. {icon} {name}{pct} — {size}")
    return f"<b>{escape(t('list_title'))}</b> ({len(torrents)})\n\n" + "\n".join(lines)
