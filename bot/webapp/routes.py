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
import time

from aiohttp import web

from config import (
    ICONS, INCOMING_DIR, APP_VERSION, current_channel,
    QB_PORT, JF_PORT, JACKETT_PORT,
)
import store
from store import (
    t, load_cats, save_cats, set_lang, set_config, get_config,
    get_creds, get_qb_status, set_qb_status,
    load_disk_entries, upsert_disk_entry, upsert_disk_entries_batch, delete_disk_entry,
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
    delete_torrent_links, delete_all_cat_contents,
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
    basename = os.path.basename(tor.save_path.rstrip("/"))
    return {
        "disk_id": f"{basename}/{tor.name}",
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
        basename = os.path.basename(tor.save_path.rstrip("/"))
        qb_by_disk_id[f"{basename}/{tor.name}"] = tor

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
        basename = os.path.basename(tor.save_path.rstrip("/"))
        delete_disk_entry(f"{basename}/{tor.name}")
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
    all_tors = await _qb_info()
    tor = next(
        (t for t in all_tors if t.name == parts[1] and os.path.basename(t.save_path.rstrip("/")) == parts[0]),
        None,
    )
    if tor is None:
        # Torrent no longer tracked by qB: synthesise a minimal stand-in so
        # delete_torrent_links can still locate and remove the library hardlinks.
        class _Stub:
            pass
        tor = _Stub()
        tor.name = parts[1]
        tor.save_path = os.path.join(INCOMING_DIR, parts[0]) + "/"
        tor.content_path = target
        tor.hash = ""
    await _thread(delete_torrent_links, tor, cats)
    await _thread(shutil.rmtree, target, True)
    delete_disk_entry(disk_id)
    asyncio.create_task(_thread(jf, "POST", "/Library/Refresh"))
    return web.json_response({"deleted": True})


@routes.post("/api/torrents/{hash}/category")
async def torrent_move(request):
    tor_hash = request.match_info["hash"]
    body = await _json(request)
    cat_id = body.get("category_id")
    cats = load_cats()
    new_cat = _find_cat(cat_id) if cat_id is not None else None
    if not new_cat:
        return _err("category not found", status=404)
    try:
        tor = await _one_torrent(tor_hash)
    except Exception as e:
        return _err(t("qb_error", e=e), status=502)
    if tor:
        def _relink():
            delete_torrent_links(tor, cats)
            if get_config("rename_mode", "flat") == "pretty":
                process_torrent_rename(tor, cats, target_cat=new_cat)
            else:
                create_flat_hardlinks(tor, cats, target_cat=new_cat)
            jf("POST", "/Library/Refresh")
        await _thread(_relink)
    try:
        await _thread(
            lambda: qb().torrents_set_location(torrent_hashes=tor_hash, location=_dl_path(new_cat))
        )
    except Exception as e:
        return _err(t("add_error", e=e), status=502)
    return web.json_response({"moved": True})


@routes.post("/api/torrents/{hash}/structure")
async def torrent_structure(request):
    """mode: pretty | flat | delete — mirrors structure_menu_kb."""
    tor_hash = request.match_info["hash"]
    body = await _json(request)
    mode = body.get("mode")
    if mode not in ("pretty", "flat", "delete"):
        return _err("mode must be pretty|flat|delete")
    cats = load_cats()
    try:
        tor = await _one_torrent(tor_hash)
    except Exception as e:
        return _err(t("qb_error", e=e), status=502)
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
    except Exception:
        free_space = 0

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
    })


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
