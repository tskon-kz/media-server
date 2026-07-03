import errno
import os
import re
from html import escape

from config import ICONS
from store import (
    t, load_cats, save_cats,
    get_user_state, set_user_state, clear_user_state,
    get_pending, set_pending, pop_pending,
    set_pending_torrent, pop_pending_torrent,
    get_rename_job, delete_rename_job,
    set_config, set_qb_status,
)
from api import jf, qb, qb_set_password, invalidate_qb
from parser import build_target_path, create_hardlink, parse_manual_input
import keyboards as kb
from ._utils import guard, _dl_path, _is_renameable, _do_search, log


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
        cat_id = pop_pending(uid, "pending_cat_id")
        if cat_id is not None:
            cats = load_cats()
            cat = next((c for c in cats if c["id"] == cat_id), None)
            if cat:
                cat["name"] = text
                save_cats(cats)
        txt, kb_val = kb.cats_view(load_cats())
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb_val)
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
            invalidate_qb()
            set_qb_status("unknown")
            await update.effective_chat.send_message(
                t("qb_pass_changed"),
                reply_markup=kb.qb_settings_kb(is_perm=True),
            )
        else:
            await update.effective_chat.send_message(
                f"{t('qb_pass_error')}\n`{result}`",
                parse_mode="Markdown",
                reply_markup=kb.qb_settings_kb(is_perm=False),
            )
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
        tor = torrents[int(text) - 1]
        cats = load_cats()
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
                    reply_markup=kb.torrent_action_kb(tor.hash, bool(cats), _is_renameable(tor, cats)),
                )
                return
            except Exception:
                pass
        await update.effective_chat.send_message(
            text_out, parse_mode="HTML",
            reply_markup=kb.torrent_action_kb(tor.hash, bool(cats), _is_renameable(tor, cats)),
        )
        return

    if state == "await_search_query":
        clear_user_state(uid)
        await _do_search(update.message, uid, text)
        return

    if state == "await_jackett_key":
        clear_user_state(uid)
        set_config("jackett_api_key", text)
        await update.message.reply_text(t("jackett_key_saved"), reply_markup=kb.jackett_settings_kb())
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
            set_user_state(uid, "await_episode_manual")
            set_pending(uid, "pending_rename_id", job_id)
            await update.message.reply_text(t("rename_invalid_input"))
            return
        clear_user_state(uid)
        dst_path = build_target_path({"path": job["cat_path"], "jf_type": jf_type}, parsed, filename)
        try:
            create_hardlink(job["src_path"], dst_path)
            delete_rename_job(job["id"])
            jf("POST", "/Library/Refresh")
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
