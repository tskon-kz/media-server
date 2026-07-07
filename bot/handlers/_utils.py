import asyncio
import logging
import os
from functools import wraps
from html import escape

from telegram import Update, LinkPreviewOptions
from telegram.ext import ContextTypes

from config import ALLOWED, ICONS, INCOMING_DIR, APP_VERSION
import store
from store import t, load_cats
import keyboards as kb
from api import (
    jf, qb, jackett_search, jackett_get_api_key,
    stack_update, updater_status, UPDATER_CONTAINER,
)
from parser import process_torrent_rename, delete_torrent_links

log = logging.getLogger(__name__)


async def _notify_admins(bot, message: str):
    for uid in ALLOWED:
        try:
            await bot.send_message(uid, message)
        except Exception:
            pass


def guard(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ALLOWED:
            await update.message.reply_text(t("no_access"))
            return
        await func(update, ctx)
    return wrapper


async def _edit(query, text, keyboard=None, parse_mode="Markdown", disable_preview=False):
    kwargs = {}
    if disable_preview:
        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
    await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=keyboard, **kwargs)


async def _show_list(query, page=0):
    try:
        torrents = qb().torrents_info()
    except Exception as e:
        await _edit(query, t("qb_error", e=e))
        return
    if not torrents:
        await _edit(query, t("empty"))
        return
    await _edit(query, kb.list_text(torrents, page), kb.list_kb(page, len(torrents)), parse_mode="HTML")


async def _show_torrent_actions(query, tor_hash):
    try:
        torrents = qb().torrents_info(torrent_hashes=tor_hash)
    except Exception as e:
        await _edit(query, t("qb_error", e=e))
        return
    if not torrents:
        await _show_list(query, 0)
        return
    tor = torrents[0]
    cats = load_cats()
    has_move = bool(cats)
    has_reparse = _is_renameable(tor, cats)
    icon = ICONS.get(tor.state, "❓")
    pct  = f" {tor.progress*100:.0f}%" if tor.progress < 1 else ""
    size = f"{tor.size/1024**3:.1f} GB"
    await _edit(
        query,
        f"{icon} <b>{escape(kb.short_name(tor.name))}</b>{pct} — {size}",
        kb.torrent_action_kb(tor.hash, has_move, has_reparse),
        parse_mode="HTML",
    )


async def _run_pretty_parse(query, ctx, tor):
    cats = load_cats()
    delete_torrent_links(tor, cats)
    linked, pending_ids, errors = process_torrent_rename(tor, cats)
    jf("POST", "/Library/Refresh")
    for _ in errors:
        await ctx.bot.send_message(query.message.chat_id, t("rename_xdev"))
    if not linked and not pending_ids and not errors:
        await _edit(query, t("reparse_no_cat"))
    elif not pending_ids:
        await _edit(query, t("reparse_result", linked=linked, pending=0))
    else:
        await _edit(
            query,
            t("reparse_result", linked=linked, pending=len(pending_ids)),
            kb.rename_torrent_summary_kb(tor.hash, linked, len(pending_ids)),
        )


async def _do_stack_update(message, tag: str):
    """Launch the stack updater and report the outcome.

    The updater reconciles the whole compose stack and recreates the bot with
    `tag`. Two completion paths:

    - Bot image changed → compose kills this process mid-flight; the fresh bot's
      `_post_init` reports success via the persisted `update_pending` flag, so
      this task simply dies and never finishes the loop below.
    - Only sidecars changed (bot not recreated) → we stay alive, so we watch the
      updater to completion and report success/failure ourselves.

    A launch failure (returned as an error string) means nothing destructive
    happened; the old bot keeps running and reports why.
    """
    name = await asyncio.to_thread(stack_update, tag)
    if name != UPDATER_CONTAINER:
        store.set_config("update_pending", "")
        try:
            await message.reply_text(t("update_failed_self", err=str(name)[:300]))
        except Exception:
            pass
        return

    for _ in range(150):  # watch up to ~5 min
        await asyncio.sleep(2)
        status = await asyncio.to_thread(updater_status, name)
        if status.get("running"):
            continue
        # Reaching here means compose did NOT replace us (same bot image), so no
        # new process will report — do it ourselves.
        store.set_config("update_pending", "")
        if status.get("exit_code") == 0:
            reply = t("update_success", v=APP_VERSION)
        else:
            err = status.get("logs") or f"exit {status.get('exit_code')}"
            reply = t("update_failed_self", err=str(err)[:300])
        try:
            await message.reply_text(reply)
        except Exception:
            pass
        return

    try:
        await message.reply_text(t("update_timeout"))
    except Exception:
        pass


async def _do_search(message, uid: int, query: str):
    if not jackett_get_api_key():
        await message.reply_text(t("jackett_no_key"))
        return
    results = await asyncio.to_thread(jackett_search, query)
    if results is None:
        await message.reply_text(t("jackett_error"))
        return
    if not results:
        await message.reply_text(t("search_no_results"))
        return
    store.set_pending(uid, "search_results", results)
    store.set_pending(uid, "search_query", query)
    await message.reply_text(
        kb.search_results_text(query, results, 0),
        reply_markup=kb.search_results_kb(results, 0),
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


def _dl_path(cat: dict) -> str:
    return os.path.join(INCOMING_DIR, os.path.basename(cat["path"]))


def _is_renameable(tor, cats: list) -> bool:
    renameable = set()
    for c in cats:
        if c["jf_type"] in ("tvshows", "movies"):
            renameable.add(c["path"].rstrip("/"))
            renameable.add(_dl_path(c).rstrip("/"))
    return tor.save_path.rstrip("/") in renameable
