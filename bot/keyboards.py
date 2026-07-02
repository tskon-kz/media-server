import re
from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from guessit import guessit
from config import JF_PORT, QB_PORT, ICONS
import store
from store import t, load_cats

PAGE_SIZE = 10

_SEASON_RE = re.compile(r'[Сс]езон\s*(\d+)|[Ss]eason\s*(\d+)|[Ss](\d{1,2})(?=[\s.\-_]|$)')


def short_name(name: str) -> str:
    if " / " in name:
        title = re.sub(r'^\[.+?\]\s*', '', name.split(" / ")[0]).strip()
        m = _SEASON_RE.search(name)
        if m:
            s = int(next(g for g in m.groups() if g is not None))
            return f"{title[:25]} S{s:02d}"
        return title

    guess = guessit(name)
    title = str(guess.get("title", "")).strip()
    if not title:
        return name
    season = guess.get("season")
    if season is not None:
        return f"{title} S{int(season):02d}"
    year = guess.get("year")
    if year:
        return f"{title} ({year})"
    return title


# --- Keyboards ---

def main_menu_kb():
    server_ip = store.get_config("server_ip")
    jf_key    = store.get_config("jellyfin_api_key")
    buttons = [
        [InlineKeyboardButton(t("settings_cats"), callback_data="settings:cats")],
        [InlineKeyboardButton(t("settings_lang"), callback_data="settings:lang")],
        [InlineKeyboardButton(t("settings_qb"),   callback_data="settings:qb")],
    ]
    if jf_key:
        buttons.append([InlineKeyboardButton(t("jf_users_btn"), callback_data="settings:jf_users")])
    buttons.append([InlineKeyboardButton(t("settings_update"),     callback_data="settings:update")])
    buttons.append([InlineKeyboardButton(t("settings_media_mgmt"), callback_data="settings:media")])
    if server_ip:
        buttons.append([
            InlineKeyboardButton("qBittorrent", url=f"http://{server_ip}:{QB_PORT}"),
            InlineKeyboardButton("Jellyfin",    url=f"http://{server_ip}:{JF_PORT}"),
        ])
    return InlineKeyboardMarkup(buttons)


def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton("🇬🇧 English",  callback_data="lang:en"),
    ]])


def list_kb(page=0, total=0):
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    buttons = []
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("←", callback_data=f"list:page:{page-1}"))
        nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop:"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("→", callback_data=f"list:page:{page+1}"))
        buttons.append(nav_row)
    buttons.append([
        InlineKeyboardButton(t("list_manage_btn"),  callback_data=f"list:manage:{page}"),
        InlineKeyboardButton(t("list_refresh_btn"), callback_data="list:view"),
    ])
    return InlineKeyboardMarkup(buttons)


def torrent_action_kb(tor_hash, has_move=False, has_reparse=False):
    buttons = [[InlineKeyboardButton(t("del_btn"), callback_data=f"del:{tor_hash}")]]
    row2 = []
    if has_move:
        row2.append(InlineKeyboardButton(t("move_btn"), callback_data=f"move:{tor_hash}"))
    if has_reparse:
        row2.append(InlineKeyboardButton(t("manage_structure_btn"), callback_data=f"structure:{tor_hash}"))
    if row2:
        buttons.append(row2)
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="list:view")])
    return InlineKeyboardMarkup(buttons)


def move_cats_kb(torrent_hash):
    cats    = load_cats()
    buttons = [[InlineKeyboardButton(c["name"], callback_data=f"moveto:{torrent_hash}:{i}")] for i, c in enumerate(cats)]
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data=f"tor_action:{torrent_hash}")])
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


def qb_settings_kb(is_perm: bool = True, has_auth_error: bool = False):
    buttons = []
    if has_auth_error:
        buttons.append([InlineKeyboardButton(t("qb_fix_pass_btn"), callback_data="qb:change_pass")])
    if not is_perm:
        buttons.append([InlineKeyboardButton(t("qb_fetch_temp_btn"), callback_data="qb:fetch_temp")])
    buttons.append([InlineKeyboardButton(t("qb_change_pass_btn"), callback_data="qb:change_pass")])
    buttons.append([InlineKeyboardButton(t("qb_restart_btn"),     callback_data="qb:restart")])
    buttons.append([InlineKeyboardButton(t("back_btn"),            callback_data="settings:menu")])
    return InlineKeyboardMarkup(buttons)


def update_kb(has_update):
    label = "update_btn" if has_update else "update_force_btn"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(label), callback_data="update:start")],
        [InlineKeyboardButton(t("back_btn"), callback_data="settings:menu")],
    ])


