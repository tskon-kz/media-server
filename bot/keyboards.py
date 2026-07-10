import re
from functools import lru_cache
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from guessit import guessit
import store
from store import t

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


# --- Update / self-update keyboards ---

def update_kb(has_update, remote=None, channel="stable", show_back=True):
    buttons = []
    if has_update:
        buttons.append([InlineKeyboardButton(
            t("update_btn", v=remote), callback_data="selfupdate:stable")])
    # Channel toggle: on edge → offer stable (a plain re-install), on stable →
    # offer edge behind the beta warning (selfupdate:edge:confirm).
    if channel == "edge":
        buttons.append([InlineKeyboardButton(
            t("update_refresh_edge_btn"), callback_data="selfupdate:edge:go")])
        buttons.append([InlineKeyboardButton(
            t("channel_switch_stable_btn"), callback_data="selfupdate:stable")])
    else:
        buttons.append([InlineKeyboardButton(
            t("channel_switch_edge_btn"), callback_data="selfupdate:edge:confirm")])
    if show_back:
        buttons.append([InlineKeyboardButton(t("back_btn"), callback_data="settings:menu")])
    return InlineKeyboardMarkup(buttons)


def update_force_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("update_force_yes_btn"), callback_data="selfupdate:edge:go")],
        [InlineKeyboardButton(t("cancel_btn"),           callback_data="settings:update")],
    ])


def update_view(local, remote, channel="stable", show_back=True):
    # On edge the local version is an edge-<sha>, never equal to the latest
    # release tag, so the stable up-to-date/available comparison is meaningless —
    # just show the beta notice and a switch-to-stable button.
    if channel == "edge":
        return t("update_on_edge", v=local), update_kb(False, remote, channel, show_back)
    if remote is None:
        return t("update_check_fail", v=local), update_kb(False, remote, channel, show_back)
    if remote == local:
        return t("update_up_to_date", v=local), update_kb(False, remote, channel, show_back)
    return t("update_available", local=local, remote=remote), update_kb(True, remote, channel, show_back)


# --- Rename (manual naming) keyboards ---

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


# --- Start screen ---

def start_kb() -> InlineKeyboardMarkup:
    buttons = []
    url = store.get_config("webapp_url")
    if url:
        buttons.append([InlineKeyboardButton(t("webapp_open_button"), web_app=WebAppInfo(url=url))])
    buttons.append([
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton("🇬🇧 English",  callback_data="lang:en"),
    ])
    return InlineKeyboardMarkup(buttons)
