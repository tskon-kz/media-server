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
import logging
import os
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

# CPU H.264 encode, shared as the fallback (and the anime4k encode tail).
CPU_CODEC = ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]

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


def _video_encode(scale_filter: str | None) -> tuple[list, str, list]:
    """Encoder command fragments for the CPU (``cas``) backend.

    Returns ``(pre_input_args, video_filter, codec_args)``. ``scale_filter`` is the
    caller's scaling stage (or None) that the hwupload tail is appended to.
    VAAPI when available (H.264 encode on the iGPU), else CPU libx264.
    """
    parts = [p for p in (scale_filter,) if p]
    if has_vaapi():
        parts.append("format=nv12,hwupload")
        return (["-vaapi_device", VAAPI_DEVICE],
                ",".join(parts),
                ["-c:v", "h264_vaapi", "-qp", "18"])
    return ([], ",".join(parts), CPU_CODEC)


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
    """Media duration in seconds for the progress-bar denominator.

    Many MKVs carry no container-level `format=duration` (only per-stream), so a
    single probe would return 0 and leave the progress bar stuck at zero the whole
    render. Fall back to the first video stream's own duration."""
    for args in (
        ("-show_entries", "format=duration"),
        ("-select_streams", "v:0", "-show_entries", "stream=duration"),
    ):
        dur = _ffprobe_value(src, *args)
        if dur > 0:
            return dur
    return 0.0


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

    if upscaler == "cas":
        pre_input, vfilter, codec = _video_encode(
            f"scale=iw*{scale}:ih*{scale}:flags=lanczos,cas=strength=0.4")
        _run_single(src, pre_input, vfilter, codec, progress_cb)
    elif upscaler == "anime4k":
        if not has_vulkan():
            raise UpscaleError("no Vulkan GPU (/dev/dri) — the AI upscaler is unavailable")
        _run_anime4k(src, scale, progress_cb)
    else:
        raise UpscaleError(f"unknown upscaler: {upscaler}")


def _run_single(src: str, pre_input: list[str], vfilter: str, codec: list[str], progress_cb):
    """One-pass ffmpeg upscale: apply ``vfilter`` to the video stream, copy every
    other stream (all audio dubs, subtitles, attachments/fonts) verbatim, and swap
    the result in for the original. ``-progress pipe:1`` gives a real progress bar.

    Temp next to src: a single sequential write the HDD handles fine, and it keeps
    the final swap a same-filesystem atomic rename."""
    duration = _probe_duration(src)
    ext = os.path.splitext(src)[1] or ".mkv"
    fd, tmp_out = tempfile.mkstemp(suffix=ext, prefix=".upscale_", dir=os.path.dirname(src))
    os.close(fd)
    cmd = [
        FFMPEG_BIN, "-y", *pre_input, "-i", src,
        # Keep every stream — the result replaces the original in place, so a
        # dropped track is lost for good. Only the video stream is filtered.
        "-map", "0",
        "-vf", vfilter,
        *codec,
        "-c:a", "copy", "-c:s", "copy", "-c:t", "copy",
        "-progress", "pipe:1", "-nostats", tmp_out,
    ]
    # Progress is read live off stdout; stderr goes to a temp file so a failing
    # ffmpeg's actual error (filtergraph/option, e.g. a bad libplacebo config) is
    # surfaced instead of a bare exit code. Reading it from a file avoids the
    # two-pipe deadlock a second PIPE would risk.
    errf = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf, text=True)
    success = False
    try:
        for line in proc.stdout:
            # Parse the unambiguous `out_time=HH:MM:SS.ffffff` field. (`out_time_ms`
            # is milliseconds in some builds and microseconds in others — jellyfin-
            # ffmpeg's ms reading left the bar stuck near zero.)
            if duration and line.startswith("out_time="):
                secs = _parse_out_time(line.split("=", 1)[1].strip())
                if secs is not None:
                    progress_cb(min(1.0, secs / duration))
        code = proc.wait()
        if code != 0:
            errf.seek(0)
            tail = errf.read().decode("utf-8", "replace").strip()[-1500:]
            raise UpscaleError(f"ffmpeg exited {code}: {tail}")
        _replace(src, tmp_out)
        success = True
    finally:
        errf.close()
        if proc.poll() is None:
            proc.kill()
        if not success:
            _cleanup(tmp_out)


def _run_anime4k(src: str, scale: int, progress_cb):
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
    convert on the CPU — ``hwdownload,format=yuv420p`` is rejected as invalid."""
    vfilter = (f"format=nv12,hwupload,"
               f"libplacebo=w=iw*{scale}:h=ih*{scale}:"
               f"custom_shader_path={ANIME4K_SHADER},"
               f"hwdownload,format=nv12")
    _run_single(src, ["-init_hw_device", "vulkan=vk", "-filter_hw_device", "vk"],
                vfilter, CPU_CODEC, progress_cb)


def _cleanup(path: str):
    try:
        os.remove(path)
    except OSError:
        pass
