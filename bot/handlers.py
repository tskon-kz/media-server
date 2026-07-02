import asyncio
import errno
import os
import re
from functools import wraps
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from config import ALLOWED, DONE_STATES, APP_VERSION, INCOMING_DIR, ICONS
from store import (
    t, set_lang, load_cats, save_cats,
    load_states, save_states,
    get_user_state, set_user_state, clear_user_state,
    get_pending, set_pending, pop_pending,
    get_pending_torrent, set_pending_torrent, pop_pending_torrent,
    has_notified_update, mark_update_notified,
    get_qb_status, set_qb_status,
    set_config,
    get_rename_job,
    get_rename_jobs_by_hash, get_pending_rename_jobs, delete_rename_job,
)
import qbittorrentapi
from api import jf, jf_add_library, jf_remove_library, qb, qb_restart, qb_set_password, qb_temp_password, remote_version, trigger_update
from parser import process_torrent_rename, create_flat_hardlinks, create_flat_hardlink_for_job, delete_torrent_links, delete_all_cat_contents, parse_manual_input, build_target_path, create_hardlink
from store import get_rename_jobs_by_hash, delete_rename_jobs_by_hash
import keyboards as kb


def _dl_path(cat: dict) -> str:
    return os.path.join(INCOMING_DIR, os.path.basename(cat["path"]))


def _is_renameable(tor, cats: list) -> bool:
    renameable = set()
    for c in cats:
        if c["jf_type"] in ("tvshows", "movies"):
            renameable.add(c["path"].rstrip("/"))
            renameable.add(_dl_path(c).rstrip("/"))
    return tor.save_path.rstrip("/") in renameable


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


async def _run_pretty_parse(query, ctx, tor):
    cats = load_cats()
    delete_torrent_links(tor, cats)
    linked, pending_ids, errors = process_torrent_rename(tor, cats)
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


