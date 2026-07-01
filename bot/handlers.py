import os
import re
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED, DONE_STATES, APP_VERSION
from store import (
    t, set_lang, load_cats, save_cats,
    load_states, save_states,
    get_user_state, set_user_state, clear_user_state,
    get_pending, set_pending, pop_pending,
    get_pending_torrent, set_pending_torrent, pop_pending_torrent,
    has_notified_update, mark_update_notified,
    set_config,
)
from api import jf, jf_add_library, jf_remove_library, qb, qb_set_password, remote_version, trigger_update
import keyboards as kb


def guard(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ALLOWED:
            await update.message.reply_text(t("no_access"))
            return
        await func(update, ctx)
    return wrapper


async def _edit(query, text, keyboard=None, parse_mode="Markdown"):
    await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=keyboard)


async def _show_list(query, edit_mode=False):
    try:
        torrents = qb().torrents_info()
    except Exception as e:
        await _edit(query, t("qb_error", e=e))
        return
    if not torrents:
        await _edit(query, t("empty"))
        return
    keyboard = kb.list_edit_kb(torrents) if edit_mode else kb.list_kb()
    await _edit(query, kb.list_text(torrents), keyboard, parse_mode="HTML")


# --- Commands ---

@guard
async def cmd_start(update, ctx):
    await update.message.reply_text(t("start"), parse_mode="Markdown")


@guard
async def cmd_list(update, ctx):
    try:
        torrents = qb().torrents_info()
    except Exception as e:
        await update.message.reply_text(t("qb_error", e=e))
        return
    if not torrents:
        await update.message.reply_text(t("empty"))
        return
    await update.message.reply_text(kb.list_text(torrents), parse_mode="HTML", reply_markup=kb.list_kb())


@guard
async def cmd_status(update, ctx):
    try:
        info = qb().transfer_info()
        msg  = t("status_ok", dl=f"{info.dl_info_speed/1024:.0f}", ul=f"{info.up_info_speed/1024:.0f}")
    except Exception:
        msg = t("status_err")
    await update.message.reply_text(msg, parse_mode="Markdown")


@guard
async def cmd_scan(update, ctx):
    ok = jf("POST", "/Library/Refresh")
    await update.message.reply_text(t("scan_ok") if ok else t("scan_error"))


@guard
async def cmd_settings(update, ctx):
    await update.message.reply_text(t("settings_main"), reply_markup=kb.main_menu_kb())


# --- Messages ---

@guard
async def on_message(update, ctx):
    uid   = update.effective_user.id
    text  = update.message.text or ""
    state = get_user_state(uid)

    if text.startswith("magnet:"):
        clear_user_state(uid)
        cats = load_cats()
        if not cats:
            try:
                qb().torrents_add(urls=text, save_path="/media/downloads")
                await update.message.reply_text(t("added"))
            except Exception as e:
                await update.message.reply_text(t("add_error", e=e))
            return
        set_pending(uid, "pending_magnet", text)
        await update.message.reply_text(t("pick_cat"), reply_markup=kb.cats_pick_kb(cats, "addmagnet"))
        return

    if state == "await_cat_rename":
        clear_user_state(uid)
        idx = pop_pending(uid, "pending_cat_idx")
        if idx is not None:
            cats = load_cats()
            if 0 <= idx < len(cats):
                cats[idx]["name"] = text
                save_cats(cats)
        text_val, kb_val = kb.cats_view(load_cats())
        await update.message.reply_text(text_val, parse_mode="Markdown", reply_markup=kb_val)
        return

    if state == "await_jf_user_name":
        clear_user_state(uid)
        set_pending(uid, "pending_jf_user_name", text)
        set_user_state(uid, "await_jf_user_pass")
        await update.message.reply_text(t("jf_add_user_pass", name=text), parse_mode="Markdown")
        return

    if state == "await_jf_user_pass":
        clear_user_state(uid)
        name = pop_pending(uid, "pending_jf_user_name", "")
        user = jf("POST", "/Users/New", {"Name": name})
        if isinstance(user, dict) and "Id" in user:
            jf("POST", f"/Users/{user['Id']}/Password", {"NewPw": text})
            await update.message.delete()
            await update.effective_chat.send_message(t("jf_user_added", name=name), parse_mode="Markdown")
        else:
            await update.message.reply_text(t("jf_user_error"))
        return

    if state == "await_cat_name":
        slug = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE).strip().lower().replace(" ", "_")
        set_pending(uid, "pending_cat_name", text)
        set_pending(uid, "pending_cat_path", f"/media/{slug}" if slug else "/media")
        await update.message.reply_text(t("cat_pick_type"), reply_markup=kb.cat_type_kb())
        return

    if state == "await_qb_pass":
        clear_user_state(uid)
        await update.message.delete()
        if qb_set_password(text):
            set_config("qb_pass", text)
            await update.effective_chat.send_message(t("qb_pass_changed"), reply_markup=kb.qb_settings_kb())
        else:
            await update.effective_chat.send_message(t("qb_pass_error"), reply_markup=kb.qb_settings_kb())
        return

    await update.message.reply_text(t("hint"))


@guard
async def on_torrent_file(update, ctx):
    uid  = update.effective_user.id
    file = await (await update.message.document.get_file()).download_as_bytearray()
    cats = load_cats()
    if not cats:
        try:
            qb().torrents_add(torrent_files=bytes(file), save_path="/media/downloads")
            await update.message.reply_text(t("added"))
        except Exception as e:
            await update.message.reply_text(t("add_error", e=e))
        return
    set_pending_torrent(uid, bytes(file))
    await update.message.reply_text(t("pick_cat"), reply_markup=kb.cats_pick_kb(cats, "addtorrent"))


