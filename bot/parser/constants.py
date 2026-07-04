"""File-type sets shared across the parser package."""

VIDEO_EXTENSIONS = {
    '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.ts', '.m2ts', '.flv', '.webm',
}
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa', '.sub', '.idx', '.vtt', '.sup', '.smi'}
AUDIO_EXTENSIONS = {
    '.mka', '.ac3', '.dts', '.eac3', '.truehd',
    '.flac', '.aac', '.mp3', '.opus', '.ogg', '.wav', '.m4a',
}

# Sidecar = external subtitle/audio that Jellyfin attaches to a video by
# matching filenames; multiple per episode must have distinct language/label
# suffixes or they collide into one.
SIDECAR_EXTENSIONS = SUBTITLE_EXTENSIONS | AUDIO_EXTENSIONS
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | SIDECAR_EXTENSIONS

# Container folders that only group tracks; dropped from sidecar labels so a
# dub in "Sound/Rus [Dub]/[2x2]" is labelled "rus.2x2", not "Sound_Rus_2x2".
GENERIC_DIRS = {"sound", "audio", "subs", "sub", "subtitle", "subtitles", "voice", "voiceover"}