async def _do_trigger_update(message):
    ok = await asyncio.to_thread(trigger_update)
    if not ok:
        set_config("update_pending", "")
        try:
            await message.reply_text(t("update_error"))
        except Exception:
            pass


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
    await update.message.reply_text(kb.list_text(torrents, 0), parse_mode="HTML", reply_markup=kb.list_kb(0, len(torrents)))


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
        result = qb_set_password(text)
        if result is True:
            set_config("qb_pass", text)
            set_config("qb_pass_is_perm", "1")
            set_qb_status("unknown")
            await update.effective_chat.send_message(t("qb_pass_changed"), reply_markup=kb.qb_settings_kb(is_perm=True))
        else:
            await update.effective_chat.send_message(f"{t('qb_pass_error')}\n`{result}`", parse_mode="Markdown", reply_markup=kb.qb_settings_kb(is_perm=False))
        return

    if state == "await_torrent_select":
        chat_id = pop_pending(uid, "pending_list_chat_id")
        msg_id  = pop_pending(uid, "pending_list_msg_id")
        try:
            torrents = qb().torrents_info()
        except Exception as e:
            clear_user_state(uid)
            await update.message.reply_text(t("qb_error", e=e))
            return
        n = len(torrents)
        if not text.isdigit() or not (1 <= int(text) <= n):
            set_user_state(uid, "await_torrent_select")
            set_pending(uid, "pending_list_chat_id", chat_id)
            set_pending(uid, "pending_list_msg_id", msg_id)
            await update.message.reply_text(t("list_select_invalid", n=n))
            return
        idx = int(text) - 1
        tor = torrents[idx]
        cats = load_cats()
        has_move = bool(cats)
        has_reparse = _is_renameable(tor, cats)
        icon = ICONS.get(tor.state, "❓")
        pct  = f" {tor.progress*100:.0f}%" if tor.progress < 1 else ""
        size = f"{tor.size/1024**3:.1f} GB"
        text_out = f"{icon} <b>{escape(kb.short_name(tor.name))}</b>{pct} — {size}"
        clear_user_state(uid)
        try:
            await update.message.delete()
        except Exception:
            pass
        if chat_id and msg_id:
            try:
                await ctx.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text_out,
                    parse_mode="HTML",
                    reply_markup=kb.torrent_action_kb(tor.hash, has_move, has_reparse),
                )
                return
            except Exception:
                pass
        await update.effective_chat.send_message(
            text_out, parse_mode="HTML",
            reply_markup=kb.torrent_action_kb(tor.hash, has_move, has_reparse),
        )
        return

    if state == "await_episode_manual":
        job_id = pop_pending(uid, "pending_rename_id")
        if job_id is None:
            clear_user_state(uid)
            await update.message.reply_text(t("hint"))
            return
        job = get_rename_job(int(job_id))
        if not job:
            clear_user_state(uid)
            await update.message.reply_text(t("hint"))
            return
        cats = load_cats()
        cat = next((c for c in cats if c["path"] == job["cat_path"]), None)
        jf_type = cat["jf_type"] if cat else job["jf_type"]
        filename = os.path.basename(job["src_path"])
        parsed = parse_manual_input(jf_type, text, filename)
        if parsed is None:
            # keep state, let user try again
            set_user_state(uid, "await_episode_manual")
            set_pending(uid, "pending_rename_id", job_id)
            await update.message.reply_text(t("rename_invalid_input"))
            return
        clear_user_state(uid)
        dst_path = build_target_path({"path": job["cat_path"], "jf_type": jf_type}, parsed, filename)
        try:
            create_hardlink(job["src_path"], dst_path)
            delete_rename_job(job["id"])
            await update.message.reply_text(t("rename_done", dst=dst_path), parse_mode="Markdown")
        except OSError as e:
            if e.errno == errno.EXDEV:
                await update.message.reply_text(t("rename_xdev"))
            else:
                await update.message.reply_text(t("rename_error", e=e))
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
        case "noop":
            pass

        case "list":
            if value.startswith("manage:"):
                page = int(value[7:])
                try:
                    torrents = qb().torrents_info()
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                if not torrents:
                    await _edit(query, t("empty"))
                    return
                set_user_state(uid, "await_torrent_select")
                set_pending(uid, "pending_list_chat_id", query.message.chat_id)
                set_pending(uid, "pending_list_msg_id", query.message.message_id)
                prompt = kb.list_text(torrents, page) + f"\n\n{t('list_select_prompt', n=len(torrents))}"
                await _edit(query, prompt, parse_mode="HTML")
            elif value.startswith("page:"):
                page = int(value[5:])
                await _show_list(query, page)
            else:
                await _show_list(query, 0)

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
                case "media":
                    await _edit(query, t("media_mgmt_title"), kb.global_structure_menu_kb())

        case "qb":
            if value == "fetch_temp":
                temp = qb_temp_password()
                if temp:
                    set_config("qb_pass", temp)
                    set_config("qb_pass_is_perm", "")
                    set_qb_status("unknown")
                    try:
                        await _edit(query, t("qb_temp_pass", pass_=temp), kb.qb_settings_kb(is_perm=False), parse_mode="Markdown")
                    except Exception:
                        await query.answer(temp, show_alert=True)
                else:
                    await _edit(query, t("qb_no_temp_pass"), kb.qb_settings_kb(is_perm=True))
            elif value == "change_pass":
                set_user_state(uid, "await_qb_pass")
                await _edit(query, t("qb_change_pass_prompt"))
            elif value == "restart":
                if qb_restart():
                    set_qb_status("unknown")
                    await _edit(query, t("qb_restart_started"), kb.qb_settings_kb())
                    ctx.job_queue.run_once(
                        job_qb_restart_check,
                        when=20,
                        data={"chat_id": query.message.chat_id},
                    )
                else:
                    await query.answer(t("qb_restart_error"), show_alert=True)

        case "lang":
            set_lang(value)
            await _edit(query, t("settings_main"), kb.main_menu_kb())

        case "update":
            if value == "start":
                set_config("update_pending", "1")
                await _edit(query, t("update_started"))
                asyncio.create_task(_do_trigger_update(query.message))

        case "tor_action":
            await _show_torrent_actions(query, value)

        case "del":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
                if torrents:
                    delete_torrent_links(torrents[0], load_cats())
                qb().torrents_delete(delete_files=True, torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("add_error", e=e))
                return
            await _show_list(query, 0)

        case "addmagnet":
            magnet = pop_pending(uid, "pending_magnet")
            if not magnet:
                await _edit(query, t("add_error", e="expired"))
                return
            cat = load_cats()[int(value)]
            try:
                qb().torrents_add(urls=magnet, save_path=_dl_path(cat))
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
                qb().torrents_add(torrent_files=torrent, save_path=_dl_path(cat))
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
                qb().torrents_set_location(torrent_hashes=tor_hash, location=_dl_path(cat))
            except Exception as e:
                await _edit(query, t("add_error", e=e))
                return
            await _show_list(query, 0)

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
                dl = os.path.join(INCOMING_DIR, os.path.basename(path))
                for d in (path, dl):
                    os.makedirs(d, exist_ok=True)
                    try:    os.chown(d, 1000, 1000)
                    except: os.chmod(d, 0o777)
            cats = load_cats()
            cats.append({"name": name, "path": path, "jf_type": value})
            save_cats(cats)
            jf_add_library(name, path, value)
            await _edit(query, *kb.cats_view(cats))

        case "structure":
            await _edit(query, t("structure_menu_title"), kb.structure_menu_kb(value))

        case "reparse" | "reparse_do":
            # legacy callbacks — redirect to new structure menu / pretty parse
            if action == "reparse":
                await _edit(query, t("structure_menu_title"), kb.structure_menu_kb(value))
                return
            tor_hash = value
            try:
                torrents = qb().torrents_info(torrent_hashes=tor_hash)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if not torrents:
                await query.answer("Not found")
                return
            await _run_pretty_parse(query, ctx, torrents[0])

        case "struct_pretty":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if not torrents:
                await query.answer("Not found")
                return
            await _run_pretty_parse(query, ctx, torrents[0])

        case "struct_flat":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if not torrents:
                await query.answer(t("unlink_nothing"), show_alert=True)
                return
            cats = load_cats()
            delete_torrent_links(torrents[0], cats)
            errors = create_flat_hardlinks(torrents[0], cats)
            if errors and "cross-device" in errors[0].lower():
                await _edit(query, t("rename_xdev"))
            else:
                await _edit(query, t("unlink_done"))

        case "struct_del":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if torrents:
                delete_torrent_links(torrents[0], load_cats())
            await _edit(query, t("media_del_done"))

        case "unlink":
            # legacy — same as struct_flat
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if not torrents:
                await query.answer(t("unlink_nothing"), show_alert=True)
                return
            cats = load_cats()
            delete_torrent_links(torrents[0], cats)
            errors = create_flat_hardlinks(torrents[0], cats)
            if errors and "cross-device" in errors[0].lower():
                await _edit(query, t("rename_xdev"))
            else:
                await _edit(query, t("unlink_done"))

        case "media":
            sub = value
            cats = load_cats()
            if sub == "pretty":
                try:
                    torrents = qb().torrents_info()
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                delete_all_cat_contents(cats)
                all_linked, all_pending, all_errors = 0, [], []
                for tor in torrents:
                    linked, pids, errs = process_torrent_rename(tor, cats)
                    all_linked += linked
                    all_pending.extend(pids)
                    all_errors.extend(errs)
                for _ in all_errors:
                    await ctx.bot.send_message(query.message.chat_id, t("rename_xdev"))
                await _edit(query, t("media_pretty_done", linked=all_linked, pending=len(all_pending)))
            elif sub == "flat":
                try:
                    torrents = qb().torrents_info()
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                delete_all_cat_contents(cats)
                errors = []
                for tor in torrents:
                    errors.extend(create_flat_hardlinks(tor, cats))
                if errors and "cross-device" in errors[0].lower():
                    await _edit(query, t("rename_xdev"))
                else:
                    await _edit(query, t("media_flat_done"))
            elif sub == "del":
                await _edit(query, t("del_links_confirm"), kb.del_links_confirm_kb())
            elif sub == "del_confirm":
                delete_all_cat_contents(cats)
                await _edit(query, t("media_del_done"))

        case "rename_reset":
            if value == "confirm":
                delete_all_cat_contents(load_cats())
                await _edit(query, t("media_del_done"))
            else:
                await _edit(query, t("del_links_confirm"), kb.del_links_confirm_kb())

        case "rename":
            sub, _, job_id_str = value.partition(":")
            if sub == "skipall":
                pending = get_pending_rename_jobs()
                for j in pending:
                    delete_rename_job(j["id"])
                await _edit(query, t("rename_skipall_done", n=len(pending)))
                return
            if sub == "flatall":
                pending = get_pending_rename_jobs()
                n = 0
                for j in pending:
                    dst = create_flat_hardlink_for_job(j)
                    delete_rename_job(j["id"])
                    if dst:
                        n += 1
                await _edit(query, t("rename_flatall_done", n=n))
                return
            job = get_rename_job(int(job_id_str))
            if not job:
                await query.answer("Not found")
                return
            if sub == "skip":
                delete_rename_job(job["id"])
                await _edit(query, t("rename_skipped"))
            elif sub == "flat":
                dst = create_flat_hardlink_for_job(job)
                delete_rename_job(job["id"])
                if dst:
                    await _edit(query, t("rename_done", dst=dst), parse_mode="Markdown")
                else:
                    await _edit(query, t("rename_xdev"))
            elif sub == "manual":
                jf_type = job["jf_type"]
                filename = os.path.basename(job["src_path"])
                key = "rename_manual_prompt_tv" if jf_type == "tvshows" else "rename_manual_prompt_movie"
                set_user_state(uid, "await_episode_manual")
                set_pending(uid, "pending_rename_id", job["id"])
                await _edit(query, t(key, filename=filename), parse_mode="Markdown")

        case "rename_tor":
            sub, _, tor_hash = value.partition(":")
            if sub == "keep_flat":
                try:
                    torrents = qb().torrents_info(torrent_hashes=tor_hash)
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                cats = load_cats()
                if torrents:
                    delete_torrent_links(torrents[0], cats)
                    create_flat_hardlinks(torrents[0], cats)
                delete_rename_jobs_by_hash(tor_hash)
                await _edit(query, t("rename_tor_kept_flat"))
            elif sub == "manual":
                pending = get_rename_jobs_by_hash(tor_hash)
                if not pending:
                    await _edit(query, t("rename_tor_kept_flat"))
                    return
                await _edit(query, t("rename_tor_sending_manual", n=len(pending)))
                for job in pending:
                    await ctx.bot.send_message(
                        query.message.chat_id,
                        t("rename_failed_parse", filename=os.path.basename(job["src_path"])),
                        parse_mode="Markdown",
                        reply_markup=kb.rename_manual_kb(job["id"], len(pending)),
                    )
            elif sub == "skip":
                pending = get_rename_jobs_by_hash(tor_hash)
                for job in pending:
                    delete_rename_job(job["id"])
                await _edit(query, t("rename_tor_skipped", n=len(pending)))

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

async def job_qb_restart_check(ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = ctx.job.data["chat_id"]
    try:
        qb().torrents_info()
        set_qb_status("ok")
        await ctx.bot.send_message(chat_id, t("qb_restart_done"))
    except Exception:
        await ctx.bot.send_message(chat_id, t("qb_restart_timeout"))


async def job_check_done(ctx: ContextTypes.DEFAULT_TYPE):
    if get_qb_status() == "error":
        return
    known = load_states()
    try:
        torrents = qb().torrents_info()
    except qbittorrentapi.LoginFailed:
        set_qb_status("error")
        return
    except Exception:
        return
    set_qb_status("ok")
    active = {tor.hash for tor in torrents}
    cats = load_cats()
    for tor in torrents:
        prev = known.get(tor.hash)
        if prev and prev not in DONE_STATES and tor.state in DONE_STATES:
            for uid in ALLOWED:
                await ctx.bot.send_message(uid, t("download_done", name=kb.short_name(tor.name)))
            jf("POST", "/Library/Refresh")
            errors = create_flat_hardlinks(tor, cats)
            for _ in errors:
                for uid in ALLOWED:
                    await ctx.bot.send_message(uid, t("rename_xdev"))
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
