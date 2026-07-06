import qbittorrentapi
from telegram import MenuButtonWebApp, WebAppInfo

from config import ALLOWED, DONE_STATES, APP_VERSION
from store import (
    t, load_cats, load_states, save_states,
    get_config, set_config, set_qb_status, get_qb_status,
    has_notified_update, mark_update_notified,
)
from api import jf, qb, invalidate_qb, gh_latest_release_tag, get_cloudflared_url
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
    try:
        torrents = qb().torrents_info()
    except qbittorrentapi.LoginFailed:
        invalidate_qb()
        set_qb_status("error")
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
            if rename_mode == "pretty":
                linked, pending_ids, errors = process_torrent_rename(tor, cats)
                jf("POST", "/Library/Refresh")
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
                jf("POST", "/Library/Refresh")
                for _ in errors:
                    for uid in ALLOWED:
                        await ctx.bot.send_message(uid, t("rename_xdev"))

        known[tor.hash] = tor.state

    for h in list(known):
        if h not in active:
            del known[h]
    save_states(known)


async def job_check_webapp_url(ctx):
    """Keep the stored Mini App URL and each user's Menu Button in sync with the
    live cloudflared quick-tunnel URL.

    The tunnel URL is regenerated on every cloudflared restart, so this polls
    the container logs and, whenever the URL changes, persists it and re-points
    the persistent Menu Button (next to the message box) at the new address.
    """
    url = get_cloudflared_url()
    if not url or url == get_config("webapp_url"):
        return
    set_config("webapp_url", url)
    button = MenuButtonWebApp(text=t("webapp_menu_button"), web_app=WebAppInfo(url=url))
    for uid in ALLOWED:
        try:
            await ctx.bot.set_chat_menu_button(chat_id=uid, menu_button=button)
        except Exception:
            pass
    log.info("Web App URL updated: %s", url)


async def job_check_update(ctx):
    latest = gh_latest_release_tag()
    if latest and latest != APP_VERSION and not has_notified_update(latest):
        mark_update_notified(latest)
        for uid in ALLOWED:
            try:
                await ctx.bot.send_message(uid, t("update_notify", v=latest), parse_mode="Markdown")
            except Exception:
                pass
