import errno
import logging
import os
import re
import shutil

from guessit import guessit
from config import INCOMING_DIR

log = logging.getLogger(__name__)

MEDIA_EXTENSIONS = {
    # video
    '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.ts', '.m2ts', '.flv', '.webm',
    # subtitles
    '.srt', '.ass', '.ssa', '.sub', '.idx', '.vtt', '.sup', '.smi',
    # external audio tracks
    '.mka', '.ac3', '.dts', '.eac3', '.truehd',
}


def parse_filename(filename: str, jf_type: str) -> dict | None:
    stem = os.path.splitext(filename)[0]
    guess = guessit(filename)

    if jf_type == "tvshows":
        title = guess.get("title")
        season = guess.get("season")
        episode = guess.get("episode")
        if isinstance(episode, list):
            episode = episode[0]

        # fallback: bare number at end, below 480 to avoid resolution/year false positives
        if title and (season is None or episode is None):
            m = re.search(r'[\s_.-](\d{1,3})$', stem)
            if m:
                n = int(m.group(1))
                if n < 480:
                    if season is None:
                        season = 1
                    if episode is None:
                        episode = n

        if title and season is not None and episode is not None:
            return {"title": str(title), "season": int(season), "episode": int(episode)}
        return None

    if jf_type == "movies":
        title = guess.get("title")
        year = guess.get("year")
        if title:
            return {"title": str(title), "year": int(year) if year else None}
        return None

    return None


def build_target_path(cat: dict, parsed: dict, src_filename: str) -> str:
    ext = os.path.splitext(src_filename)[1].lower()
    cat_path = cat["path"]

    if cat["jf_type"] == "tvshows":
        title = parsed["title"]
        s, e = parsed["season"], parsed["episode"]
        fname = f"{title} - S{s:02d}E{e:02d}{ext}"
        return os.path.join(cat_path, title, f"Season {s:02d}", fname)

    if cat["jf_type"] == "movies":
        title = parsed["title"]
        folder = f"{title} ({parsed['year']})" if parsed.get("year") else title
        return os.path.join(cat_path, folder, f"{folder}{ext}")

    return os.path.join(cat_path, src_filename)


def parse_manual_input(jf_type: str, manual_input: str, src_filename: str) -> dict | None:
    """Parse user-supplied manual input. Returns parsed dict or None on bad format."""
    text = manual_input.strip()

    if jf_type == "tvshows":
        m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', text)
        if not m:
            return None
        season = int(m.group(1))
        episode = int(m.group(2))
        title_part = text[:m.start()].strip(" -_")
        if not title_part:
            guess = guessit(src_filename)
            title_part = str(guess.get("title", "Unknown"))
        return {"title": title_part, "season": season, "episode": episode}

    if jf_type == "movies":
        # "Title (Year)" or "Title Year" or just "Title"
        m = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', text)
        if m:
            return {"title": m.group(1).strip(), "year": int(m.group(2))}
        m = re.match(r'^(.+?)\s+(\d{4})\s*$', text)
        if m:
            return {"title": m.group(1).strip(), "year": int(m.group(2))}
        return {"title": text, "year": None}

    return None


def create_hardlink(src: str, dst: str):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        return
    os.link(src, dst)


def _cleanup_empty_dirs(path: str, stop_at: str):
    d = os.path.dirname(path)
    while d and d != stop_at and os.path.isdir(d) and not os.listdir(d):
        try:
            os.rmdir(d)
        except OSError:
            break
        d = os.path.dirname(d)


def get_video_files(path: str) -> list[str]:
    if os.path.isfile(path):
        return [path] if os.path.splitext(path)[1].lower() in MEDIA_EXTENSIONS else []
    files = []
    for root, _, names in os.walk(path):
        for name in names:
            if os.path.splitext(name)[1].lower() in MEDIA_EXTENSIONS:
                files.append(os.path.join(root, name))
    return sorted(files)


