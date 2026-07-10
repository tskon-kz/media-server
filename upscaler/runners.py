"""Upscaler backends. Each produces a 2x (or `scale`x) version of a video file
and atomically replaces the original in place, so the library relink the bot runs
afterwards points at the upscaled data with no extra disk cost.

Both backends are a single ffmpeg pass (so both report real progress and stay in
the same speed class as a plain resize — no explode-to-PNG frame churn):

- ``cas``     — lanczos upscale + AMD FidelityFX Contrast Adaptive Sharpening
  (``cas`` filter). CPU-only scaling, works everywhere; H.264 encode moves to the
  iGPU (VAAPI) when available, else CPU libx264. Not neural, but visibly sharper
  than a plain resize.
- ``anime4k`` — the Anime4K neural shaders run as a GPU pass through ffmpeg's
  ``libplacebo`` filter (Vulkan; needs ``/dev/dri``). Real-time even on a weak
  iGPU — a completely different weight class from a per-frame CNN. The upscaled
  frames come back to system memory (``hwdownload``) and are H.264-encoded on the
  CPU; the Vulkan→VAAPI encode handoff is left as a future optimisation.

Requires a libplacebo-enabled ffmpeg (jellyfin-ffmpeg); ``FFMPEG_BIN`` points at
it. Stock Debian ffmpeg has no libplacebo, so the ``anime4k`` backend would fail.
"""
import collections
import logging
import os
import re
import subprocess
import tempfile

log = logging.getLogger("upscaler")

# Only real video files can be upscaled. The bot filters sidecars (subs/audio)
# out before queueing, but stale jobs queued by older bot builds may still name a
# subtitle/audio file — skip those cleanly instead of erroring on a non-video.
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".m2ts", ".flv", ".webm",
}

# ffmpeg/ffprobe binaries. The Dockerfile points these at jellyfin-ffmpeg, which
# ships the libplacebo filter the `anime4k` backend needs (stock ffmpeg has none).
FFMPEG_BIN        = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN       = os.environ.get("FFPROBE_BIN", "ffprobe")

# Anime4K GLSL shader preset (a combined libplacebo hook file) bundled in the
# image; passed to the libplacebo filter's custom_shader_path.
ANIME4K_SHADER    = os.environ.get("ANIME4K_SHADER", "/opt/anime4k/anime4k.glsl")

# Compression presets — the `id` is the contract with the bot's config.py /
# COMPRESSION_LEVELS. `crf` drives the CPU libx264 paths (anime4k + cas-on-CPU);
# `qp` drives the VAAPI encode (cas on an iGPU). Higher = smaller file. On a 2x
# upscale the added detail is synthetic, so it compresses well with little visible
# loss — hence `aggressive` leans notably harder. More levels/knobs land here.
COMPRESSION = {
    "balanced":   {"crf": "20", "qp": "22"},
    "aggressive": {"crf": "23", "qp": "25"},
}
DEFAULT_COMPRESSION = "balanced"


def _quality(compression: str | None) -> dict:
    return COMPRESSION.get(compression or DEFAULT_COMPRESSION, COMPRESSION[DEFAULT_COMPRESSION])


# CPU H.264 encode, shared as the fallback (and the anime4k encode tail).
def _cpu_codec(crf: str) -> list[str]:
    return ["-c:v", "libx264", "-crf", crf, "-preset", "fast", "-pix_fmt", "yuv420p"]

# VAAPI hardware H.264 encode. `auto` = use it when the device probes OK; `off`
# forces the CPU libx264 path (e.g. for a broken driver). Same /dev/dri already
# mounted for the AI backend.
VAAPI_DEVICE      = os.environ.get("VAAPI_DEVICE", "/dev/dri/renderD128")
HWENC             = os.environ.get("UPSCALE_HWENC", "auto").lower()


class UpscaleError(Exception):
    pass


