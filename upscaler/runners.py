"""Upscaler backends: single Vulkan/libplacebo ffmpeg pass, CPU libx264 encode,
atomic in-place replace. `anime4k` = neural GLSL shaders (anime); `fsr` =
ewa_lanczossharp polar scaler (live-action). Needs jellyfin-ffmpeg (libplacebo)
and /dev/dri."""
import collections
import logging
import os
import re
import subprocess
import tempfile

log = logging.getLogger("upscaler")

# Skip stale jobs from older builds that named a sidecar instead of a video.
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".m2ts", ".flv", ".webm",
}

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")
ANIME4K_SHADER = os.environ.get("ANIME4K_SHADER", "/opt/anime4k/anime4k.glsl")
TEMP_PREFIX = ".upscale_"

# `id` is the contract with the bot's config.COMPRESSION_LEVELS. Both CRFs are
# visually transparent — the choice trades file size, not quality.
COMPRESSION = {
    "balanced": {"crf": "18"},
    "aggressive": {"crf": "20"},
}
DEFAULT_COMPRESSION = "balanced"


def _quality(compression: str | None) -> dict:
    return COMPRESSION.get(compression or DEFAULT_COMPRESSION, COMPRESSION[DEFAULT_COMPRESSION])


def _cpu_codec(crf: str) -> list[str]:
    return ["-c:v", "libx264", "-crf", crf, "-preset", "fast", "-pix_fmt", "yuv420p"]


class UpscaleError(Exception):
    pass


# Probed once and memoised — GPU caps don't change during the container's life.
_vulkan_cached: bool | None = None


def has_vulkan() -> bool:
    global _vulkan_cached
    if _vulkan_cached is None:
        _vulkan_cached = _probe_vulkan()
        log.info("Vulkan (Anime4K) available: %s", _vulkan_cached)
    return _vulkan_cached


def _probe_vulkan() -> bool:
    if not os.path.exists("/dev/dri"):
        return False
    try:
        subprocess.run(["vulkaninfo"], capture_output=True, timeout=30, check=True)
        return True
    except Exception:
        return False


def _ffprobe_value(src: str, *args: str) -> float:
    """Run ffprobe returning a single numeric field; 0.0 on any failure/empty/N/A."""
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", *args,
             "-of", "default=noprint_wrappers=1:nokey=1", src],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip().splitlines()
        val = out[0].strip() if out else ""
        if not val or val.startswith("N/A"):
            return 0.0
        return float(val)
    except Exception:
        return 0.0


def _probe_duration(src: str) -> float:
    """Media duration (s). Falls back to the video stream when the container
    lacks `format=duration` (common in MKV)."""
    for args in (
            ("-show_entries", "format=duration"),
            ("-select_streams", "v:0", "-show_entries", "stream=duration"),
    ):
        dur = _ffprobe_value(src, *args)
        if dur > 0:
            return dur
    return 0.0


def _probe_total_frames(src: str) -> int:
    """Frame count — the progress denominator when duration is unknown. `nb_frames`
    is often absent in MKV; fall back to `-count_packets` (demux only, no decode)."""
    n = _ffprobe_value(src, "-select_streams", "v:0", "-show_entries", "stream=nb_frames")
    if n > 0:
        return int(n)
    n = _ffprobe_value(src, "-count_packets", "-select_streams", "v:0",
                       "-show_entries", "stream=nb_read_packets")
    return int(n) if n > 0 else 0


_TARGET_HEIGHTS = {"1080": 1080, "2k": 1440, "4k": 2160}


def _probe_dims(src: str) -> tuple[int, int]:
    """Source (width, height) in pixels, or (0, 0) if unknown."""
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "default=noprint_wrappers=1:nokey=1", src],
            capture_output=True, text=True, timeout=60,
        ).stdout.split()
        if len(out) >= 2 and out[0].isdigit() and out[1].isdigit():
            return int(out[0]), int(out[1])
    except Exception:
        pass
    return 0, 0


def _scale_dims(src: str, target: str) -> tuple[str, str] | None:
    """Output (width, height) scale exprs. `2x`/unknown target = double each dim;
    a resolution target scales to that height keeping aspect. None = source already
    at/above target, skip."""
    th = _TARGET_HEIGHTS.get(target or "")
    if not th:
        return "iw*2", "ih*2"
    w, h = _probe_dims(src)
    if h <= 0 or w <= 0:
        return "iw*2", "ih*2"
    if h >= th:
        return None
    ow = round(w * th / h)
    ow -= ow % 2  # H.264 needs even dimensions
    return str(ow), str(th)


# Progress is read off stderr's status line (unbuffered, flushed per `\r`), not
# `-progress pipe:1` (its 32KB buffer stalls the bar during slow Vulkan startup).
_TIME_RE = re.compile(r"time=(\S+)")
_FRAME_RE = re.compile(r"frame=\s*(\d+)")

