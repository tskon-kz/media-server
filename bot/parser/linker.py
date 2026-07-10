"""High-level operations: turn a finished torrent into a Jellyfin library layout."""

import errno
import logging
import os
import shutil

from config import INCOMING_DIR
from store import add_rename_job, delete_rename_jobs_by_hash

from .constants import SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS
from .filenames import tor_fallback_title, parse_filename, is_extra
from .naming import (
    build_target_path, sidecar_label, season_episode_widths, dedupe, extras_base_dir,
)
from .fsops import get_video_files, find_cat, create_hardlink

log = logging.getLogger(__name__)


def count_parseable_files(tor, cats: list[dict]) -> tuple[int, int]:
    """Returns (parseable, unparseable) counts without creating any links."""
    cat = find_cat(tor, cats)
    if not cat or cat["jf_type"] not in ("tvshows", "movies"):
        return 0, 0
    content_path = getattr(tor, "content_path", None) or os.path.join(tor.save_path, tor.name)
    fallback_title = tor_fallback_title(tor)
    parseable = unparseable = 0
    for src_path in get_video_files(content_path):
        if is_extra(src_path, content_path):
            continue  # extras aren't episodes, don't count against parseability
        if parse_filename(os.path.basename(src_path), cat["jf_type"], fallback_title):
            parseable += 1
        else:
            unparseable += 1
    return parseable, unparseable


def process_torrent_rename(tor, cats: list[dict], *, target_cat: dict | None = None) -> tuple[int, list[int], list[str]]:
    """Create pretty hardlinks for parseable files, queue the rest as pending_manual.
    Returns (linked_count, pending_job_ids, xdev_errors)."""
    cat = target_cat or find_cat(tor, cats)
    if not cat:
        log.debug("Torrent %s: no matching category", tor.hash)
        return 0, [], []
    if cat["jf_type"] not in ("tvshows", "movies"):
        log.debug("Torrent %s: jf_type=%s not supported for rename", tor.hash, cat["jf_type"])
        return 0, [], []

    content_path = getattr(tor, "content_path", None) or os.path.join(tor.save_path, tor.name)
    fallback_title = tor_fallback_title(tor)
    linked, pending_ids, errors = 0, [], []

    # Structure-first: split off video extras (creditless OP/ED, PVs, specials)
    # by their folder context before parsing, so they can't be mistaken for
    # episodes and overwrite real ones.
    all_files = get_video_files(content_path)
    extra_files = [f for f in all_files if is_extra(f, content_path)]
    main_files = [f for f in all_files if f not in set(extra_files)]

    # First pass: parse everything so episode-number width can be decided per
    # season (a 220-episode season needs E001, a 24-episode one E01).
    parsed_files = []
    for src_path in main_files:
        filename = os.path.basename(src_path)
        parsed = parse_filename(filename, cat["jf_type"], fallback_title)
        if parsed:
            parsed_files.append((src_path, filename, parsed))
        else:
            pending_ids.append(add_rename_job(tor.hash, src_path, cat["path"], cat["jf_type"]))
            log.info("Cannot parse %s, queued pending_manual", filename)

    widths = season_episode_widths(parsed_files) if cat["jf_type"] == "tvshows" else {}
    used: set = set()

    # Second pass: link with the right episode width; give sidecars a
    # language/group suffix so multiple dubs/subs per episode all survive.
    for src_path, filename, parsed in parsed_files:
        ext = os.path.splitext(filename)[1].lower()
        # Movies have no season; widths is empty for them anyway, so fall back to
        # the default width instead of KeyError-ing on the missing 'season' key.
        width = widths.get((parsed.get("title"), parsed.get("season")), 2)
        is_sidecar = ext in SIDECAR_EXTENSIONS
        label = sidecar_label(src_path, content_path, filename) if is_sidecar else ""
        dst_path = build_target_path(cat, parsed, filename, episode_width=width, label=label)
        if is_sidecar:
            dst_path = dedupe(dst_path, used)
        used.add(dst_path)
        try:
            create_hardlink(src_path, dst_path)
            linked += 1
            log.info("Hardlinked: %s -> %s", src_path, dst_path)
        except OSError as e:
            if e.errno == errno.EXDEV:
                errors.append(str(e))
                log.error("Cross-device: %s", src_path)
            else:
                log.error("Hardlink failed: %s", e)
                pending_ids.append(add_rename_job(tor.hash, src_path, cat["path"], cat["jf_type"]))

    # Extras keep their original name under <Show>/extras (Jellyfin's Extras tab).
    if extra_files:
        extras_dir = os.path.join(extras_base_dir(cat, tor, fallback_title, parsed_files), "extras")
        for src_path in extra_files:
            dst_path = os.path.join(extras_dir, os.path.basename(src_path))
            try:
                create_hardlink(src_path, dst_path)
                linked += 1
                log.info("Extra hardlinked: %s -> %s", src_path, dst_path)
            except OSError as e:
                errors.append(str(e))
                log.error("Extra hardlink failed %s: %s", src_path, e)

    return linked, pending_ids, errors


