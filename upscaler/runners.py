"""Upscaler backends. Each produces a 2x (or `scale`x) version of a video file
and atomically replaces the original in place, so the library relink the bot runs
afterwards points at the upscaled data with no extra disk cost.

- ``ffmpeg``     — classical lanczos resize; CPU-only, works everywhere.
- ``realesrgan`` — AI, frame-by-frame via the ncnn-vulkan binary; needs a Vulkan
  device (``/dev/dri``). Uses the video-optimised ``realesr-animevideov3`` model
  (far faster than the general ``realesrgan-x4plus``) and processes the video in
  short segments so the intermediate PNG frames live on a fast scratch dir
  (tmpfs/SSD, ``UPSCALE_TMPDIR``) instead of piling up next to the source on a
  slow USB HDD. Only one segment's frames exist at a time, so disk/RAM use stays
  bounded no matter how long the video is.

The ncnn-vulkan binary can only read/write files or directories (no stdin/stdout
streaming), so a literal ffmpeg->realesrgan->ffmpeg pipe is impossible; the
segment-in-scratch approach is the closest we get to "not touching the slow disk".
"""
import logging
import os
import shutil
import subprocess
import tempfile
import time

log = logging.getLogger("upscaler")

# Only real video files can be upscaled. The bot filters sidecars (subs/audio)
# out before queueing, but stale jobs queued by older bot builds may still name a
# subtitle/audio file — skip those cleanly instead of erroring on a non-video.
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".m2ts", ".flv", ".webm",
}

# Binary + model locations (overridable so the Dockerfile can pin exact paths).
REALESRGAN_BIN    = os.environ.get("REALESRGAN_BIN", "realesrgan-ncnn-vulkan")
REALESRGAN_MODELS = os.environ.get("REALESRGAN_MODELS", "")
# Video-optimised model shipped with the ncnn release. Much lighter per frame
# than realesrgan-x4plus, which is what made the old runs take hours.
REALESRGAN_MODEL  = os.environ.get("REALESRGAN_MODEL", "realesr-animevideov3")

