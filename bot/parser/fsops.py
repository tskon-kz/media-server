"""Low-level filesystem helpers: hardlinks, walking, category lookup, cleanup."""

import logging
import os

from config import INCOMING_DIR
from .constants import MEDIA_EXTENSIONS

log = logging.getLogger(__name__)


def create_hardlink(src: str, dst: str):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        if os.stat(src).st_ino == os.stat(dst).st_ino:
            return  # already pointing at the right inode
        os.unlink(dst)  # stale link (e.g. original was replaced in-place by upscaler)
    os.link(src, dst)


def cleanup_empty_dirs(path: str, stop_at: str):
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


def find_cat(tor, cats: list[dict]) -> dict | None:
    save_path = tor.save_path.rstrip("/")
    return next(
        (c for c in cats if save_path in (
            c["path"].rstrip("/"),
            os.path.join(INCOMING_DIR, os.path.basename(c["path"])).rstrip("/"),
        )),
        None,
    )


def try_unlink(path: str, stop_at: str):
    if os.path.exists(path):
        try:
            os.unlink(path)
            cleanup_empty_dirs(path, stop_at)
        except OSError as e:
            log.warning("Could not remove %s: %s", path, e)
