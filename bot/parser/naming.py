"""Building Jellyfin target paths and sidecar (dub/sub) labels."""

import os
import re

from guessit import guessit

from .constants import GENERIC_DIRS


def build_target_path(cat: dict, parsed: dict, src_filename: str,
                      *, episode_width: int = 2, label: str = "") -> str:
    ext = os.path.splitext(src_filename)[1].lower()
    cat_path = cat["path"]
    suffix = f".{label}" if label else ""  # Jellyfin sidecar suffix, e.g. ".rus.AniLibria"

    if cat["jf_type"] == "tvshows":
        title = parsed["title"]
        s, e = parsed["season"], parsed["episode"]
        fname = f"{title} - S{s:02d}E{e:0{episode_width}d}{suffix}{ext}"
        return os.path.join(cat_path, title, f"Season {s:02d}", fname)

    if cat["jf_type"] == "movies":
        title = parsed["title"]
        folder = f"{title} ({parsed['year']})" if parsed.get("year") else title
        return os.path.join(cat_path, folder, f"{folder}{suffix}{ext}")

    return os.path.join(cat_path, src_filename)


def _sanitize_token(s: str) -> str:
    # Dots separate fields in Jellyfin sidecar names, so strip them from labels.
    s = re.sub(r'[.\s]+', '_', s.strip())
    s = re.sub(r'[^\w\-]', '', s, flags=re.UNICODE)  # keep unicode (e.g. Cyrillic dub folders)
    return s.strip('_')


def _dir_label_parts(name: str) -> list[str]:
    """Split a folder name into meaningful parts, dropping episode-range groups.

    "[2x2] [001-220] [MVO]" -> ["2x2", "MVO"]; "Rus [Dub+MVO]" -> ["Rus", "Dub+MVO"].
    """
    out = []
    for a, b, c in re.findall(r'\[([^\]]*)\]|\(([^)]*)\)|([^\[\]()]+)', name):
        for word in (a or b or c).split():
            if re.fullmatch(r'[\d,\-–—]+', word):  # episode range like 001-220
                continue
            out.append(word)
    return out


def sidecar_label(src_path: str, content_root: str, filename: str) -> str:
    """Build a language/studio suffix so multiple dubs/subs per episode stay distinct.

    Combines the detected language with the studio/type from the folders the file
    came from (dubs/subs live in their own directories, e.g. "Rus Sub/[Alex & Julia]").
    """
    root = content_root if os.path.isdir(content_root) else os.path.dirname(content_root)
    rel_dir = os.path.relpath(os.path.dirname(src_path), root)
    dir_comps = [] if rel_dir in (".", "") else rel_dir.split(os.sep)

    # Language usually lives in the folder name ("Rus Sub"), not the episode filename.
    lang_code = None
    try:
        guess = guessit(" ".join(dir_comps + [filename]))
        lang = guess.get("subtitle_language") or guess.get("language")
        if isinstance(lang, list):
            lang = lang[0] if lang else None
        if lang is not None:
            lang_code = str(getattr(lang, "alpha3", lang))
    except Exception:
        pass

    # Collect studio/type tokens, dropping generics and case-insensitive repeats
    # (incl. a folder token equal to the language, e.g. "Rus" when lang is rus).
    seen = {lang_code.lower()} if lang_code else set()
    title_tokens = []
    for comp in dir_comps:
        for part in _dir_label_parts(comp):
            st = _sanitize_token(part)
            if st and st.lower() not in GENERIC_DIRS and st.lower() not in seen:
                seen.add(st.lower())
                title_tokens.append(st)

    # Jellyfin reads the first dot-field as language; keep the studio/type as a
    # single underscore-joined title field: "<lang>.<Studio_Type>".
    fields = []
    if lang_code:
        fields.append(lang_code)
    if title_tokens:
        fields.append("_".join(title_tokens))
    return ".".join(fields)


def season_episode_widths(parsed_files: list[tuple]) -> dict:
    """Zero-pad width per (title, season): 3 for 100+ episode seasons, else 2."""
    max_ep: dict = {}
    for _src, _fn, p in parsed_files:
        key = (p["title"], p["season"])
        max_ep[key] = max(max_ep.get(key, 0), p["episode"])
    return {k: max(2, len(str(v))) for k, v in max_ep.items()}


def dedupe(dst_path: str, used: set) -> str:
    if dst_path not in used and not os.path.exists(dst_path):
        return dst_path
    root, ext = os.path.splitext(dst_path)
    i = 2
    while f"{root}.{i}{ext}" in used or os.path.exists(f"{root}.{i}{ext}"):
        i += 1
    return f"{root}.{i}{ext}"


def content_root_dir(cat: dict, parsed: dict) -> str:
    """The show/movie folder a parsed item lives in (used for extras + deletion)."""
    if cat["jf_type"] == "tvshows":
        return os.path.join(cat["path"], parsed["title"])
    if cat["jf_type"] == "movies":
        folder = f"{parsed['title']} ({parsed['year']})" if parsed.get("year") else parsed["title"]
        return os.path.join(cat["path"], folder)
    return cat["path"]


def extras_base_dir(cat: dict, tor, fallback_title: str | None, parsed_files: list) -> str:
    """Folder under which a torrent's extras/ directory goes."""
    if parsed_files:
        return content_root_dir(cat, parsed_files[0][2])
    name = fallback_title or os.path.splitext(tor.name)[0]
    return os.path.join(cat["path"], name)
