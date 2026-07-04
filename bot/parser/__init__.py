"""Filename parsing + hardlink/rename logic, split into focused modules.

Public API is re-exported here so callers keep using ``from parser import ...``.
"""

from .constants import (
    VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS, AUDIO_EXTENSIONS,
    SIDECAR_EXTENSIONS, MEDIA_EXTENSIONS,
)
from .filenames import parse_filename, parse_manual_input, is_extra, tor_fallback_title
from .naming import build_target_path
from .fsops import create_hardlink, get_video_files
from .linker import (
    count_parseable_files,
    process_torrent_rename,
    create_flat_hardlink_for_job,
    create_flat_hardlinks,
    delete_torrent_links,
    delete_all_cat_contents,
)

__all__ = [
    "VIDEO_EXTENSIONS", "SUBTITLE_EXTENSIONS", "AUDIO_EXTENSIONS",
    "SIDECAR_EXTENSIONS", "MEDIA_EXTENSIONS",
    "parse_filename", "parse_manual_input", "is_extra", "tor_fallback_title",
    "build_target_path", "create_hardlink", "get_video_files",
    "count_parseable_files", "process_torrent_rename",
    "create_flat_hardlink_for_job", "create_flat_hardlinks",
    "delete_torrent_links", "delete_all_cat_contents",
]
