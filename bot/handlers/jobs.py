import qbittorrentapi

from config import ALLOWED, DONE_STATES, APP_VERSION
from store import (
    t, load_cats, load_states, save_states,
    get_config, set_qb_status, get_qb_status,
    has_notified_update, mark_update_notified,
)
from api import jf, qb, invalidate_qb, remote_version
from parser import create_flat_hardlinks, process_torrent_rename
import keyboards as kb
from ._utils import _notify_admins, log


async def job_qb_restart_check(ctx):
    chat_id = ctx.job.data["chat_id"]
    try:
        qb().torrents_info()
        set_qb_status("ok")
        await ctx.bot.send_message(chat_id, t("qb_restart_done"))
    except Exception:
        await ctx.bot.send_message(chat_id, t("qb_restart_timeout"))


async def job_check_done(ctx):
    if get_qb_status() == "error":
        return
    known = load_states()
    prev_status = get_qb_status()
    try:
        torrents = qb().torrents_info()
    except qbittorrentapi.LoginFailed:
        invalidate_qb()
        set_qb_status("error")
        if prev_status != "error":
            log.error("qBittorrent auth failed")
            await _notify_admins(ctx.bot, t("qb_auth_error_notify"))
        return
    except Exception:
        return
    set_qb_status("ok")
    active = {tor.hash for tor in torrents}
    cats = load_cats()
    rename_mode = get_config("rename_mode", "flat")

    for tor in torrents:
        prev = known.get(tor.hash)
        if prev and prev not in DONE_STATES and tor.state in DONE_STATES:
            log.info("Download done: %s", tor.name)
            for uid in ALLOWED:
                await ctx.bot.send_message(uid, t("download_done", name=kb.short_name(tor.name)), parse_mode="Markdown")
            jf("POST", "/Library/Refresh")

            if rename_mode == "pretty":
                linked, pending_ids, errors = process_torrent_rename(tor, cats)
                for _ in errors:
                    for uid in ALLOWED:
                        await ctx.bot.send_message(uid, t("rename_xdev"))
                if pending_ids:
                    for uid in ALLOWED:
                        await ctx.bot.send_message(
                            uid,
                            t("rename_pending_notify", name=kb.short_name(tor.name), n=len(pending_ids)),
                            parse_mode="Markdown",
                            reply_markup=kb.rename_torrent_summary_kb(tor.hash, linked, len(pending_ids)),
                        )
            else:
                errors = create_flat_hardlinks(tor, cats)
                for _ in errors:
                    for uid in ALLOWED:
                        await ctx.bot.send_message(uid, t("rename_xdev"))

        known[tor.hash] = tor.state

    for h in list(known):
        if h not in active:
            del known[h]
    save_states(known)


async def job_check_update(ctx):
    remote = remote_version()
    if remote and remote != APP_VERSION and not has_notified_update(remote):
        mark_update_notified(remote)
        for uid in ALLOWED:
            try:
                await ctx.bot.send_message(uid, t("update_notify", v=remote), parse_mode="Markdown")
            except Exception:
                pass
