import errno
import logging
import os
import re

from guessit import guessit

log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.ts', '.m2ts', '.flv', '.webm'}


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
        return [path] if os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS else []
    files = []
    for root, _, names in os.walk(path):
        for name in names:
            if os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS:
                files.append(os.path.join(root, name))
    return sorted(files)


def process_torrent_rename(tor, cats: list[dict]) -> tuple[list[int], list[str]]:
    """
    Called after a torrent completes. Creates hardlinks for parseable files,
    queues pending_manual records for the rest.
    Returns (pending_manual_job_ids, error_messages).
    """
    from store import add_rename_job

    save_path = tor.save_path.rstrip("/")
    cat = next(
        (c for c in cats if save_path in (
            c["path"].rstrip("/"),
            os.path.join(c["path"], ".incoming").rstrip("/"),
        )),
        None,
    )
    if not cat:
        log.debug("Torrent %s: save_path=%s matches no category, skipping rename", tor.hash, tor.save_path)
        return [], []

    if cat["jf_type"] not in ("tvshows", "movies"):
        log.debug("Torrent %s: jf_type=%s not supported for rename", tor.hash, cat["jf_type"])
        return [], []

    content_path = getattr(tor, "content_path", None) or os.path.join(tor.save_path, tor.name)
    video_files = get_video_files(content_path)

    pending_ids: list[int] = []
    errors: list[str] = []

    for src_path in video_files:
        filename = os.path.basename(src_path)
        parsed = parse_filename(filename, cat["jf_type"])

        if parsed:
            dst_path = build_target_path(cat, parsed, filename)
            try:
                create_hardlink(src_path, dst_path)
                add_rename_job(tor.hash, src_path, cat["path"], cat["jf_type"], "linked", dst_path)
                log.info("Hardlinked: %s -> %s", src_path, dst_path)
            except OSError as e:
                if e.errno == errno.EXDEV:
                    msg = f"Cross-device hardlink: {src_path} — download dir and media library must be on the same partition."
                    log.error(msg)
                    errors.append(msg)
                else:
                    log.error("Hardlink failed %s -> %s: %s", src_path, dst_path, e)
                    job_id = add_rename_job(tor.hash, src_path, cat["path"], cat["jf_type"], "pending_manual")
                    pending_ids.append(job_id)
        else:
            job_id = add_rename_job(tor.hash, src_path, cat["path"], cat["jf_type"], "pending_manual")
            pending_ids.append(job_id)
            log.info("Cannot parse %s, queued as pending_manual (job %d)", filename, job_id)

    return pending_ids, errors


def delete_torrent_hardlinks(torrent_hash: str):
    from store import get_rename_jobs_by_hash, delete_rename_jobs_by_hash

    for job in get_rename_jobs_by_hash(torrent_hash):
        if job["status"] == "linked" and job["dst_path"] and os.path.exists(job["dst_path"]):
            try:
                os.unlink(job["dst_path"])
                _cleanup_empty_dirs(job["dst_path"], job["cat_path"])
            except OSError as e:
                log.warning("Could not remove hardlink %s: %s", job["dst_path"], e)
    delete_rename_jobs_by_hash(torrent_hash)