def _find_cat(tor, cats: list[dict]) -> dict | None:
    save_path = tor.save_path.rstrip("/")
    return next(
        (c for c in cats if save_path in (
            c["path"].rstrip("/"),
            os.path.join(INCOMING_DIR, os.path.basename(c["path"])).rstrip("/"),
        )),
        None,
    )


def _try_unlink(path: str, stop_at: str):
    if os.path.exists(path):
        try:
            os.unlink(path)
            _cleanup_empty_dirs(path, stop_at)
        except OSError as e:
            log.warning("Could not remove %s: %s", path, e)


def process_torrent_rename(tor, cats: list[dict]) -> tuple[int, list[int], list[str]]:
    """Create pretty hardlinks for parseable files, queue the rest as pending_manual.
    Returns (linked_count, pending_job_ids, xdev_errors)."""
    from store import add_rename_job

    cat = _find_cat(tor, cats)
    if not cat:
        log.debug("Torrent %s: no matching category", tor.hash)
        return 0, [], []
    if cat["jf_type"] not in ("tvshows", "movies"):
        log.debug("Torrent %s: jf_type=%s not supported for rename", tor.hash, cat["jf_type"])
        return 0, [], []

    content_path = getattr(tor, "content_path", None) or os.path.join(tor.save_path, tor.name)
    linked, pending_ids, errors = 0, [], []

    for src_path in get_video_files(content_path):
        filename = os.path.basename(src_path)
        parsed = parse_filename(filename, cat["jf_type"])
        if parsed:
            dst_path = build_target_path(cat, parsed, filename)
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
        else:
            pending_ids.append(add_rename_job(tor.hash, src_path, cat["path"], cat["jf_type"]))
            log.info("Cannot parse %s, queued pending_manual", filename)

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


def create_flat_hardlinks(tor, cats: list[dict]) -> list[str]:
    """Flat hardlinks preserving the torrent's original file structure. Returns errors."""
    cat = _find_cat(tor, cats)
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
    """Delete all content directories created for a torrent."""
    from store import delete_rename_jobs_by_hash

    cat = _find_cat(tor, cats)
    if not cat:
        delete_rename_jobs_by_hash(tor.hash)
        return

    save_path = tor.save_path.rstrip("/")
    content_path = getattr(tor, "content_path", None) or os.path.join(tor.save_path, tor.name)
    incoming_cat = os.path.join(INCOMING_DIR, os.path.basename(cat["path"]))
    dirs_to_delete: set[str] = set()

    for src_path in get_video_files(content_path):
        filename = os.path.basename(src_path)
        # pretty: collect parent dir of each linked file (e.g. Show/Season 01)
        if cat["jf_type"] in ("tvshows", "movies"):
            parsed = parse_filename(filename, cat["jf_type"])
            if parsed:
                d = os.path.dirname(build_target_path(cat, parsed, filename))
                if d != cat["path"]:
                    dirs_to_delete.add(d)
        # flat: collect top-level subdir under cat path
        base = incoming_cat if src_path.startswith(incoming_cat + os.sep) else cat["path"]
        rel_parts = os.path.relpath(src_path, base).split(os.sep)
        if len(rel_parts) > 1:
            dirs_to_delete.add(os.path.join(cat["path"], rel_parts[0]))

    # delete deepest dirs first so parents are cleaned up correctly
    for d in sorted(dirs_to_delete, key=lambda p: p.count(os.sep), reverse=True):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            log.info("Removed: %s", d)
        # remove now-empty parent dirs up to cat root
        parent = os.path.dirname(d)
        while parent != cat["path"] and os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
            parent = os.path.dirname(parent)

    delete_rename_jobs_by_hash(tor.hash)


def delete_all_cat_contents(cats: list[dict]):
    """Delete all contents of every category directory."""
    from store import delete_all_rename_jobs

    for cat in cats:
        cat_path = cat["path"]
        if not os.path.isdir(cat_path):
            continue
        for item in os.listdir(cat_path):
            item_path = os.path.join(cat_path, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.unlink(item_path)
                log.info("Removed: %s", item_path)
            except OSError as e:
                log.warning("Could not remove %s: %s", item_path, e)
    delete_all_rename_jobs()
