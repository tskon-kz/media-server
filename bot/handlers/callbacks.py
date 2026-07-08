import asyncio
import os

from config import ALLOWED, APP_VERSION, current_channel
from store import (
    t, set_config, set_lang, load_cats,
    set_user_state, set_pending,
    delete_rename_jobs_by_hash, get_rename_jobs_by_hash,
    get_pending_rename_jobs, get_rename_job, delete_rename_job,
)
from api import jf, qb, gh_latest_release_tag
from parser import create_flat_hardlinks, create_flat_hardlink_for_job, delete_torrent_links
import keyboards as kb
from ._utils import _edit, _do_self_update


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

        case "lang":
            if value in ("ru", "en"):
                set_lang(value)
            await _edit(query, t("start"), kb.start_kb())

        case "selfupdate":
            if value == "stable":
                set_config("update_pending", "1")
                await _edit(query, t("update_started"))
                asyncio.create_task(_do_self_update(query.message, "stable"))
            elif value == "edge:confirm":
                await _edit(query, t("update_force_warn"), kb.update_force_confirm_kb())
            elif value == "edge:go":
                set_config("update_pending", "1")
                await _edit(query, t("update_started"))
                asyncio.create_task(_do_self_update(query.message, "edge"))

        case "settings":
            if value == "update":
                remote = await asyncio.to_thread(gh_latest_release_tag)
                await _edit(query, *kb.update_view(APP_VERSION, remote, current_channel()))

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
                    jf("POST", "/Library/Refresh")
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
                jf("POST", "/Library/Refresh")
                await _edit(query, t("rename_flatall_done", n=n))
                return
            job = get_rename_job(int(job_id_str))
            if not job:
                await _edit(query, t("hint"))
                return
            if sub == "skip":
                delete_rename_job(job["id"])
                await _edit(query, t("rename_skipped"))
            elif sub == "flat":
                dst = create_flat_hardlink_for_job(job)
                delete_rename_job(job["id"])
                if dst:
                    jf("POST", "/Library/Refresh")
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