def create_flat_hardlink_for_job(job: dict) -> str | None:
    """Flat hardlink for one pending job. Returns dst_path on success, None on error."""
    incoming_cat = os.path.join(INCOMING_DIR, os.path.basename(job["cat_path"]))
    base = incoming_cat if job["src_path"].startswith(incoming_cat + os.sep) else job["cat_path"]
    dst_path = os.path.join(job["cat_path"], os.path.relpath(job["src_path"], base))
    try:
        create_hardlink(job["src_path"], dst_path)
        log.info("Flat hardlink for job %d: %s -> %s", job["id"], job["src_path"], dst_path)
        return dst_path
    except OSError as e:
        log.error("Flat hardlink for job %d failed: %s", job["id"], e)
        return None


def create_flat_hardlinks(tor, cats: list[dict], *, target_cat: dict | None = None) -> list[str]:
    """Flat hardlinks preserving the torrent's original file structure. Returns errors."""
    cat = target_cat or find_cat(tor, cats)
    if not cat:
        return []

    save_path = tor.save_path.rstrip("/")
    content_path = getattr(tor, "content_path", None) or os.path.join(tor.save_path, tor.name)
    errors = []

    for src_path in get_video_files(content_path):
        dst_path = os.path.join(cat["path"], os.path.relpath(src_path, save_path))
        try:
            create_hardlink(src_path, dst_path)
            log.info("Flat hardlink: %s -> %s", src_path, dst_path)
        except OSError as e:
            log.error("Flat hardlink failed %s: %s", src_path, e)
            errors.append(str(e))

    return errors


def delete_torrent_links(tor, cats: list[dict]):
    """Delete all content directories created for a torrent in its current category."""
    cur_cat = find_cat(tor, cats)
    if not cur_cat:
        delete_rename_jobs_by_hash(tor.hash)
        return
    content_path = getattr(tor, "content_path", None) or os.path.join(tor.save_path, tor.name)
    src_files = get_video_files(content_path)
    fallback_title = tor_fallback_title(tor)

    cat = cur_cat
    incoming_cat = os.path.join(INCOMING_DIR, os.path.basename(cat["path"]))
    dirs_to_delete: set[str] = set()
    first_parsed = None
    has_extra = False

    for src_path in src_files:
        filename = os.path.basename(src_path)
        extra = is_extra(src_path, content_path)
        has_extra = has_extra or extra
        if cat["jf_type"] in ("tvshows", "movies") and not extra:
            parsed = parse_filename(filename, cat["jf_type"], fallback_title)
            if parsed:
                if first_parsed is None:
                    first_parsed = parsed
                d = os.path.dirname(build_target_path(cat, parsed, filename))
                if d != cat["path"]:
                    dirs_to_delete.add(d)
        base = incoming_cat if src_path.startswith(incoming_cat + os.sep) else cat["path"]
        rel_parts = os.path.relpath(src_path, base).split(os.sep)
        if len(rel_parts) > 1:
            dirs_to_delete.add(os.path.join(cat["path"], rel_parts[0]))

    if has_extra and cat["jf_type"] in ("tvshows", "movies"):
        pf = [(None, None, first_parsed)] if first_parsed else []
        dirs_to_delete.add(os.path.join(extras_base_dir(cat, tor, fallback_title, pf), "extras"))

    for d in sorted(dirs_to_delete, key=lambda p: p.count(os.sep), reverse=True):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            log.info("Removed: %s", d)
        parent = os.path.dirname(d)
        while parent != cat["path"] and os.path.isdir(parent):
            try:
                entries = os.listdir(parent)
            except OSError:
                break
            if any(
                os.path.isdir(os.path.join(parent, e))
                or os.path.splitext(e)[1].lower() in MEDIA_EXTENSIONS
                for e in entries
            ):
                break
            try:
                shutil.rmtree(parent)
                log.info("Removed: %s", parent)
            except OSError as e:
                log.warning("Could not remove %s: %s", parent, e)
                break
            parent = os.path.dirname(parent)

    delete_rename_jobs_by_hash(tor.hash)