_ERROR_RE = re.compile(
    r"error|invalid|failed|unable|cannot|no such|not found|"
    r"unsupported|conversion|impossible|denied|permission|"
    r"out of memory|killed|device|vulkan|libplacebo|filtergraph|"
    r"\[.*@ .*\] ",
    re.IGNORECASE,
)


def _is_error_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("Metadata:", "Stream #", "Input #", "Output #",
                            "Duration:", "BPS", "DURATION", "NUMBER_OF_",
                            "_STATISTICS_", "encoder", "handler_name",
                            "vendor_id", "title", "creation_time", "language")):
        return False
    return bool(_ERROR_RE.search(stripped))


def _parse_out_time(val: str) -> float | None:
    """Seconds from an `HH:MM:SS.ffffff` time; None for the `N/A` before frame 1."""
    if not val or val.startswith("N/A"):
        return None
    try:
        h, m, s = val.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def _replace(src: str, tmp_out: str):
    """Same-filesystem atomic swap (tmp_out is written next to src)."""
    os.replace(tmp_out, src)


def _has_video(src: str) -> bool:
    """True if ffprobe finds a video stream (guards broken/mislabelled files)."""
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-select_streams", "v",
             "-show_entries", "stream=codec_type",
             "-of", "default=noprint_wrappers=1:nokey=1", src],
            capture_output=True, text=True, timeout=60,
        ).stdout
        return "video" in out
    except Exception:
        return False


def _probe_color(src: str) -> dict:
    """Source colour metadata (space/transfer/primaries/range), known values only."""
    fields = ("color_space", "color_transfer", "color_primaries", "color_range")
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=" + ",".join(fields),
             "-of", "default=noprint_wrappers=1", src],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:
        return {}
    parsed: dict = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and v.lower() not in ("unknown", "unspecified", "n/a"):
                parsed[k] = v
    return parsed


def _source_color_args(src: str) -> list[str]:
    """Re-attach the source's colour tags to the encoder (hwdownload drops them);
    hardcoding BT.709 would tint SD/DVD (BT.601) sources cool."""
    flags = {"color_space": "-colorspace", "color_transfer": "-color_trc",
             "color_primaries": "-color_primaries", "color_range": "-color_range"}
    parsed = _probe_color(src)
    args: list[str] = []
    for f, flag in flags.items():
        if f in parsed:
            args += [flag, parsed[f]]
    return args


def _libplacebo_color_opts(src: str) -> str:
    """libplacebo output-colour pinned to the source so its linear-light round-trip
    is identity and colours don't shift (else BT.601 footage gets a cool tint).
    Empty when untagged."""
    parsed = _probe_color(src)
    opts = []
    if "color_space" in parsed:
        opts.append(f"colorspace={parsed['color_space']}")
    if "color_primaries" in parsed:
        opts.append(f"color_primaries={parsed['color_primaries']}")
    if "color_transfer" in parsed:
        opts.append(f"color_trc={parsed['color_transfer']}")
    rng = parsed.get("color_range", "")
    if rng in ("tv", "limited"):
        opts.append("range=tv")
    elif rng in ("pc", "full"):
        opts.append("range=pc")
    return (":" + ":".join(opts)) if opts else ""


def _validate_output(tmp_out: str, src_duration: float):
    """Guard the destructive swap: require a valid video stream and a duration
    close to the source, else raise (original kept)."""
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "default=noprint_wrappers=1:nokey=1", tmp_out],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:
        raise UpscaleError(f"output validation failed to run ffprobe: {e}")
    dims = [v for v in out.stdout.strip().splitlines() if v.strip()]
    if out.returncode != 0 or len(dims) < 2 or not all(d.isdigit() and int(d) > 0 for d in dims[:2]):
        raise UpscaleError(
            f"upscaled output has no valid video stream (ffprobe: {out.stderr.strip() or out.stdout.strip()})")
    out_duration = _probe_duration(tmp_out)
    if src_duration > 0 and out_duration > 0 and abs(out_duration - src_duration) > max(2.0, src_duration * 0.02):
        raise UpscaleError(
            f"upscaled output duration {out_duration:.1f}s differs from source {src_duration:.1f}s")


