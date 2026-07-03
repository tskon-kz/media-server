import re
from functools import lru_cache
from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from guessit import guessit
from config import JF_PORT, QB_PORT, JACKETT_PORT, ICONS, SEARCH_PAGE_SIZE
import store
from store import t, load_cats
from api import jackett_has_password, jackett_get_api_key

PAGE_SIZE = 10

_SEASON_RE = re.compile(r'[Сс]езон\s*(\d+)|[Ss]eason\s*(\d+)|[Ss](\d{1,2})(?=[\s.\-_]|$)')


@lru_cache(maxsize=512)
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
    rename_mode = store.get_config("rename_mode", "flat")
    # 2-column grid, grouped by meaning: content (categories/library),
    # system (language/update), services (qBittorrent/Jackett).
    buttons = [
        [InlineKeyboardButton(t("settings_cats"),       callback_data="settings:cats"),
         InlineKeyboardButton(t("settings_media_mgmt"), callback_data="settings:media")],
        [InlineKeyboardButton(t("settings_lang"),       callback_data="settings:lang"),
         InlineKeyboardButton(t("settings_update"),     callback_data="settings:update")],
        [InlineKeyboardButton(t("settings_qb"),         callback_data="settings:qb"),
         InlineKeyboardButton(t("settings_jackett"),    callback_data="settings:jackett")],
    ]
    if jf_key:
        buttons.append([InlineKeyboardButton(t("jf_users_btn"), callback_data="settings:jf_users")])
    mode_key = "rename_mode_flat_btn" if rename_mode == "flat" else "rename_mode_pretty_btn"
    buttons.append([InlineKeyboardButton(t(mode_key), callback_data="toggle_rename_mode")])
    if server_ip:
        buttons.append([
            InlineKeyboardButton("qBittorrent", url=f"http://{server_ip}:{QB_PORT}"),
            InlineKeyboardButton("Jellyfin",    url=f"http://{server_ip}:{JF_PORT}"),
            InlineKeyboardButton("Jackett",     url=f"http://{server_ip}:{JACKETT_PORT}"),
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
    buttons.append([
        InlineKeyboardButton(t("search_btn"), url="https://jac-red.ru"),
        InlineKeyboardButton(t("search_jackett_btn"), callback_data="list:search"),
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


def del_torrent_confirm_kb(tor_hash: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("del_confirm_btn"), callback_data=f"del_confirm:{tor_hash}")],
        [InlineKeyboardButton(t("back_btn"),         callback_data=f"tor_action:{tor_hash}")],
    ])


def move_cats_kb(torrent_hash):
    cats    = load_cats()
    buttons = [[InlineKeyboardButton(c["name"], callback_data=f"moveto:{torrent_hash}:{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data=f"tor_action:{torrent_hash}")])
    return InlineKeyboardMarkup(buttons)


def cats_pick_kb(cats, action):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(c["name"], callback_data=f"{action}:{c['id']}")]
        for c in cats
    ])


def cats_menu_kb(cats):
    type_label = {
        "movies": t("jf_movies"), "tvshows": t("jf_tvshows"),
        "music":  t("jf_music"),  "mixed":   t("jf_mixed"),
    }
    buttons = [
        [InlineKeyboardButton(f"✏️ {c['name']} · {type_label.get(c.get('jf_type', ''), '?')}", callback_data=f"editcat:{c['id']}"),
         InlineKeyboardButton("🗑", callback_data=f"delcat:{c['id']}")]
        for c in cats
    ]
    buttons += [
        [InlineKeyboardButton(t("cat_add_btn"), callback_data="addcat")],
        [InlineKeyboardButton(t("back_btn"),    callback_data="settings:menu")],
    ]
    return InlineKeyboardMarkup(buttons)


def delcat_confirm_kb(cat_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("delcat_confirm_btn"), callback_data=f"delcat_confirm:{cat_id}")],
        [InlineKeyboardButton(t("back_btn"),            callback_data="settings:cats")],
    ])


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
        text = t("qb_settings_title", user=escape(user), pass_=escape(pass_), status=status_text)
    else:
        text = t("qb_settings_title_temp", user=escape(user), status=status_text)
    return text, qb_settings_kb(is_perm, has_auth_error)


def update_view(local, remote):
    if remote is None:
        return t("update_check_fail", v=local), update_kb(False)
    if remote == local:
        return t("update_up_to_date", v=local), update_kb(False)
    return t("update_available", local=local, remote=remote), update_kb(True)


def jackett_settings_kb(has_password: bool = False):
    buttons = [
        [InlineKeyboardButton(t("jackett_change_pass_btn"), callback_data="jackett:change_pass")],
    ]
    if has_password:
        buttons.append([InlineKeyboardButton(t("jackett_remove_pass_btn"), callback_data="jackett:remove_pass")])
    buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="settings:menu")])
    return InlineKeyboardMarkup(buttons)


def _search_size(b: int) -> str:
    if b >= 1024 ** 3:
        return f"{b / 1024 ** 3:.1f} GB"
    if b >= 1024 ** 2:
        return f"{b / 1024 ** 2:.0f} MB"
    return f"{b / 1024:.0f} KB"


_SEARCH_DIVIDER = "\n" + "─" * 16 + "\n"


def _search_page(results: list[dict], page: int) -> tuple[int, int, int]:
    total_pages = max(1, (len(results) + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * SEARCH_PAGE_SIZE
    return page, total_pages, start


def search_results_text(query: str, results: list[dict], page: int = 0) -> str:
    # Rendered as the message body (HTML) so the title can wrap freely across
    # lines — inline-button labels are single-line and get truncated.
    page, total_pages, start = _search_page(results, page)
    header = t("search_results_title", q=escape(query), n=len(results),
               page=page + 1, pages=total_pages)
    entries = []
    for offset, r in enumerate(results[start:start + SEARCH_PAGE_SIZE]):
        info = t(
            "search_result_info",
            seeders=r.get("seeders", 0),
            size=_search_size(r.get("size", 0)),
            tracker=escape(r.get("tracker") or "?"),
            date=(r.get("date") or "")[:10] or "?",
        )
        # Blank line between title and stats so each result reads as a block.
        entries.append(f"<b>{start + offset + 1}.</b> {escape(r['title'])}\n\n{info}")
    return header + "\n\n" + _SEARCH_DIVIDER.join(entries)


def search_results_kb(results: list[dict], page: int = 0):
    page, total_pages, start = _search_page(results, page)
    nums = [
        InlineKeyboardButton(str(start + offset + 1), callback_data=f"search:{start + offset}")
        for offset in range(len(results[start:start + SEARCH_PAGE_SIZE]))
    ]
    buttons = [nums]
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("←", callback_data=f"searchpage:{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop:"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("→", callback_data=f"searchpage:{page + 1}"))
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


# --- View helpers (text + keyboard) ---


def jackett_view():
    api_status = t("jackett_key_set") if jackett_get_api_key() else t("jackett_key_not_set")
    has_password = jackett_has_password()
    pass_status = t("jackett_pass_set") if has_password else t("jackett_pass_not_set")
    return t("jackett_settings_title", api_status=api_status, pass_status=pass_status), jackett_settings_kb(has_password)


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