def rename_reset_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("rename_reset_confirm_btn"), callback_data="rename_reset:confirm")],
        [InlineKeyboardButton(t("back_btn"),                  callback_data="settings:menu")],
    ])


def structure_menu_kb(tor_hash: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("parse_pretty_btn"), callback_data=f"struct_pretty:{tor_hash}")],
        [InlineKeyboardButton(t("flat_btn"),         callback_data=f"struct_flat:{tor_hash}")],
        [InlineKeyboardButton(t("del_links_btn"),    callback_data=f"struct_del:{tor_hash}")],
        [InlineKeyboardButton(t("back_btn"),         callback_data=f"tor_action:{tor_hash}")],
    ])


def global_structure_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("parse_pretty_btn"), callback_data="media:pretty")],
        [InlineKeyboardButton(t("flat_btn"),         callback_data="media:flat")],
        [InlineKeyboardButton(t("del_links_btn"),    callback_data="media:del")],
        [InlineKeyboardButton(t("back_btn"),         callback_data="settings:menu")],
    ])


def del_links_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("del_links_confirm_btn"), callback_data="media:del_confirm")],
        [InlineKeyboardButton(t("back_btn"),               callback_data="settings:media")],
    ])


def rename_torrent_summary_kb(tor_hash: str, linked: int, pending: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("rename_tor_keep_flat_btn"), callback_data=f"rename_tor:keep_flat:{tor_hash}")],
        [
            InlineKeyboardButton(t("rename_tor_manual_btn"), callback_data=f"rename_tor:manual:{tor_hash}"),
            InlineKeyboardButton(t("rename_tor_skip_btn"),   callback_data=f"rename_tor:skip:{tor_hash}"),
        ],
    ])


def rename_manual_kb(job_id: int, pending_total: int = 1):
    rows = [[
        InlineKeyboardButton(t("rename_manual_btn"),    callback_data=f"rename:manual:{job_id}"),
        InlineKeyboardButton(t("rename_keep_flat_btn"), callback_data=f"rename:flat:{job_id}"),
        InlineKeyboardButton(t("rename_skip_btn"),      callback_data=f"rename:skip:{job_id}"),
    ]]
    if pending_total > 1:
        rows.append([
            InlineKeyboardButton(t("rename_flatall_btn"), callback_data="rename:flatall:"),
            InlineKeyboardButton(t("rename_skipall_btn"), callback_data="rename:skipall:"),
        ])
    return InlineKeyboardMarkup(rows)


# --- View helpers (text + keyboard) ---

def cats_view(cats):
    lines = "\n".join(f"• {c['name']} → `{c['path'].removeprefix('/media/')}`" for c in cats) if cats else t("no_cats")
    return f"{t('settings_title')}\n\n{lines}", cats_menu_kb(cats)


def jf_users_view(users):
    body = "\n".join(f"• {u['Name']}" for u in users) if users else t("jf_no_users")
    return f"{t('jf_users_title')}\n\n{body}", jf_users_kb(users)


def qb_view():
    user, pass_ = store.get_creds()
    is_perm = bool(store.get_config("qb_pass_is_perm"))
    qb_status = store.get_qb_status()
    status_text = t(f"qb_conn_{qb_status}")
    has_auth_error = qb_status == "error"
    if is_perm:
        text = t("qb_settings_title", user=user, pass_=pass_, status=status_text)
    else:
        text = t("qb_settings_title_temp", user=user, status=status_text)
    return text, qb_settings_kb(is_perm, has_auth_error)


def update_view(local, remote):
    if remote is None:
        return t("update_check_fail", v=local), update_kb(False)
    if remote == local:
        return t("update_up_to_date", v=local), update_kb(False)
    return t("update_available", local=local, remote=remote), update_kb(True)


def list_text(torrents, page=0):
    start = page * PAGE_SIZE
    page_torrents = torrents[start:start + PAGE_SIZE]
    lines = []
    for i, tor in enumerate(page_torrents, start + 1):
        icon = ICONS.get(tor.state, "❓")
        pct  = f" {tor.progress*100:.0f}%" if tor.progress < 1 else ""
        size = f"{tor.size/1024**3:.1f} GB"
        name = escape(short_name(tor.name))
        lines.append(f"{i}. {icon} {name}{pct} — {size}")
    return f"<b>{escape(t('list_title'))}</b> ({len(torrents)})\n\n" + "\n".join(lines)
