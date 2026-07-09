import os
import qbittorrentapi
from telegram import MenuButtonWebApp, WebAppInfo

from config import ALLOWED, DONE_STATES, APP_VERSION, WEBAPP_URL, INCOMING_DIR
from store import (
    t, load_cats, load_states, save_states,
    get_config, set_config, set_qb_status, get_qb_status,
    has_notified_update, mark_update_notified,
    upsert_disk_entry,
    get_finished_upscale_disk_ids, get_upscale_jobs_by_disk_id, mark_upscale_disk_notified,
)
from api import jf, qb, invalidate_qb, gh_latest_release_tag, get_cloudflared_url
from parser import create_flat_hardlinks, process_torrent_rename, delete_torrent_links, find_cat
import keyboards as kb
from ._utils import _notify_admins, log


async def job_check_done(ctx):
    known = load_states()
    try:
        # qb() self-recovers from a stale temp password (see api._qb_login), so we
        # keep retrying every run rather than latching on "error" forever — a fixed
        # password or a qb restart heals on the next tick.
        torrents = qb().torrents_info()
    except qbittorrentapi.LoginFailed:
        invalidate_qb()
        # Notify admins only on the transition into error, not every 30 s.
        if get_qb_status() != "error":
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
            cat = find_cat(tor, cats)
            if cat:
                basename = os.path.basename(cat["path"].rstrip("/"))
                upsert_disk_entry(f"{basename}/{tor.name}", tor.name, cat["id"], tor.size)
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


def _upscale_stub(disk_id: str):
    """Minimal torrent stand-in for content the upscaler rewrote in place, so the
    parser can rebuild library hardlinks (the replaced files have new inodes)."""
    parts = disk_id.split("/", 1)
    if len(parts) != 2 or ".." in disk_id or not all(parts):
        return None
    slug, name = parts

    class _Stub:
        pass

    stub = _Stub()
    stub.name = name
    stub.save_path = os.path.join(INCOMING_DIR, slug) + "/"
    stub.content_path = os.path.join(INCOMING_DIR, slug, name)
    stub.hash = ""
    return stub


async def job_check_upscale(ctx):
    """Finalise finished upscale batches: rebuild library hardlinks (originals
    were replaced → old inodes are stale), refresh Jellyfin, notify, mark done."""
    cats = load_cats()
    rename_mode = get_config("rename_mode", "flat")
    for disk_id in get_finished_upscale_disk_ids():
        jobs = get_upscale_jobs_by_disk_id(disk_id)
        errored = [j for j in jobs if j["status"] == "error"]
        stub = _upscale_stub(disk_id)
        if stub is not None and len(errored) < len(jobs):
            # At least one file was upscaled — repoint the library at the new files.
            try:
                delete_torrent_links(stub, cats)
                if rename_mode == "pretty":
                    process_torrent_rename(stub, cats)
                else:
                    create_flat_hardlinks(stub, cats)
                jf("POST", "/Library/Refresh")
            except Exception:
                log.exception("Upscale relink failed for %s", disk_id)
        name = kb.short_name(disk_id.split("/", 1)[1])
        for uid in ALLOWED:
            try:
                if errored:
                    await ctx.bot.send_message(
                        uid, t("upscale_error", name=name, e=errored[0]["error"] or "?"))
                else:
                    await ctx.bot.send_message(uid, t("upscale_done", name=name))
            except Exception:
                pass
        mark_upscale_disk_notified(disk_id)


async def job_check_webapp_url(ctx):
    """Keep the stored Mini App URL and each user's Menu Button in sync.

    When WEBAPP_URL is set (named Cloudflare tunnel with a static domain), it is
    used directly. Otherwise polls cloudflared container logs for the ephemeral
    trycloudflare.com URL and updates on every change (new URL on each restart).
    """
    url = WEBAPP_URL or get_cloudflared_url()
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
