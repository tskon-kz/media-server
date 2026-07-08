#!/usr/bin/env python3
"""Standalone tests for parser.filenames.parse_filename.

Run from the repo root (no pytest needed, only `guessit` installed):

    python3 bot/parser/test_filenames.py

To add a new example: append a row to CASES below. Format is

    (filename, jf_type, fallback_title, expected)

where jf_type is "tvshows" or "movies", fallback_title is the show title
guessit would otherwise miss (or None), and expected is the dict you want
back — or None if the file must stay unparsed. That's the whole workflow:
drop a real-world filename in, write what it should resolve to, rerun.

This file loads filenames.py in isolation so it doesn't drag in config/store
(which need env vars); it never touches the filesystem or the database.
"""

import os
import sys
import types

from guessit import guessit as _guessit


def _load_parse_filename():
    """Exec filenames.py alone, bypassing parser/__init__ (config/store deps)."""
    path = os.path.join(os.path.dirname(__file__), "filenames.py")
    with open(path) as fh:
        source = fh.read()
    module = types.ModuleType("filenames_under_test")
    module.__dict__["guessit"] = _guessit
    exec(compile(source, path, "exec"), module.__dict__)
    return module.parse_filename


# (filename, jf_type, fallback_title, expected) — add new examples here.
CASES = [
    # E<num> without S<num>: episode from the E-prefix, season forced to 1.
    ("Naruto.E001.1080p.BluRay.hevc.mkv", "tvshows", None,
     {"title": "Naruto", "season": 1, "episode": 1}),
    ("Naruto.E056.1080p.BluRay.hevc.mkv", "tvshows", None,
     {"title": "Naruto", "season": 1, "episode": 56}),
    ("Naruto.E111.1080p.BluRay.hevc.mkv", "tvshows", None,
     {"title": "Naruto", "season": 1, "episode": 111}),
    ("Naruto.E166.1080p.BluRay.hevc.mkv", "tvshows", None,
     {"title": "Naruto", "season": 1, "episode": 166}),

    # Bare absolute numbers: the full trailing number wins over guessit's mis-split.
    ("[SOFCJ-Raws] Naruto - 063 (DVDRip 768x576 HEVC VFR 10bit FLAC).mkv", "tvshows", "Naruto",
     {"title": "Naruto", "season": 1, "episode": 63}),
    ("[SOFCJ-Raws] Naruto - 175 (DVDRip 768x576 HEVC VFR 10bit FLAC).mkv", "tvshows", "Naruto",
     {"title": "Naruto", "season": 1, "episode": 175}),
    ("Naruto - 150.mkv", "tvshows", "Naruto",
     {"title": "Naruto", "season": 1, "episode": 150}),
    ("Naruto - 001.mkv", "tvshows", "Naruto",
     {"title": "Naruto", "season": 1, "episode": 1}),
    ("One Piece - 1000 [1080p].mkv", "tvshows", "One Piece",
     {"title": "One Piece", "season": 1, "episode": 1000}),
    ("Bleach 366.mkv", "tvshows", "Bleach",
     {"title": "Bleach", "season": 1, "episode": 366}),
    ("Death Note - 37 END.mkv", "tvshows", "Death Note",
     {"title": "Death Note", "season": 1, "episode": 37}),

    # Explicit SxxExx: taken verbatim from guessit.
    ("Black.Mirror.s01e03.avi", "tvshows", None,
     {"title": "Black Mirror", "season": 1, "episode": 3}),
    ("Black.Mirror.s03e06.srt", "tvshows", None,
     {"title": "Black Mirror", "season": 3, "episode": 6}),
    ("The.Haunting.of.Hill.House.S01E01.Rus.Eng.LostFilm.avi", "tvshows", None,
     {"title": "The Haunting of Hill House", "season": 1, "episode": 1}),
    ("The.Haunting.of.Hill.House.S01E06.Rus.Eng.LostFilm.avi", "tvshows", None,
     {"title": "The Haunting of Hill House", "season": 1, "episode": 6}),
    ("Show.Name.S02E05.720p.mkv", "tvshows", None,
     {"title": "Show Name", "season": 2, "episode": 5}),
    ("Breaking.Bad.S05E14.Ozymandias.1080p.mkv", "tvshows", None,
     {"title": "Breaking Bad", "season": 5, "episode": 14}),
    ("Attack on Titan S04E28.mkv", "tvshows", None,
     {"title": "Attack on Titan", "season": 4, "episode": 28}),
    ("Show.2020.S01E01.mkv", "tvshows", None,
     {"title": "Show", "season": 1, "episode": 1}),

    # Season marker + separate episode number.
    ("Show.Name.S02.05.mkv", "tvshows", None,
     {"title": "Show Name", "season": 2, "episode": 5}),
    ("Show S01 - 05.mkv", "tvshows", None,
     {"title": "Show", "season": 1, "episode": 5}),
    ("Naruto S02 - 099.mkv", "tvshows", "Naruto",
     {"title": "Naruto", "season": 2, "episode": 99}),
    ("Show.S03.E10.mkv", "tvshows", None,
     {"title": "Show", "season": 3, "episode": 10}),

    # filename starts with SxEx → guessit used the episode title as show title,
    # so the fallback_title has to stand in.
    ("s01e02.The.Episode.Title.mkv", "tvshows", "My Show",
     {"title": "My Show", "season": 1, "episode": 2}),

    # Movies.
    ("Inception.2010.1080p.BluRay.mkv", "movies", None,
     {"title": "Inception", "year": 2010}),
    ("The Matrix (1999).mkv", "movies", None,
     {"title": "The Matrix", "year": 1999}),
    ("Interstellar.mkv", "movies", None,
     {"title": "Interstellar", "year": None}),
]


def main() -> int:
    parse_filename = _load_parse_filename()
    failures = 0
    for filename, jf_type, fallback_title, expected in CASES:
        actual = parse_filename(filename, jf_type, fallback_title)
        if actual == expected:
            print(f"  ok   {filename}")
        else:
            failures += 1
            print(f"  FAIL {filename}")
            print(f"       expected: {expected}")
            print(f"       actual:   {actual}")

    total = len(CASES)
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