# GPU capabilities don't change while the container lives, and this worker is a
# long-running poll loop, so probe once and memoise instead of shelling out per
# job. None = not yet probed.
_vulkan_cached: bool | None = None
_vaapi_cached: bool | None = None


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


def has_vaapi() -> bool:
    global _vaapi_cached
    if _vaapi_cached is None:
        _vaapi_cached = _probe_vaapi()
        log.info("VAAPI hardware encode available: %s (device=%s)", _vaapi_cached, VAAPI_DEVICE)
    return _vaapi_cached


def _probe_vaapi() -> bool:
    if HWENC == "off" or not os.path.exists(VAAPI_DEVICE):
        return False
    try:
        out = subprocess.run(
            ["vainfo", "--display", "drm", "--device", VAAPI_DEVICE],
            capture_output=True, text=True, timeout=30,
        )
        # Need an actual H.264 *encode* entrypoint, not just decode.
        return out.returncode == 0 and "VAEntrypointEncSlice" in out.stdout
    except Exception:
        return False


def _video_encode(scale_filter: str | None, quality: dict) -> tuple[list, str, list]:
    """Encoder command fragments for the CPU (``cas``) backend.

    Returns ``(pre_input_args, video_filter, codec_args)``. ``scale_filter`` is the
    caller's scaling stage (or None) that the hwupload tail is appended to.
    VAAPI when available (H.264 encode on the iGPU), else CPU libx264. ``quality``
    supplies the compression level (`qp` for VAAPI, `crf` for libx264).
    """
    parts = [p for p in (scale_filter,) if p]
    if has_vaapi():
        parts.append("format=nv12,hwupload")
        return (["-vaapi_device", VAAPI_DEVICE],
                ",".join(parts),
                ["-c:v", "h264_vaapi", "-qp", quality["qp"]])
    return ([], ",".join(parts), _cpu_codec(quality["crf"]))


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
    """Media duration (s) for the progress-bar denominator. Many MKVs lack
    container-level `format=duration`, so fall back to the video stream's own."""
    for args in (
        ("-show_entries", "format=duration"),
        ("-select_streams", "v:0", "-show_entries", "stream=duration"),
    ):
        dur = _ffprobe_value(src, *args)
        if dur > 0:
            return dur
    return 0.0


def _probe_total_frames(src: str) -> int:
    """Total video frames, for the progress-bar denominator when `_probe_duration`
    fails (some anime MKVs carry no container *and* no stream duration, which would
    otherwise leave a single-file job's bar stuck at 0 the whole render — batches
    hide this behind their per-file completion steps, single files can't).

    `nb_frames` is a cheap tag read but often absent in MKV; fall back to
    `-count_packets` (demux only, no decode — fast even on a weak host)."""
    n = _ffprobe_value(src, "-select_streams", "v:0", "-show_entries", "stream=nb_frames")
    if n > 0:
        return int(n)
    n = _ffprobe_value(src, "-count_packets", "-select_streams", "v:0",
                       "-show_entries", "stream=nb_read_packets")
    return int(n) if n > 0 else 0


# ffmpeg's stderr status line: `frame=  123 fps=.. q=.. size=.. time=00:00:04.56 ..`.
# We read progress from stderr (not `-progress pipe:1`): stderr is unbuffered and
# flushed on every `\r` update, whereas pipe:1's 32KB AVIO buffer leaves the bar
# stuck at 0 during a slow Vulkan/libplacebo start until it finally fills.
_TIME_RE  = re.compile(r"time=(\S+)")
_FRAME_RE = re.compile(r"frame=\s*(\d+)")


def _parse_out_time(val: str) -> float | None:
    """Seconds from ffmpeg's `-progress` ``out_time`` value (``HH:MM:SS.ffffff``).
    Returns None for the ``N/A`` ffmpeg emits before the first frame."""
    if not val or val.startswith("N/A"):
        return None
    try:
        h, m, s = val.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def _replace(src: str, tmp_out: str):
    """Swap the upscaled file in for the original, preserving the extension so the
    bot's linker still recognises the file. ``tmp_out`` is written next to ``src``
    so this stays a same-filesystem atomic rename."""
    os.replace(tmp_out, src)


