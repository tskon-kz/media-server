"""Understanding filenames: parse episodes/movies, manual input, extras detection."""

import os
import re

from guessit import guessit


def tor_fallback_title(tor) -> str | None:
    t = guessit(tor.name).get("title")
    return str(t) if t else None


def parse_filename(filename: str, jf_type: str, fallback_title: str | None = None) -> dict | None:
    stem = os.path.splitext(filename)[0]
    guess = guessit(filename)

    if jf_type == "tvshows":
        title = guess.get("title")
        season = guess.get("season")
        episode = guess.get("episode")
        if isinstance(episode, list):
            episode = episode[0]

        # filename starts with SxEx → guessit used the episode title as show title
        if re.match(r'^s\d{1,2}e\d{1,3}', stem, re.IGNORECASE):
            title = fallback_title

        # Bare zero-padded numbers ("Naruto - 150", "Naruto - 001") make guessit
        # split them into season/episode ("150"->S1E50, "001"->S0E1), and it does
        # so inconsistently across a release's videos vs its dub/sub files. With no
        # explicit season marker, trust the trailing number as the absolute episode
        # so every file (video + sidecars) maps to the same S01Exxx.
        has_season_marker = re.search(r'(?i)(?:\bs\d{1,2}(?!\d)|season[ ._]?\d{1,2})', stem)
        if not has_season_marker:
            clean_stem = re.sub(r'(\s*[\[(][^\]\)]*[\]\)])+$', '', stem).rstrip()
            m = re.search(r'(?:^|[\s_.\-])(\d{1,4})\s*$', clean_stem)
            if m:
                n = int(m.group(1))
                if 0 < n < 3000 and n != (guess.get("year") or -1):
                    season, episode = 1, n
                    if not title:
                        title = fallback_title

        # fallback: bare number for partial guesses (other layouts)
        if title and (season is None or episode is None):
            clean_stem = re.sub(r'(\s*[\[(][^\]\)]*[\]\)])+$', '', stem).rstrip()
            m = re.search(r'[\s_.-](\d{1,3})$', clean_stem)
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


# Non-episode video extras (creditless OP/ED, PVs, menus, specials…). Detected by
# folder context so e.g. "OP-ED [Creditless]/NCOP01.mkv" is NOT parsed as E01.
_EXTRAS_DIR_RE = re.compile(
    r'(?i)(creditless|non[-_ ]?credit|nc[-_ ]?op|nc[-_ ]?ed|op[-_/ ]?ed|opening|ending|'
    r'\bextras?\b|\bspecials?\b|\bbonus\b|\bpv\b|\bcm\b|\bmenu\b|interview|trailer|'
    r'preview|\bsample\b|featurette|scans?|booklet)'
)
# Narrower set for loose files (avoid false positives on real episode titles).
_EXTRAS_NAME_RE = re.compile(r'(?i)(creditless|non[-_ ]?credit|\bnc[-_ ]?op\b|\bnc[-_ ]?ed\b|\bncop\b|\bnced\b)')


def is_extra(src_path: str, content_root: str) -> bool:
    root = content_root if os.path.isdir(content_root) else os.path.dirname(content_root)
    rel = os.path.relpath(src_path, root)
    dir_part = os.path.dirname(rel)
    stem = os.path.splitext(os.path.basename(src_path))[0]
    return bool((dir_part and _EXTRAS_DIR_RE.search(dir_part)) or _EXTRAS_NAME_RE.search(stem))
