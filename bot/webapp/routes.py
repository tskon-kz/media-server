"""JSON API for the Telegram Mini App.

Every endpoint is a thin wrapper over the same `store` / `api` / `parser`
functions the bot command handlers use — no business logic lives here. Multi-step
bot conversations (category pickers, manual-rename prompts) collapse into a
single request/response with all needed fields in the body.

Blocking I/O (qBittorrent, Jellyfin, Jackett, hardlinking) is pushed to a thread
so it never stalls the shared PTB/aiohttp event loop.
"""
import asyncio
import os
import re
import shutil
import threading
import time

from aiohttp import web

from config import (
    ICONS, INCOMING_DIR, BACKUP_DIR, APP_VERSION, current_channel,
    QB_PORT, JF_PORT, JACKETT_PORT, UPSCALERS, UPSCALER_IDS,
    COMPRESSION_LEVELS, COMPRESSION_IDS, UPSCALE_TARGETS, UPSCALE_TARGET_IDS,
)
import store
from store import (
    t, load_cats, save_cats, set_lang, set_config, get_config,
    get_creds, get_qb_status, set_qb_status,
    load_disk_entries, upsert_disk_entry, upsert_disk_entries_batch, delete_disk_entry,
    add_upscale_job, get_active_upscale_status, delete_upscale_jobs_by_disk_id,
    cancel_queued_upscale, get_done_upscale_src_paths, clear_incomplete_upscale_jobs,
    get_done_upscale_jobs, get_upscaled_disk_ids,
)
from api import (
    jf, jf_add_library, jf_remove_library, qb, invalidate_qb,
    qb_temp_password, qb_restart, qb_set_password,
    jackett_get_api_key, jackett_has_password, jackett_set_password,
    jackett_search, jackett_download_torrent,
    gh_latest_release_tag, self_update,
)
from parser import (
    process_torrent_rename, create_flat_hardlinks,
    delete_torrent_links, delete_all_cat_contents, get_video_files,
    VIDEO_EXTENSIONS,
)
import keyboards as kb

routes = web.RouteTableDef()

_thread = asyncio.to_thread


# ---- shared helpers (kept local so webapp doesn't import handlers/) ----

def _dl_path(cat: dict) -> str:
    return os.path.join(INCOMING_DIR, os.path.basename(cat["path"]))


def _is_renameable(tor, cats: list) -> bool:
    targets = set()
    for c in cats:
        if c["jf_type"] in ("tvshows", "movies"):
            targets.add(c["path"].rstrip("/"))
            targets.add(_dl_path(c).rstrip("/"))
    return tor.save_path.rstrip("/") in targets


def _qb_disk_id(tor) -> str:
    """Disk-identity of a qB torrent.

    Keyed on what actually lands on disk (basename of ``content_path``), not on
    ``tor.name``: a single-file torrent's display name can differ from the
    on-disk filename (e.g. a trailing ``.torrent``), which would otherwise make
    it fail to match its own downloaded file and get mislabelled as disk-only.
    """
    content = os.path.basename((getattr(tor, "content_path", "") or "").rstrip("/"))
    name = content or tor.name
    return f"{os.path.basename(tor.save_path.rstrip('/'))}/{name}"


def _disk_stub(disk_id: str):
    """Minimal torrent stand-in built from a disk entry, so the parser can act
    on library hardlinks for content qBittorrent no longer tracks."""
    parts = disk_id.split("/", 1)
    if len(parts) != 2 or ".." in disk_id or not all(parts):
        return None
    basename, name = parts
    target = os.path.join(INCOMING_DIR, basename, name)
    if not os.path.realpath(target).startswith(os.path.realpath(INCOMING_DIR) + os.sep):
        return None

    class _Stub:
        pass

    stub = _Stub()
    stub.name = name
    stub.save_path = os.path.join(INCOMING_DIR, basename) + "/"
    stub.content_path = target
    stub.hash = ""
    return stub


def _backup_path(disk_id: str) -> str | None:
    """Backup location for a disk_id (``<catslug>/<name>``), or None if malformed.

    Backups are real copies (not hardlinks) under BACKUP_DIR so they survive the
    upscaler replacing the originals in place; keeps the original layout so the
    user can restore by copying back.
    """
    parts = disk_id.split("/", 1)
    if len(parts) != 2 or ".." in disk_id or not all(parts):
        return None
    target = os.path.join(BACKUP_DIR, parts[0], parts[1])
    if not os.path.realpath(os.path.dirname(target)).startswith(os.path.realpath(BACKUP_DIR)):
        return None
    return target


def _has_backup(disk_id: str) -> bool:
    p = _backup_path(disk_id)
    return bool(p) and os.path.exists(p)


async def _resolve_torrent(disk_id: str):
    """Live qB torrent for this disk entry, or a disk stub if qB no longer
    tracks it. The disk is the source of truth; qBittorrent is secondary."""
    if disk_id.startswith("qb:"):
        return await _one_torrent(disk_id[3:])
    try:
        all_tors = await _qb_info()
    except Exception:
        all_tors = []
    tor = next((tor for tor in all_tors if _qb_disk_id(tor) == disk_id), None)
    if tor is not None:
        return tor
    return _disk_stub(disk_id)