def _has_video(src: str) -> bool:
    """True if ffprobe finds at least one video stream. Guards against being
    handed a broken/truncated file or a non-video the linker mislabelled."""
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


def _source_color_args(src: str) -> list[str]:
    """Re-attach the source's colour tags (hwdownload drops them). Only known
    values are emitted; hardcoding BT.709 would tint SD/DVD (BT.601) sources cool."""
    fields = ("color_space", "color_transfer", "color_primaries", "color_range")
    flags = {"color_space": "-colorspace", "color_transfer": "-color_trc",
             "color_primaries": "-color_primaries", "color_range": "-color_range"}
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=" + ",".join(fields),
             "-of", "default=noprint_wrappers=1", src],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:
        return []
    parsed = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip()
    args: list[str] = []
    for f in fields:
        val = parsed.get(f, "")
        if val and val.lower() not in ("unknown", "unspecified", "n/a"):
            args += [flags[f], val]
    return args


def _validate_output(tmp_out: str, src_duration: float):
    """Sanity-check the encode before the destructive swap so a broken-but-exit-0
    output can't lose the source. Needs a valid video stream and a duration close
    to the source; raises ``UpscaleError`` otherwise (job errors, original kept)."""
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
    # Allow a small tolerance; a wildly-off duration means a truncated/corrupt file.
    if src_duration > 0 and out_duration > 0 and abs(out_duration - src_duration) > max(2.0, src_duration * 0.02):
        raise UpscaleError(
            f"upscaled output duration {out_duration:.1f}s differs from source {src_duration:.1f}s")


def run(job: dict, progress_cb):
    upscaler = job["upscaler"]
    src = job["src_path"]
    scale = int(job["scale"] or 2)
    if not os.path.isfile(src):
        raise UpscaleError(f"source missing: {src}")
    if os.path.splitext(src)[1].lower() not in VIDEO_EXTENSIONS:
        # Sidecar (subtitle/audio) that slipped in from an older queueing build —
        # not something to upscale. Skip it cleanly so the batch isn't tainted.
        log.info("skipping non-video file %s", os.path.basename(src))
        return
    if not _has_video(src):
        raise UpscaleError(f"no decodable video stream in {os.path.basename(src)}")

    quality = _quality(job.get("compression"))
    log.info("compression=%s (crf=%s qp=%s)", job.get("compression") or DEFAULT_COMPRESSION,
             quality["crf"], quality["qp"])
    if upscaler == "cas":
        pre_input, vfilter, codec = _video_encode(
            f"scale=iw*{scale}:ih*{scale}:flags=lanczos,cas=strength=0.4", quality)
        _run_single(src, pre_input, vfilter, codec, progress_cb)
    elif upscaler == "anime4k":
        if not has_vulkan():
            raise UpscaleError("no Vulkan GPU (/dev/dri) — the AI upscaler is unavailable")
        _run_anime4k(src, scale, quality, progress_cb)
    else:
        raise UpscaleError(f"unknown upscaler: {upscaler}")