def run(job: dict, progress_cb):
    upscaler = job["upscaler"]
    src = job["src_path"]
    target = job.get("target") or "2x"
    if not os.path.isfile(src):
        raise UpscaleError(f"source missing: {src}")
    if os.path.splitext(src)[1].lower() not in VIDEO_EXTENSIONS:
        log.info("skipping non-video file %s", os.path.basename(src))
        return
    if not _has_video(src):
        raise UpscaleError(f"no decodable video stream in {os.path.basename(src)}")

    dims = _scale_dims(src, target)
    if dims is None:
        # Already at/above target; full bar so the batch counter advances.
        log.info("skipping %s: already >= target %s", os.path.basename(src), target)
        progress_cb(1.0)
        return
    ow, oh = dims

    quality = _quality(job.get("compression"))
    log.info("target=%s dims=%sx%s compression=%s (crf=%s) upscaler=%s", target, ow, oh,
             job.get("compression") or DEFAULT_COMPRESSION, quality["crf"], upscaler)
    if upscaler == "anime4k":
        if not has_vulkan():
            raise UpscaleError("no Vulkan GPU (/dev/dri) — the AI upscaler is unavailable")
        _run_libplacebo(src, ow, oh, quality, progress_cb, shader=ANIME4K_SHADER)
    elif upscaler == "fsr":
        if not has_vulkan():
            raise UpscaleError("no Vulkan GPU (/dev/dri) — the GPU upscaler is unavailable")
        _run_libplacebo(src, ow, oh, quality, progress_cb, shader=None)
    else:
        raise UpscaleError(f"unknown upscaler: {upscaler}")


def _run_single(src: str, pre_input: list[str], vfilter: str, codec: list[str], progress_cb):
    """One-pass upscale: apply `vfilter` to video, copy all other streams verbatim,
    atomically swap in for the original."""
    duration = _probe_duration(src)
    total_frames = _probe_total_frames(src)
    log.info("progress denominator: duration=%.1fs total_frames=%d", duration, total_frames)
    ext = os.path.splitext(src)[1] or ".mkv"
    fd, tmp_out = tempfile.mkstemp(suffix=ext, prefix=TEMP_PREFIX, dir=os.path.dirname(src))
    os.close(fd)
    cmd = [
        FFMPEG_BIN, "-y", *pre_input, "-i", src,
        # Not `-map 0`: that pulls embedded cover-art as extra video streams `-c:v`
        # would re-encode into bogus tracks. `?` = optional.
        "-map", "0:v:0", "-map", "0:a?", "-map", "0:s?", "-map", "0:t?",
        "-vf", vfilter,
        *codec,
        "-c:a", "copy", "-c:s", "copy", "-c:t", "copy",
        tmp_out,
    ]
    log.info("ffmpeg cmd: %s", " ".join(cmd))
    # text=True splits on the `\r` ffmpeg uses to refresh its status line, so each
    # progress update arrives as its own line.
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    tail = collections.deque(maxlen=40)
    # Separate ring of error-looking lines: the per-stream metadata dump can fill
    # `tail` on a many-track source and bury the actual error.
    errors = collections.deque(maxlen=15)
    success = False
    try:
        for line in proc.stderr:
            tail.append(line)
            if _is_error_line(line):
                errors.append(line)
            frac = None
            # Prefer time=; fall back to frame= when time= is absent/N/A.
            if duration > 0:
                m = _TIME_RE.search(line)
                if m:
                    secs = _parse_out_time(m.group(1))
                    if secs is not None:
                        frac = secs / duration
            if frac is None and total_frames > 0:
                m = _FRAME_RE.search(line)
                if m:
                    frac = int(m.group(1)) / total_frames
            if frac is not None:
                progress_cb(min(1.0, frac))
        code = proc.wait()
        if code != 0:
            detail = "".join(errors) if errors else "".join(tail)
            raise UpscaleError(f"ffmpeg exited {code}: {detail.strip()[-1500:]}")
        _validate_output(tmp_out, duration)
        _replace(src, tmp_out)
        success = True
    finally:
        if proc.poll() is None:
            proc.kill()
        if not success:
            _cleanup(tmp_out)


def _run_libplacebo(src: str, ow: str, oh: str, quality: dict, progress_cb, shader: str | None):
    """Single Vulkan/libplacebo pass, then hwdownload + CPU libx264. `shader` set =
    Anime4K neural shaders; None = ewa_lanczossharp polar scaler.

    `format=nv12,hwupload` is explicit: it normalises 10-bit sources to 8-bit and
    uploads before the filter (the implicit path throws EINVAL). hwdownload can only
    emit the uploaded sw_format (nv12), so yuv420p conversion is a separate link."""
    scaler = f"custom_shader_path={shader}" if shader else "upscaler=ewa_lanczossharp"
    color = _libplacebo_color_opts(src)
    vfilter = (f"format=nv12,hwupload,"
               f"libplacebo=w={ow}:h={oh}:{scaler}{color},"
               f"hwdownload,format=nv12,format=yuv420p")
    codec = _cpu_codec(quality["crf"]) + _source_color_args(src) + ["-profile:v", "high"]
    _run_single(src, ["-init_hw_device", "vulkan=vk", "-filter_hw_device", "vk"],
                vfilter, codec, progress_cb)


def _cleanup(path: str):
    try:
        os.remove(path)
    except OSError:
        pass


def cleanup_temp_files(directories):
    """Remove leftover `.upscale_*` temps from interrupted encodes. Called at
    startup for the dirs of re-queued jobs (the original is always intact)."""
    for directory in {d for d in directories if d}:
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in names:
            if name.startswith(TEMP_PREFIX):
                _cleanup(os.path.join(directory, name))