def _scan_incoming(cats: list) -> list[dict]:
    """Fast: one os.listdir per category download dir, no size I/O."""
    entries = []
    for cat in cats:
        basename = os.path.basename(cat["path"].rstrip("/"))
        incoming = os.path.join(INCOMING_DIR, basename)
        if not os.path.isdir(incoming):
            continue
        try:
            names = sorted(os.listdir(incoming))
        except OSError:
            continue
        for name in names:
            if name.startswith("."):
                continue
            entries.append({
                "name": name,
                "disk_id": f"{basename}/{name}",
                "cat": cat,
            })
    return entries


def _compute_disk_size(path: str) -> int:
    total = 0
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        for dirpath, _dirs, files in os.walk(path):
            for fname in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, fname))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _torrent_dict(tor, cats: list) -> dict:
    return {
        "disk_id": _qb_disk_id(tor),
        "hash": tor.hash,
        "in_qbittorrent": True,
        "name": kb.short_name(tor.name),
        "raw_name": tor.name,
        "state": tor.state,
        "icon": ICONS.get(tor.state, "❓"),
        "progress": tor.progress,
        "size": tor.size,
        "dlspeed": getattr(tor, "dlspeed", 0),
        "upspeed": getattr(tor, "upspeed", 0),
        "eta": getattr(tor, "eta", 0),
        "save_path": tor.save_path,
        "renameable": _is_renameable(tor, cats),
    }


def _torrent_dict_merged(disk_entry: dict, size: int, qb_tor=None, cats: list | None = None) -> dict:
    disk_id = disk_entry["disk_id"]
    if qb_tor is not None:
        return {
            "disk_id": disk_id,
            "hash": qb_tor.hash,
            "in_qbittorrent": True,
            "name": kb.short_name(qb_tor.name),
            "raw_name": qb_tor.name,
            "state": qb_tor.state,
            "icon": ICONS.get(qb_tor.state, "❓"),
            "progress": qb_tor.progress,
            "size": qb_tor.size,
            "dlspeed": getattr(qb_tor, "dlspeed", 0),
            "upspeed": getattr(qb_tor, "upspeed", 0),
            "eta": getattr(qb_tor, "eta", 0),
            "save_path": qb_tor.save_path,
            "renameable": _is_renameable(qb_tor, cats or []),
        }
    cat = disk_entry["cat"]
    name = disk_entry["name"]
    return {
        "disk_id": disk_id,
        "hash": None,
        "in_qbittorrent": False,
        "name": kb.short_name(name),
        "raw_name": name,
        "state": "archived",
        "icon": "📁",
        "progress": 1.0,
        "size": size if size > 0 else None,
        "dlspeed": 0,
        "upspeed": 0,
        "eta": 0,
        "save_path": cat["path"],
        "renameable": cat.get("jf_type") in ("tvshows", "movies"),
    }





async def _qb_info(hashes=None):
    def _f():
        return qb().torrents_info(torrent_hashes=hashes) if hashes else qb().torrents_info()
    return await _thread(_f)


async def _one_torrent(tor_hash):
    tors = await _qb_info(tor_hash)
    return tors[0] if tors else None