def _run_single(src: str, pre_input: list[str], vfilter: str, codec: list[str], progress_cb):
    """One-pass ffmpeg upscale: apply ``vfilter`` to the video stream, copy every
    other stream (all audio dubs, subtitles, attachments/fonts) verbatim, and swap
    the result in for the original. ``-progress pipe:1`` gives a real progress bar.

    Temp next to src: a single sequential write the HDD handles fine, and it keeps
    the final swap a same-filesystem atomic rename."""
    duration = _probe_duration(src)
    # Frame count is the fallback denominator when duration is unknown — without
    # one, a single-file job's bar never moves (batches hide it behind completions).
    total_frames = _probe_total_frames(src) if duration <= 0 else 0
    log.info("progress denominator: duration=%.1fs total_frames=%d", duration, total_frames)
    ext = os.path.splitext(src)[1] or ".mkv"
    fd, tmp_out = tempfile.mkstemp(suffix=ext, prefix=".upscale_", dir=os.path.dirname(src))
    os.close(fd)
    cmd = [
        FFMPEG_BIN, "-y", *pre_input, "-i", src,
        # Primary video + all audio/subs/attachments, NOT `-map 0`: a blanket map
        # pulls in embedded cover-art/ad images as extra video streams that `-c:v`
        # re-encodes into bogus tracks Jellyfin can't play. `?` = optional.
        "-map", "0:v:0", "-map", "0:a?", "-map", "0:s?", "-map", "0:t?",
        "-vf", vfilter,
        *codec,
        "-c:a", "copy", "-c:s", "copy", "-c:t", "copy",
        tmp_out,
    ]
    log.info("ffmpeg cmd: %s", " ".join(cmd))
    # Progress is read live off ffmpeg's stderr status line. text=True in universal-
    # newline mode splits on the `\r` ffmpeg uses to refresh that line, so each
    # update arrives as its own iterable "line". The same stream carries any real
    # error, so we keep a rolling tail to surface it on a nonzero exit (stdout is
    # discarded — nothing is written there without `-progress`, so no deadlock).
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    tail = collections.deque(maxlen=40)
    success = False
    try:
        for line in proc.stderr:
            tail.append(line)
            if duration > 0:
                m = _TIME_RE.search(line)
                if m:
                    secs = _parse_out_time(m.group(1))
                    if secs is not None:
                        progress_cb(min(1.0, secs / duration))
            # Fallback when duration is unknown: encoded `frame=` over total frames.
            elif total_frames > 0:
                m = _FRAME_RE.search(line)
                if m:
                    progress_cb(min(1.0, int(m.group(1)) / total_frames))
        code = proc.wait()
        if code != 0:
            raise UpscaleError(f"ffmpeg exited {code}: {''.join(tail).strip()[-1500:]}")
        # Validate before the destructive swap — never overwrite a good source
        # with a broken encode.
        _validate_output(tmp_out, duration)
        _replace(src, tmp_out)
        success = True
    finally:
        if proc.poll() is None:
            proc.kill()
        if not success:
            _cleanup(tmp_out)


def _run_anime4k(src: str, scale: int, quality: dict, progress_cb):
    """Upscale with the Anime4K neural shaders as a single libplacebo (Vulkan) pass,
    then bring the frames back to system memory (``hwdownload``) and H.264-encode on
    the CPU. The libplacebo shader work is the expensive part and runs on the GPU;
    the Vulkan→VAAPI encode handoff (two hw devices in one graph) is left as a
    future optimisation, so encode stays on libx264 here regardless of VAAPI.

    ``format=nv12,hwupload`` is explicit (not relying on libplacebo's auto-upload):
    it normalises 10-bit anime sources to an 8-bit format Vulkan accepts and puts
    the frames on the GPU before the shader — the implicit path throws EINVAL.
    ``hwdownload`` can only emit the Vulkan frame's own sw_format (nv12, what we
    uploaded), so we download as nv12 and let the encoder's ``-pix_fmt yuv420p``
    convert on the CPU — ``hwdownload,format=yuv420p`` is rejected as invalid, so
    the yuv420p normalisation is a separate filter link after the download."""
    vfilter = (f"format=nv12,hwupload,"
               f"libplacebo=w=iw*{scale}:h=ih*{scale}:"
               f"custom_shader_path={ANIME4K_SHADER},"
               f"hwdownload,format=nv12,format=yuv420p")
    codec = _cpu_codec(quality["crf"]) + _source_color_args(src) + ["-profile:v", "high"]
    _run_single(src, ["-init_hw_device", "vulkan=vk", "-filter_hw_device", "vk"],
                vfilter, codec, progress_cb)


def _cleanup(path: str):
    try:
        os.remove(path)
    except OSError:
        pass