# --- Callbacks ---

async def on_callback(update, ctx):
    query = update.callback_query
    uid   = update.effective_user.id
    if uid not in ALLOWED:
        await query.answer(t("no_access"))
        return
    await query.answer()

    action, _, value = query.data.partition(":")

    match action:
        case "list":
            await _show_list(query, edit_mode=(value == "edit"))

        case "settings":
            match value:
                case "menu":
                    await _edit(query, t("settings_main"), kb.main_menu_kb())
                case "cats":
                    await _edit(query, *kb.cats_view(load_cats()))
                case "lang":
                    await _edit(query, t("lang_pick"), kb.lang_kb())
                case "qb":
                    await _edit(query, *kb.qb_view())
                case "jf_users":
                    await _edit(query, *kb.jf_users_view(jf("GET", "/Users") or []))
                case "update":
                    await _edit(query, *kb.update_view(APP_VERSION, remote_version()))

        case "qb":
            if value == "change_pass":
                set_user_state(uid, "await_qb_pass")
                await _edit(query, t("qb_change_pass_prompt"))

        case "lang":
            set_lang(value)
            await _edit(query, t("settings_main"), kb.main_menu_kb())

        case "update":
            if value == "start":
                try:
                    trigger_update()
                    await _edit(query, t("update_started"))
                except Exception:
                    await _edit(query, t("update_error"))

        case "del":
            try:
                qb().torrents_delete(delete_files=True, torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("add_error", e=e))
                return
            await _show_list(query, edit_mode=True)

        case "addmagnet":
            magnet = pop_pending(uid, "pending_magnet")
            if not magnet:
                await _edit(query, t("add_error", e="expired"))
                return
            cat = load_cats()[int(value)]
            try:
                qb().torrents_add(urls=magnet, save_path=cat["path"])
                await _edit(query, t("added"))
            except Exception as e:
                await _edit(query, t("add_error", e=e))

        case "addtorrent":
            torrent = pop_pending_torrent(uid)
            if not torrent:
                await _edit(query, t("add_error", e="expired"))
                return
            cat = load_cats()[int(value)]
            try:
                qb().torrents_add(torrent_files=torrent, save_path=cat["path"])
                await _edit(query, t("added"))
            except Exception as e:
                await _edit(query, t("add_error", e=e))

        case "move":
            if not load_cats():
                await query.answer(t("no_cats"))
            else:
                await query.edit_message_reply_markup(reply_markup=kb.move_cats_kb(value))

        case "moveto":
            tor_hash, _, cat_idx = value.partition(":")
            cat = load_cats()[int(cat_idx)]
            try:
                qb().torrents_set_location(torrent_hashes=tor_hash, location=cat["path"])
            except Exception as e:
                await _edit(query, t("add_error", e=e))
                return
            await _show_list(query)

        case "editcat":
            set_pending(uid, "pending_cat_idx", int(value))
            set_user_state(uid, "await_cat_rename")
            await _edit(query, t("cat_rename_prompt"))

        case "delcat":
            cats = load_cats()
            cat  = cats.pop(int(value))
            save_cats(cats)
            jf_remove_library(cat["name"])
            await _edit(query, *kb.cats_view(cats))

        case "cattype":
            name = pop_pending(uid, "pending_cat_name", "")
            path = pop_pending(uid, "pending_cat_path", "")
            clear_user_state(uid)
            if path:
                os.makedirs(path, exist_ok=True)
                try:    os.chown(path, 1000, 1000)
                except: os.chmod(path, 0o777)
            cats = load_cats()
            cats.append({"name": name, "path": path, "jf_type": value})
            save_cats(cats)
            jf_add_library(name, path, value)
            await _edit(query, *kb.cats_view(cats))

        case "jf_deluser":
            if jf("DELETE", f"/Users/{value}") is not None:
                await _edit(query, *kb.jf_users_view(jf("GET", "/Users") or []))
            else:
                await query.answer(t("jf_user_error"))

        case "jf_adduser":
            set_user_state(uid, "await_jf_user_name")
            await _edit(query, t("jf_add_user_name"))

        case "addcat":
            set_user_state(uid, "await_cat_name")
            await _edit(query, t("cat_add_name"))


# --- Background jobs ---

async def job_check_done(ctx: ContextTypes.DEFAULT_TYPE):
    known = load_states()
    try:
        torrents = qb().torrents_info()
    except Exception:
        return
    active = {tor.hash for tor in torrents}
    for tor in torrents:
        prev = known.get(tor.hash)
        if prev and prev not in DONE_STATES and tor.state in DONE_STATES:
            for uid in ALLOWED:
                await ctx.bot.send_message(uid, t("download_done", name=tor.name))
            jf("POST", "/Library/Refresh")
        known[tor.hash] = tor.state
    for h in list(known):
        if h not in active:
            del known[h]
    save_states(known)


async def job_check_update(ctx: ContextTypes.DEFAULT_TYPE):
    remote = remote_version()
    if remote and remote != APP_VERSION and not has_notified_update(remote):
        mark_update_notified(remote)
        for uid in ALLOWED:
            try:
                await ctx.bot.send_message(uid, t("update_notify", v=remote), parse_mode="Markdown")
            except Exception:
                pass