async def _json(request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


def _err(msg, status=400):
    return web.json_response({"error": msg}, status=status)


def _find_cat(cat_id):
    return next((c for c in load_cats() if c["id"] == int(cat_id)), None)


async def _add_to_qb(*, magnet=None, torrent_bytes=None, save_path):
    def _f():
        if magnet is not None:
            qb().torrents_add(urls=magnet, save_path=save_path)
        else:
            qb().torrents_add(torrent_files=torrent_bytes, save_path=save_path)
    await _thread(_f)


# ---- health (public) ----

@routes.get("/api/health")
async def health(request):
    return web.json_response({"status": "ok", "version": APP_VERSION})


# ---- home / config ----

@routes.get("/api/config")
async def config(request):
    server_ip = get_config("server_ip")
    links = None
    if server_ip:
        links = {
            "qbittorrent": f"http://{server_ip}:{QB_PORT}",
            "jellyfin":    f"http://{server_ip}:{JF_PORT}",
            "jackett":     f"http://{server_ip}:{JACKETT_PORT}",
        }
    return web.json_response({
        "version": APP_VERSION,
        "lang": get_config("lang", "ru"),
        "rename_mode": get_config("rename_mode", "flat"),
        "webapp_url": get_config("webapp_url"),
        "quick_links": links,
        "has_categories": bool(load_cats()),
        "upscalers": UPSCALERS,
        "compression_levels": COMPRESSION_LEVELS,
        "upscale_targets": UPSCALE_TARGETS,
        "upscale_target": get_config("upscale_target", "2x"),
        "upscale_paused": get_config("upscale_paused", "0") == "1",
    })


# ---- torrents ----

@routes.get("/api/torrents")
async def torrents_list(request):
    cats = load_cats()
    try:
        qb_tors = await _qb_info()
    except Exception:
        invalidate_qb()
        qb_tors = []

    disk_entries = await _thread(_scan_incoming, cats)
    db_sizes = {disk_id: e["size"] for disk_id, e in load_disk_entries().items()}

    qb_by_disk_id: dict[str, object] = {}
    for tor in qb_tors:
        qb_by_disk_id[_qb_disk_id(tor)] = tor

    result = []
    matched_hashes: set[str] = set()
    needs_size: list[tuple[dict, str]] = []

    for de in disk_entries:
        disk_id = de["disk_id"]
        qb_tor = qb_by_disk_id.get(disk_id)
        if qb_tor is not None:
            matched_hashes.add(qb_tor.hash)

        size = db_sizes.get(disk_id, 0)
        if qb_tor is None and size == 0:
            disk_path = os.path.join(INCOMING_DIR, *disk_id.split("/", 1))
            needs_size.append((de, disk_path))

        result.append(_torrent_dict_merged(de, size, qb_tor, cats))

    if needs_size:
        computed_sizes = await asyncio.gather(
            *[_thread(_compute_disk_size, path) for _, path in needs_size]
        )
        size_fixes: list[tuple[str, str, int, int]] = []
        for (de, _), computed in zip(needs_size, computed_sizes):
            size = computed if computed > 0 else -1
            size_fixes.append((de["disk_id"], de["name"], de["cat"]["id"], size))
            for item in result:
                if item["disk_id"] == de["disk_id"] and not item["in_qbittorrent"]:
                    item["size"] = size if size > 0 else None
                    break
        upsert_disk_entries_batch(size_fixes)

    for tor in qb_tors:
        if tor.hash not in matched_hashes:
            d = _torrent_dict(tor, cats)
            d["disk_id"] = f"qb:{tor.hash}"
            result.append(d)

    active_upscales = get_active_upscale_status()
    active_backups = store.get_active_backup_disk_ids()
    upscaled_disk_ids = get_upscaled_disk_ids()
    for item in result:
        st = active_upscales.get(item["disk_id"])
        item["upscaling"] = st is not None
        item["upscale_progress"] = st["cur"] if st else 0
        item["upscale_done"] = st["done"] if st else 0
        item["upscale_total"] = st["total"] if st else 0
        item["has_upscale_results"] = item["disk_id"] in upscaled_disk_ids
        item["has_backup"] = _has_backup(item["disk_id"])
        item["backing_up"] = item["disk_id"] in active_backups

    return web.json_response({
        "torrents": result,
        "has_categories": bool(cats),
    })


@routes.post("/api/torrents")
async def torrent_add(request):
    """Add a magnet (JSON) or a .torrent file (multipart)."""
    cats = load_cats()
    magnet = None
    torrent_bytes = None
    cat_id = None

    if request.content_type and request.content_type.startswith("multipart/"):
        post = await request.post()
        cat_id = post.get("category_id")
        field = post.get("file")
        if field is None:
            return _err("file required")
        torrent_bytes = field.file.read() if hasattr(field, "file") else bytes(field)
    else:
        body = await _json(request)
        magnet = (body.get("magnet") or "").strip() or None
        cat_id = body.get("category_id")
        if not magnet:
            return _err("magnet required")

    if cat_id:
        cat = _find_cat(cat_id)
        if not cat:
            return _err("category not found", status=404)
        save_path = _dl_path(cat)
    elif not cats:
        save_path = "/media/downloads"
    else:
        return _err("category_id required")

    try:
        await _add_to_qb(magnet=magnet, torrent_bytes=torrent_bytes, save_path=save_path)
    except Exception as e:
        return _err(t("add_error", e=e), status=502)
    return web.json_response({"added": True})


@routes.post("/api/torrents/{hash}/delete")
async def torrent_delete(request):
    tor_hash = request.match_info["hash"]
    body = await _json(request)
    delete_files = body.get("delete_files", True)
    cats = load_cats()
    try:
        tor = await _one_torrent(tor_hash)
        if tor:
            await _thread(delete_torrent_links, tor, cats)
        await _thread(
            lambda: qb().torrents_delete(delete_files=delete_files, torrent_hashes=tor_hash)
        )
    except Exception as e:
        return _err(t("add_error", e=e), status=502)
    if tor:
        delete_disk_entry(_qb_disk_id(tor))
    asyncio.create_task(_thread(jf, "POST", "/Library/Refresh"))
    return web.json_response({"deleted": True})


@routes.post("/api/torrents/{hash}/remove-from-client")
async def torrent_remove_from_client(request):
    tor_hash = request.match_info["hash"]
    try:
        await _thread(lambda: qb().torrents_delete(delete_files=False, torrent_hashes=tor_hash))
    except Exception as e:
        return _err(t("qb_error", e=e), status=502)
    return web.json_response({"removed": True})


@routes.post("/api/disk/delete")
async def disk_delete(request):
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    parts = disk_id.split("/")
    if len(parts) != 2 or ".." in parts or not all(parts):
        return _err("invalid disk_id")
    target = os.path.join(INCOMING_DIR, parts[0], parts[1])
    if not os.path.realpath(target).startswith(os.path.realpath(INCOMING_DIR) + os.sep):
        return _err("invalid disk_id")
    cats = load_cats()
    tor = await _resolve_torrent(disk_id)
    if tor is None:
        return _err("invalid disk_id")
    await _thread(delete_torrent_links, tor, cats)
    await _thread(shutil.rmtree, target, True)
    delete_disk_entry(disk_id)
    asyncio.create_task(_thread(jf, "POST", "/Library/Refresh"))
    return web.json_response({"deleted": True})


@routes.post("/api/torrents/category")
async def torrent_move(request):
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    cat_id = body.get("category_id")
    cats = load_cats()
    new_cat = _find_cat(cat_id) if cat_id is not None else None
    if not new_cat:
        return _err("category not found", status=404)
    tor = await _resolve_torrent(disk_id)
    if tor is None:
        return _err("torrent not found", status=404)

    def _relink():
        delete_torrent_links(tor, cats)
        if get_config("rename_mode", "flat") == "pretty":
            process_torrent_rename(tor, cats, target_cat=new_cat)
        else:
            create_flat_hardlinks(tor, cats, target_cat=new_cat)
        jf("POST", "/Library/Refresh")
    await _thread(_relink)

    if getattr(tor, "hash", ""):
        # Live qB torrent: let qBittorrent relocate the download (it re-checks
        # the files at the new location).
        try:
            await _thread(
                lambda: qb().torrents_set_location(torrent_hashes=tor.hash, location=_dl_path(new_cat))
            )
        except Exception as e:
            return _err(t("add_error", e=e), status=502)
    else:
        # Disk-only entry: no client to relocate, so move the content ourselves
        # into the new category's download dir. os.rename/shutil.move keeps inodes
        # on the same filesystem, so the library hardlinks repointed above stay
        # valid. Keep the disk-entry index in sync with the new location.
        new_dir = _dl_path(new_cat)
        new_disk_id = f"{os.path.basename(new_cat['path'].rstrip('/'))}/{tor.name}"

        def _relocate():
            os.makedirs(new_dir, exist_ok=True)
            new_path = os.path.join(new_dir, tor.name)
            if os.path.realpath(tor.content_path) != os.path.realpath(new_path):
                shutil.move(tor.content_path, new_path)

        try:
            await _thread(_relocate)
        except Exception as e:
            return _err(t("add_error", e=e), status=502)

        if new_disk_id != disk_id:
            size = load_disk_entries().get(disk_id, {}).get("size", 0)
            delete_disk_entry(disk_id)
            upsert_disk_entry(new_disk_id, tor.name, new_cat["id"], size)
    return web.json_response({"moved": True})


@routes.post("/api/torrents/structure")
async def torrent_structure(request):
    """mode: pretty | flat | delete — mirrors structure_menu_kb."""
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    mode = body.get("mode")
    if mode not in ("pretty", "flat", "delete"):
        return _err("mode must be pretty|flat|delete")
    cats = load_cats()
    tor = await _resolve_torrent(disk_id)
    if not tor:
        return _err("torrent not found", status=404)

    if mode == "pretty":
        def _f():
            delete_torrent_links(tor, cats)
            linked, pending_ids, errors = process_torrent_rename(tor, cats)
            jf("POST", "/Library/Refresh")
            return linked, pending_ids, errors
        linked, pending_ids, errors = await _thread(_f)
        return web.json_response({
            "mode": "pretty",
            "linked": linked,
            "pending": len(pending_ids),
            "xdev": bool(errors),
        })
    if mode == "flat":
        def _f():
            delete_torrent_links(tor, cats)
            errors = create_flat_hardlinks(tor, cats)
            jf("POST", "/Library/Refresh")
            return errors
        errors = await _thread(_f)
        xdev = bool(errors) and "cross-device" in errors[0].lower()
        return web.json_response({"mode": "flat", "xdev": xdev})
    # delete
    def _f():
        delete_torrent_links(tor, cats)
        jf("POST", "/Library/Refresh")
    await _thread(_f)
    return web.json_response({"mode": "delete", "deleted": True})


# ---- upscale / backup ----
#
# Shared blocking helpers so the Telegram callbacks can reuse the exact same
# logic via _thread — no business logic duplicated between the two surfaces.

def _cat_for(tor, cats: list) -> dict | None:
    slug = os.path.basename(tor.save_path.rstrip("/"))
    return next((c for c in cats if os.path.basename(c["path"].rstrip("/")) == slug), None)


def _cat_id_for(tor, cats: list) -> int | None:
    cat = _cat_for(tor, cats)
    return cat["id"] if cat else None


def _upscale_files(tor) -> list[str]:
    """Sorted list of real video files of a torrent (sidecars excluded). The order
    is the index space the range picker (from/to) and the info endpoint share."""
    files = [f for f in get_video_files(tor.content_path)
             if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS]
    return sorted(files)


def queue_upscale(tor, cats: list, upscaler: str, user_id: int | None,
                  compression: str = "balanced", target: str = "2x",
                  start: int | None = None, end: int | None = None,
                  names: list[str] | None = None) -> tuple[int, str]:
    """Snap the torrent out of qB (keeping files), then queue one upscale job per
    video file to process, skipping files already upscaled.
    Returns (queued_count, disk_id the jobs are keyed on).

    Selection is either an explicit set of basenames (``names`` — used by the
    movie file-picker) or a 1-based ``start``/``end`` range (used by the series
    episode range). When neither is given, every video file is queued."""
    files = _upscale_files(tor)
    if names:
        wanted = set(names)
        files = [f for f in files if os.path.basename(f) in wanted]
    elif start is not None or end is not None:
        lo = max(1, start or 1) - 1
        hi = end if end is not None else len(files)
        files = files[lo:hi]
    disk_id = _qb_disk_id(tor)
    # Clear stale queued/error rows from previous attempts but keep the done rows —
    # they are the "already upscaled" record that lets us skip finished files.
    clear_incomplete_upscale_jobs(disk_id)
    already = get_done_upscale_src_paths(disk_id)
    files = [f for f in files if f not in already]
    if getattr(tor, "hash", ""):
        # Remove from the client but keep the files: the upscaler rewrites them in
        # place, and a live torrent would recheck/error on the changed data.
        qb().torrents_delete(delete_files=False, torrent_hashes=tor.hash)
        cat_id = _cat_id_for(tor, cats)
        if cat_id is not None:
            upsert_disk_entry(disk_id, os.path.basename(tor.content_path.rstrip("/")),
                              cat_id, _compute_disk_size(tor.content_path))
    for src in files:
        add_upscale_job(disk_id, src, upscaler, user_id,
                        compression=compression, target=target)
    return len(files), disk_id


@routes.get("/api/torrents/upscale/info")
async def torrent_upscale_info(request):
    disk_id = (request.query.get("disk_id") or "").strip()
    tor = await _resolve_torrent(disk_id)
    if not tor:
        return _err("torrent not found", status=404)
    files = await _thread(_upscale_files, tor)
    already = get_done_upscale_src_paths(_qb_disk_id(tor) if getattr(tor, "hash", "") else disk_id)
    items = [{"name": os.path.basename(f), "upscaled": f in already} for f in files]
    cat = _cat_for(tor, load_cats())
    is_series = bool(cat) and cat.get("jf_type") == "tvshows"
    return web.json_response({"total": len(items), "files": items, "is_series": is_series})


@routes.get("/api/torrents/upscale/results")
async def torrent_upscale_results(request):
    """Finished-upscale details for a disk: which files, upscaler and settings."""
    disk_id = (request.query.get("disk_id") or "").strip()
    tor = await _resolve_torrent(disk_id)
    key = _qb_disk_id(tor) if tor and getattr(tor, "hash", "") else disk_id
    label = {u["id"]: u["label"] for u in UPSCALERS}
    target_label = {u["id"]: u["label"] for u in UPSCALE_TARGETS}
    results = [{
        "name": os.path.basename(j["src_path"]),
        "upscaler": label.get(j["upscaler"], j["upscaler"] or "?"),
        "compression": j["compression"],
        "target": target_label.get(j["target"], j["target"]),
    } for j in get_done_upscale_jobs(key)]
    return web.json_response({"results": results})


@routes.post("/api/torrents/upscale/cancel")
async def torrent_upscale_cancel(request):
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    tor = await _resolve_torrent(disk_id)
    key = _qb_disk_id(tor) if tor and getattr(tor, "hash", "") else disk_id
    cancel_queued_upscale(key)
    return web.json_response({"cancelled": True})


@routes.post("/api/upscale/pause")
async def upscale_pause(request):
    body = await _json(request)
    set_config("upscale_paused", "1" if body.get("paused") else "0")
    return web.json_response({"paused": bool(body.get("paused"))})


@routes.post("/api/torrents/upscale")
async def torrent_upscale(request):
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    upscaler = body.get("upscaler")
    if upscaler not in UPSCALER_IDS:
        return _err("unknown upscaler")
    compression = body.get("compression") or "balanced"
    if compression not in COMPRESSION_IDS:
        return _err("unknown compression level")
    target = body.get("target") or get_config("upscale_target", "2x")
    if target not in UPSCALE_TARGET_IDS:
        return _err("unknown upscale target")
    start = body.get("start")
    end = body.get("end")
    names = body.get("names")
    if names is not None and not isinstance(names, list):
        return _err("names must be a list")
    cats = load_cats()
    tor = await _resolve_torrent(disk_id)
    if not tor:
        return _err("torrent not found", status=404)
    # Refuse a second run while one is in flight: re-queueing would upscale the
    # already-upscaled files again (2x → 4x) since the originals are gone.
    if _qb_disk_id(tor) in get_active_upscale_status():
        return _err(t("upscale_in_progress"))
    user_id = request.get("user_id")
    queued, new_disk_id = await _thread(
        queue_upscale, tor, cats, upscaler, user_id, compression, target, start, end, names)
    if not queued:
        return _err("no video files to upscale")
    return web.json_response({"queued": queued, "disk_id": new_disk_id})


def _run_backup(src: str, dst: str, key: str):
    """Copy into a `.partial` sibling, then atomically rename into place, so a
    half-finished copy is never seen as a valid backup (`_has_backup` checks dst).
    Runs in a daemon thread: a 157 GB copytree can't finish inside the tunnel
    timeout, so the request returns immediately and this reaps in the background.
    The result (done/error) is recorded in `backup_jobs`; `job_check_backup` turns
    it into a persistent Telegram notification."""
    partial = f"{dst}.partial"
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.lexists(partial):
            _rm_in_background(partial)
        # Mirror the source layout exactly (dir → dir, file → file) so restore,
        # which branches on isdir(backup), stays consistent.
        if os.path.isdir(src):
            shutil.copytree(src, partial)
        else:
            shutil.copy2(src, partial)
        if os.path.lexists(dst):
            _rm_in_background(dst)
        os.replace(partial, dst)
        store.finish_backup_job(key)
    except Exception as e:
        shutil.rmtree(partial, ignore_errors=True)
        store.finish_backup_job(key, error=str(e)[:500])


@routes.post("/api/torrents/backup")
async def torrent_backup(request):
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    tor = await _resolve_torrent(disk_id)
    if not tor:
        return _err("torrent not found", status=404)
    # Key the backup on the canonical <slug>/<name>, not a raw qb:<hash> id.
    key = _qb_disk_id(tor) if getattr(tor, "hash", "") else disk_id
    dst = _backup_path(key)
    if not dst:
        return _err("invalid disk_id")
    if key in store.get_active_backup_disk_ids():
        return web.json_response({"backing_up": True})
    store.start_backup_job(key, kb.short_name(tor.name), request.get("user_id"))
    threading.Thread(target=_run_backup, args=(tor.content_path, dst, key),
                     daemon=True).start()
    return web.json_response({"backing_up": True})


@routes.post("/api/torrents/backup/restore")
async def torrent_backup_restore(request):
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    backup = _backup_path(disk_id)
    if not backup or not os.path.exists(backup):
        return _err("backup not found", status=404)
    tor = await _resolve_torrent(disk_id)
    if tor is None:
        return _err("torrent not found", status=404)
    cats = load_cats()

    def _f():
        dst = tor.content_path
        # Copy the backup to a temp sibling first, then swap it in — never delete
        # the live content until the fresh copy is fully in place, so a failed
        # copy (or a crash in the relink below) can't leave the source gone.
        tmp = dst.rstrip("/") + ".restore-tmp"
        if os.path.isdir(tmp):
            shutil.rmtree(tmp)
        elif os.path.lexists(tmp):
            os.remove(tmp)
        if os.path.isdir(backup):
            shutil.copytree(backup, tmp)
        else:
            shutil.copy2(backup, tmp)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        elif os.path.lexists(dst):
            os.remove(dst)
        os.rename(tmp, dst)
        # The restored source is pristine again: drop every upscale record (done +
        # stale jobs) so a fresh full range can be queued.
        delete_upscale_jobs_by_disk_id(disk_id)
        store.update_disk_entry_size(disk_id, _compute_disk_size(dst))
        delete_torrent_links(tor, cats)
        if get_config("rename_mode", "flat") == "pretty":
            process_torrent_rename(tor, cats)
        else:
            create_flat_hardlinks(tor, cats)
        jf("POST", "/Library/Refresh")

    await _thread(_f)
    return web.json_response({"restored": True})


def _rm_in_background(path: str):
    """Make a (possibly multi-GB) tree vanish immediately, then reap the bytes off
    the request path. Renaming to a sibling is atomic and instant, so the caller
    can return before the slow rmtree runs — otherwise a large backup delete blows
    past the Cloudflare tunnel timeout (524)."""
    if not os.path.lexists(path):
        return
    trash = f"{path}.trash-{os.getpid()}-{time.time_ns()}"
    try:
        os.rename(path, trash)
    except OSError:
        trash = path  # different fs / rename failed: fall back to deleting in place

    def _reap():
        if os.path.isdir(trash) and not os.path.islink(trash):
            shutil.rmtree(trash, ignore_errors=True)
        else:
            try:
                os.remove(trash)
            except OSError:
                pass
    threading.Thread(target=_reap, daemon=True).start()


@routes.post("/api/torrents/backup/delete")
async def torrent_backup_delete(request):
    body = await _json(request)
    disk_id = (body.get("disk_id") or "").strip()
    dst = _backup_path(disk_id)
    if not dst:
        return _err("invalid disk_id")
    _rm_in_background(dst)
    return web.json_response({"deleted": True})


# ---- status / scan ----

_DOWNLOADING = {"downloading", "stalledDL", "checkingDL", "forcedDL", "metaDL", "queuedDL"}
_SEEDING = {"uploading", "stalledUP", "checkingUP", "forcedUP", "queuedUP"}


@routes.get("/api/status")
async def status(request):
    try:
        info = await _thread(lambda: qb().transfer_info())
    except Exception:
        invalidate_qb()  # force re-login on the next poll
        return web.json_response({"connected": False})

    jf_connected = await _thread(jf, "GET", "/System/Info") is not None

    try:
        tors = await _qb_info()
        torrents_total = len(tors)
        torrents_downloading = sum(1 for t in tors if t.state in _DOWNLOADING)
        torrents_seeding = sum(1 for t in tors if t.state in _SEEDING)
    except Exception:
        torrents_total = torrents_downloading = torrents_seeding = 0

    # free_space_on_disk is NOT part of /transfer/info (newer qBittorrent dropped
    # it there); it lives in /sync/maindata → server_state. Fetch it separately and
    # never let a missing field break the whole status response.
    try:
        server_state = (await _thread(lambda: qb().sync_maindata())).get("server_state", {})
        # qBittorrent reports -1 when it can't determine free space; show 0, not a
        # negative byte count in the UI.
        free_space = max(0, server_state.get("free_space_on_disk", 0))
        alt_speed_enabled = bool(server_state.get("use_alt_speed_limits", False))
        dl_rate_limit = server_state.get("dl_rate_limit", 0)
        up_rate_limit = server_state.get("up_rate_limit", 0)
    except Exception:
        free_space = 0
        alt_speed_enabled = False
        dl_rate_limit = 0
        up_rate_limit = 0

    try:
        disk = shutil.disk_usage("/media")
        total_space = disk.total
    except Exception:
        total_space = 0

    return web.json_response({
        "connected": True,
        "jf_connected": jf_connected,
        "dl": getattr(info, "dl_info_speed", 0),
        "ul": getattr(info, "up_info_speed", 0),
        "dl_data": getattr(info, "dl_info_data", 0),
        "ul_data": getattr(info, "up_info_data", 0),
        "free_space": free_space,
        "total_space": total_space,
        "torrents_total": torrents_total,
        "torrents_downloading": torrents_downloading,
        "torrents_seeding": torrents_seeding,
        "alt_speed_enabled": alt_speed_enabled,
        "dl_rate_limit": dl_rate_limit,
        "up_rate_limit": up_rate_limit,
    })


@routes.post("/api/qb/toggle_alt_speed")
async def toggle_alt_speed(request):
    try:
        await _thread(lambda: qb().transfer_toggle_speed_limits_mode())
        server_state = (await _thread(lambda: qb().sync_maindata())).get("server_state", {})
        alt_speed_enabled = bool(server_state.get("use_alt_speed_limits", False))
        return web.json_response({"alt_speed_enabled": alt_speed_enabled})
    except Exception as e:
        return _err(t("qb_error", e=e), status=502)


@routes.post("/api/scan")
async def scan(request):
    ok = await _thread(jf, "POST", "/Library/Refresh")
    return web.json_response({"ok": bool(ok)})


_SEARCH_CACHE_TTL = 300  # seconds

# ---- search ----

@routes.get("/api/search")
async def search(request):
    query = (request.query.get("q") or "").strip()
    if not query:
        return _err("q required")
    if not jackett_get_api_key():
        return _err(t("jackett_no_key"), status=503)
    try:
        page = max(1, int(request.query.get("page") or 1))
        page_size = max(1, min(50, int(request.query.get("page_size") or 10)))
    except ValueError:
        page, page_size = 1, 10

    cache = request.app.setdefault("_search_cache", {})
    cached = cache.get(query)
    if cached and time.monotonic() - cached["ts"] < _SEARCH_CACHE_TTL:
        all_results = cached["results"]
    else:
        all_results = await _thread(jackett_search, query)
        if all_results is None:
            return _err(t("jackett_error"), status=502)
        cache[query] = {"results": all_results, "ts": time.monotonic()}

    total = len(all_results)
    offset = (page - 1) * page_size
    results = all_results[offset:offset + page_size]
    return web.json_response({"query": query, "results": results, "total": total, "page": page, "page_size": page_size})


@routes.post("/api/search/add")
async def search_add(request):
    """Add a chosen search result. Body: {magnet? , link?, category_id?}."""
    body = await _json(request)
    magnet = body.get("magnet")
    link = body.get("link")
    cat_id = body.get("category_id")
    cats = load_cats()

    if cat_id:
        cat = _find_cat(cat_id)
        if not cat:
            return _err("category not found", status=404)
        save_path = _dl_path(cat)
    elif not cats:
        save_path = "/media/downloads"
    else:
        return _err("category_id required")

    if magnet:
        try:
            await _add_to_qb(magnet=magnet, save_path=save_path)
        except Exception as e:
            return _err(t("add_error", e=e), status=502)
        return web.json_response({"added": True})

    if link:
        data = await _thread(jackett_download_torrent, link)
        if data is None:
            return _err(t("jackett_error"), status=502)
        try:
            await _add_to_qb(torrent_bytes=data, save_path=save_path)
        except Exception as e:
            return _err(t("add_error", e=e), status=502)
        return web.json_response({"added": True})

    return _err("magnet or link required")


# ---- categories ----

@routes.get("/api/categories")
async def categories_list(request):
    return web.json_response({"categories": load_cats()})


@routes.post("/api/categories")
async def category_create(request):
    body = await _json(request)
    name = (body.get("name") or "").strip()
    jf_type = body.get("jf_type")
    if not name:
        return _err("name required")
    if jf_type not in ("movies", "tvshows", "music", "mixed"):
        return _err("jf_type must be movies|tvshows|music|mixed")

    raw_slug = (body.get("slug") or "").strip() or name
    slug = re.sub(r"[^\w\s]", "", raw_slug, flags=re.UNICODE).strip().lower().replace(" ", "_")
    path = f"/media/{slug}" if slug else "/media"

    def _f():
        for d in (path, _dl_path({"path": path})):
            os.makedirs(d, exist_ok=True)
            try:
                os.chown(d, 1000, 1000)
            except Exception:
                os.chmod(d, 0o777)
        cats = load_cats()
        cats.append({"name": name, "path": path, "jf_type": jf_type})
        save_cats(cats)
        jf_add_library(name, path, jf_type)
    await _thread(_f)
    return web.json_response({"categories": load_cats()})


@routes.patch("/api/categories/{id}")
async def category_rename(request):
    cat_id = int(request.match_info["id"])
    body = await _json(request)
    name = (body.get("name") or "").strip()
    if not name:
        return _err("name required")
    cats = load_cats()
    cat = next((c for c in cats if c["id"] == cat_id), None)
    if not cat:
        return _err("category not found", status=404)
    cat["name"] = name
    save_cats(cats)
    return web.json_response({"categories": load_cats()})


@routes.delete("/api/categories/{id}")
async def category_delete(request):
    cat_id = int(request.match_info["id"])
    cats = load_cats()
    cat = next((c for c in cats if c["id"] == cat_id), None)
    if cat:
        save_cats([c for c in cats if c["id"] != cat_id])
        await _thread(jf_remove_library, cat["name"])
    return web.json_response({"categories": load_cats()})


# ---- settings ----

@routes.get("/api/settings")
async def settings_get(request):
    user, _pass = get_creds()
    return web.json_response({
        "rename_mode": get_config("rename_mode", "flat"),
        "upscale_target": get_config("upscale_target", "2x"),
        "lang": get_config("lang", "ru"),
        "qbittorrent": {
            "user": user,
            "is_perm": bool(get_config("qb_pass_is_perm")),
            "status": get_qb_status(),
        },
        "jackett": {
            "has_key": bool(jackett_get_api_key()),
            "has_password": jackett_has_password(),
        },
        "jellyfin": {
            "has_key": bool(get_config("jellyfin_api_key")),
        },
    })


@routes.post("/api/settings/rename_mode")
async def settings_rename_mode(request):
    body = await _json(request)
    mode = body.get("mode")
    if mode not in ("flat", "pretty"):
        return _err("mode must be flat|pretty")
    set_config("rename_mode", mode)
    return web.json_response({"rename_mode": mode})


@routes.post("/api/settings/upscale_target")
async def settings_upscale_target(request):
    body = await _json(request)
    target = body.get("target")
    if target not in UPSCALE_TARGET_IDS:
        return _err("unknown upscale target")
    set_config("upscale_target", target)
    return web.json_response({"upscale_target": target})


@routes.post("/api/settings/language")
async def settings_language(request):
    body = await _json(request)
    lang = body.get("lang")
    if lang not in ("ru", "en"):
        return _err("lang must be ru|en")
    set_lang(lang)
    return web.json_response({"lang": lang})


@routes.post("/api/settings/qb_password")
async def settings_qb_password(request):
    body = await _json(request)
    password = body.get("password") or ""
    if not password:
        return _err("password required")
    result = await _thread(qb_set_password, password)
    if result is True:
        set_config("qb_pass", password)
        set_config("qb_pass_is_perm", "1")
        invalidate_qb()
        set_qb_status("unknown")
        return web.json_response({"ok": True})
    return _err(f"{t('qb_pass_error')}: {result}", status=502)


@routes.post("/api/settings/qb/fetch_temp")
async def settings_qb_fetch_temp(request):
    temp = await _thread(qb_temp_password)
    if not temp:
        return web.json_response({"found": False})
    set_config("qb_pass", temp)
    set_config("qb_pass_is_perm", "")
    set_qb_status("unknown")
    invalidate_qb()
    return web.json_response({"found": True, "password": temp})


@routes.post("/api/settings/qb/restart")
async def settings_qb_restart(request):
    ok = await _thread(qb_restart)
    if ok:
        set_qb_status("unknown")
        invalidate_qb()
    return web.json_response({"ok": bool(ok)})


@routes.post("/api/settings/jackett_password")
async def settings_jackett_password(request):
    body = await _json(request)
    password = body.get("password") or ""  # empty removes the password
    result = await _thread(jackett_set_password, password)
    if result is True:
        return web.json_response({"ok": True, "has_password": bool(password)})
    return _err(f"{t('jackett_pass_error')}: {result}", status=502)


@routes.get("/api/settings/jellyfin/users")
async def jellyfin_users_list(request):
    users = await _thread(jf, "GET", "/Users") or []
    return web.json_response({
        "users": [{"id": u["Id"], "name": u["Name"]} for u in users],
    })


@routes.post("/api/settings/jellyfin/users")
async def jellyfin_user_create(request):
    body = await _json(request)
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    if not name or not password:
        return _err("name and password required")

    def _f():
        user = jf("POST", "/Users/New", {"Name": name})
        if isinstance(user, dict) and "Id" in user:
            jf("POST", f"/Users/{user['Id']}/Password", {"NewPw": password})
            return user
        return None
    user = await _thread(_f)
    if not user:
        return _err(t("jf_user_error"), status=502)
    return web.json_response({"created": {"id": user["Id"], "name": name}})


@routes.delete("/api/settings/jellyfin/users/{id}")
async def jellyfin_user_delete(request):
    user_id = request.match_info["id"]
    ok = await _thread(jf, "DELETE", f"/Users/{user_id}")
    if ok is None:
        return _err(t("jf_user_error"), status=502)
    return web.json_response({"deleted": True})


# ---- update ----

@routes.get("/api/update")
async def update_get(request):
    latest = await _thread(gh_latest_release_tag)
    channel = current_channel()
    return web.json_response({
        "current": APP_VERSION,
        "latest": latest,
        "has_update": bool(latest and latest != APP_VERSION and channel == "stable"),
        "channel": channel,
    })


@routes.post("/api/update")
async def update_post(request):
    """Blue/green swap ONLY the bot container to `tag` (stable | edge).

    Fire-and-forget: on success `self_update` retires this container, killing the
    process mid-flight, so the client should treat a dropped connection after
    `started` as success and reconnect once the bot is back. Only the bot is
    touched — qBittorrent/Jellyfin/cloudflared are never recreated. Infra changes
    go through update.sh on the host.
    """
    body = await _json(request)
    tag = body.get("tag", "stable")
    if tag not in ("stable", "edge"):
        return _err("tag must be stable|edge")
    set_config("update_pending", "1")

    async def _run():
        # On success this never returns (the process is replaced); the fresh
        # bot's _post_init clears the flag and notifies. On failure we clear it.
        await _thread(self_update, tag)
        set_config("update_pending", "")
    asyncio.create_task(_run())
    return web.json_response({"started": True, "tag": tag})