# Fast scratch dir for the intermediate frames. Defaults to /tmp; docker-compose
# points it at a tmpfs (RAM) so the frame churn never hits the media HDD.
FAST_TMPDIR       = os.environ.get("UPSCALE_TMPDIR", "/tmp")
# Seconds of video per segment. Small enough that one segment's upscaled 4K
# frames fit comfortably in the scratch dir; large enough to amortise ffmpeg
# start-up. ~20s ≈ a few hundred frames.
SEGMENT_SECONDS   = int(os.environ.get("UPSCALE_SEGMENT_SECONDS", "20"))

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
        log.info("Vulkan (AI upscaler) available: %s", _vulkan_cached)
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
    """Encoder command fragments, shared by the ffmpeg and ncnn re-encode steps.

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
    return ([],
            ",".join(parts),
            ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"])


def _probe_duration(src: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", src],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def _probe_fps(src: str) -> str:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate",
             "-of", "default=noprint_wrappers=1:nokey=1", src],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        return out or "24000/1001"
    except Exception:
        return "24000/1001"


def _fps_float(fps: str) -> float:
    try:
        if "/" in fps:
            num, den = fps.split("/", 1)
            return float(num) / float(den)
        return float(fps)
    except (ValueError, ZeroDivisionError):
        return 24000.0 / 1001.0


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
            ["ffprobe", "-v", "error", "-select_streams", "v",
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

    if upscaler == "ffmpeg":
        _run_ffmpeg(src, scale, progress_cb)
    elif upscaler == "realesrgan":
        if not has_vulkan():
            raise UpscaleError("no Vulkan GPU (/dev/dri) — the AI upscaler is unavailable")
        _run_ncnn(src, scale, progress_cb)
    else:
        raise UpscaleError(f"unknown upscaler: {upscaler}")


def _run_ffmpeg(src: str, scale: int, progress_cb):
    duration = _probe_duration(src)
    ext = os.path.splitext(src)[1] or ".mkv"
    # Temp next to src: a single sequential write the HDD handles fine, and it
    # keeps the final swap a same-filesystem atomic rename. The lanczos filter is
    # CPU-bound, not disk-bound, so scratch placement doesn't matter here.
    fd, tmp_out = tempfile.mkstemp(suffix=ext, prefix=".upscale_", dir=os.path.dirname(src))
    os.close(fd)
    # lanczos scaling stays on the CPU (quality); only the H.264 encode moves to
    # the GPU when VAAPI is available.
    pre_input, vfilter, codec = _video_encode(f"scale=iw*{scale}:ih*{scale}:flags=lanczos")
    cmd = [
        "ffmpeg", "-y", *pre_input, "-i", src,
        # Keep every stream (all audio dubs, all subtitles, attachments/fonts) —
        # the result replaces the original in place, so a dropped track is lost
        # for good. Only the video stream is filtered; the rest is copied.
        "-map", "0",
        "-vf", vfilter,
        *codec,
        "-c:a", "copy", "-c:s", "copy", "-c:t", "copy",
        "-progress", "pipe:1", "-nostats", tmp_out,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    success = False
    try:
        for line in proc.stdout:
            if duration and line.startswith("out_time_ms="):
                try:
                    ms = int(line.split("=", 1)[1])
                    progress_cb(ms / 1e6 / duration)
                except ValueError:
                    pass
        code = proc.wait()
        if code != 0:
            raise UpscaleError(f"ffmpeg exited {code}")
        _replace(src, tmp_out)
        success = True
    finally:
        if proc.poll() is None:
            proc.kill()
        if not success:
            _cleanup(tmp_out)


def _run_ncnn(src: str, scale: int, progress_cb):
    """Split the video into short segments, upscale each segment's frames with the
    ncnn-vulkan binary on a fast scratch dir, re-encode per segment, then concat
    and re-mux the original audio/subtitles. Only one segment of frames exists on
    disk at a time, so this stays bounded and off the slow media HDD."""
    fps = _probe_fps(src)
    fps_f = _fps_float(fps)
    duration = _probe_duration(src)
    total_frames = max(1, round(duration * fps_f)) if duration else 1
    ext = os.path.splitext(src)[1] or ".mkv"

    os.makedirs(FAST_TMPDIR, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="upscale_", dir=FAST_TMPDIR)
    seg_src = os.path.join(workdir, "seg_src")   # stream-copied source chunks
    seg_enc = os.path.join(workdir, "seg_enc")   # upscaled + re-encoded chunks
    frames_in = os.path.join(workdir, "in")
    frames_out = os.path.join(workdir, "out")
    os.makedirs(seg_src)
    os.makedirs(seg_enc)

    try:
        # 1. Split the video stream into ~SEGMENT_SECONDS chunks (stream copy, so
        #    this is near-instant and lossless). Audio/subs are re-muxed at the end
        #    from the untouched original, so only the video is segmented here.
        _run_ok(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-map", "0:v:0",
             "-c", "copy", "-f", "segment", "-segment_time", str(SEGMENT_SECONDS),
             "-reset_timestamps", "1", os.path.join(seg_src, "s%05d.mkv")],
            "segmenting failed",
        )
        segments = sorted(f for f in os.listdir(seg_src) if f.endswith(".mkv"))
        if not segments:
            raise UpscaleError("no segments produced from source")

        done_frames = 0
        for idx, seg in enumerate(segments):
            seg_path = os.path.join(seg_src, seg)
            # Fresh empty frame dirs per segment.
            shutil.rmtree(frames_in, ignore_errors=True)
            shutil.rmtree(frames_out, ignore_errors=True)
            os.makedirs(frames_in)
            os.makedirs(frames_out)

            # 2. Decode this segment's frames. Map the video stream explicitly and
            #    drop audio/subs so the image2 muxer can't fail stream selection
            #    (-vsync 0 keeps exact source frames).
            _run_ok(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", seg_path,
                 "-map", "0:v:0", "-an", "-sn", "-vsync", "0",
                 os.path.join(frames_in, "%08d.png")],
                "frame extraction failed",
            )
            seg_total = len([f for f in os.listdir(frames_in) if f.endswith(".png")])
            if seg_total == 0:
                continue

            # 3. Upscale the frames with the video-optimised model.
            ncnn_cmd = [REALESRGAN_BIN, "-i", frames_in, "-o", frames_out,
                        "-s", str(scale), "-n", REALESRGAN_MODEL]
            if REALESRGAN_MODELS:
                ncnn_cmd += ["-m", REALESRGAN_MODELS]
            proc = subprocess.Popen(ncnn_cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            # ncnn has no machine-readable progress; poll the output frame count.
            # Reserve the last 10% of the bar for the final concat/mux.
            while proc.poll() is None:
                seg_done = len(os.listdir(frames_out))
                progress_cb(0.9 * (done_frames + seg_done) / total_frames)
                time.sleep(2)
            if proc.returncode != 0:
                raise UpscaleError(f"{REALESRGAN_BIN} exited {proc.returncode}")

            # 4. Re-encode this segment (video only; audio/subs come from original).
            pre_input, vfilter, codec = _video_encode(None)
            _run_ok(
                ["ffmpeg", "-y", "-loglevel", "error", *pre_input,
                 "-framerate", fps, "-i", os.path.join(frames_out, "%08d.png"),
                 *(["-vf", vfilter] if vfilter else []), *codec,
                 os.path.join(seg_enc, f"e{idx:05d}.mkv")],
                "segment re-encode failed",
            )
            done_frames += seg_total
            progress_cb(min(0.9, 0.9 * done_frames / total_frames))

        # 5. Concat the upscaled segments (stream copy) into one video-only file.
        enc_segments = sorted(f for f in os.listdir(seg_enc) if f.endswith(".mkv"))
        if not enc_segments:
            raise UpscaleError("no upscaled segments produced")
        concat_list = os.path.join(workdir, "concat.txt")
        with open(concat_list, "w") as fh:
            for f in enc_segments:
                fh.write(f"file '{os.path.join(seg_enc, f)}'\n")
        video_only = os.path.join(workdir, f"video{ext}")
        _run_ok(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", concat_list, "-c", "copy", video_only],
            "concat failed",
        )

        # 6. Mux the upscaled video with the original audio/subtitles. The output
        #    goes next to src (HDD) so the final swap is a same-fs atomic rename.
        fd, tmp_out = tempfile.mkstemp(suffix=ext, prefix=".upscale_", dir=os.path.dirname(src))
        os.close(fd)
        try:
            _run_ok(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", video_only, "-i", src,
                 "-map", "0:v:0", "-map", "1:a?", "-map", "1:s?",
                 "-c", "copy", tmp_out],
                "final mux failed",
            )
            progress_cb(1.0)
            _replace(src, tmp_out)
        except Exception:
            _cleanup(tmp_out)
            raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_ok(cmd: list[str], errmsg: str):
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise UpscaleError(f"{errmsg}: binary not found: '{cmd[0]}'")
    if proc.returncode != 0:
        # Take the tail so the actual error isn't hidden behind ffmpeg's version banner.
        tail = proc.stderr.strip()[-400:]
        raise UpscaleError(f"{errmsg}: {tail}")


def _cleanup(path: str):
    try:
        os.remove(path)
    except OSError:
        pass
