"""Upscaler backends. Each produces a 2x (or `scale`x) version of a video file
and atomically replaces the original in place, so the library relink the bot runs
afterwards points at the upscaled data with no extra disk cost.

- ``ffmpeg``  — classical lanczos resize; CPU-only, works everywhere.
- ``realesrgan`` / ``waifu2x`` — AI, frame-by-frame via the ncnn-vulkan binaries;
  need a Vulkan device (``/dev/dri``).
- ``video2x`` — the Video2X CLI, which orchestrates ncnn models itself.
"""
import os
import shutil
import subprocess
import tempfile
import time

# Binary + model locations (overridable so the Dockerfile can pin exact paths).
REALESRGAN_BIN    = os.environ.get("REALESRGAN_BIN", "realesrgan-ncnn-vulkan")
REALESRGAN_MODELS = os.environ.get("REALESRGAN_MODELS", "")
WAIFU2X_BIN       = os.environ.get("WAIFU2X_BIN", "waifu2x-ncnn-vulkan")
WAIFU2X_MODELS    = os.environ.get("WAIFU2X_MODELS", "")
VIDEO2X_BIN       = os.environ.get("VIDEO2X_BIN", "video2x")


class UpscaleError(Exception):
    pass


def has_vulkan() -> bool:
    if not os.path.exists("/dev/dri"):
        return False
    try:
        subprocess.run(["vulkaninfo"], capture_output=True, timeout=30, check=True)
        return True
    except Exception:
        return False


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


def _replace(src: str, tmp_out: str):
    """Swap the upscaled file in for the original, preserving the extension so the
    bot's linker still recognises the file."""
    os.replace(tmp_out, src)


def run(job: dict, progress_cb):
    upscaler = job["upscaler"]
    src = job["src_path"]
    scale = int(job["scale"] or 2)
    if not os.path.isfile(src):
        raise UpscaleError(f"source missing: {src}")

    if upscaler == "ffmpeg":
        _run_ffmpeg(src, scale, progress_cb)
    elif upscaler in ("realesrgan", "waifu2x"):
        if not has_vulkan():
            raise UpscaleError("no Vulkan GPU (/dev/dri) — AI upscalers unavailable")
        _run_ncnn(src, scale, upscaler, progress_cb)
    elif upscaler == "video2x":
        if not has_vulkan():
            raise UpscaleError("no Vulkan GPU (/dev/dri) — Video2X unavailable")
        _run_video2x(src, scale, progress_cb)
    else:
        raise UpscaleError(f"unknown upscaler: {upscaler}")


def _run_ffmpeg(src: str, scale: int, progress_cb):
    duration = _probe_duration(src)
    ext = os.path.splitext(src)[1] or ".mkv"
    fd, tmp_out = tempfile.mkstemp(suffix=ext, prefix=".upscale_", dir=os.path.dirname(src))
    os.close(fd)
    cmd = [
        "ffmpeg", "-y", "-i", src,
        # Keep every stream (all audio dubs, all subtitles, attachments/fonts) —
        # the result replaces the original in place, so a dropped track is lost
        # for good. Only the video stream is filtered; the rest is copied.
        "-map", "0",
        "-vf", f"scale=iw*{scale}:ih*{scale}:flags=lanczos",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-c:s", "copy", "-c:t", "copy",
        "-progress", "pipe:1", "-nostats", tmp_out,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        for line in proc.stdout:
            if duration and line.startswith("out_time_ms="):
                try:
                    ms = int(line.split("=", 1)[1])
                    progress_cb(ms / 1e6 / duration)
                except ValueError:
                    pass
        code = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    if code != 0:
        _cleanup(tmp_out)
        raise UpscaleError(f"ffmpeg exited {code}")
    _replace(src, tmp_out)


def _run_ncnn(src: str, scale: int, model: str, progress_cb):
    """Extract frames → upscale each with the ncnn-vulkan binary → reassemble
    with the original audio at the original fps."""
    binary = REALESRGAN_BIN if model == "realesrgan" else WAIFU2X_BIN
    fps = _probe_fps(src)
    ext = os.path.splitext(src)[1] or ".mkv"
    workdir = tempfile.mkdtemp(prefix=".upscale_", dir=os.path.dirname(src))
    frames_in = os.path.join(workdir, "in")
    frames_out = os.path.join(workdir, "out")
    os.makedirs(frames_in)
    os.makedirs(frames_out)
    tmp_out = os.path.join(workdir, f"out{ext}")
    try:
        _run_ok(["ffmpeg", "-y", "-i", src, os.path.join(frames_in, "%08d.png")],
                "frame extraction failed")
        total = len([f for f in os.listdir(frames_in) if f.endswith(".png")]) or 1

        ncnn_cmd = [binary, "-i", frames_in, "-o", frames_out, "-s", str(scale)]
        if model == "realesrgan":
            ncnn_cmd += ["-n", "realesrgan-x4plus"]
            if REALESRGAN_MODELS:
                ncnn_cmd += ["-m", REALESRGAN_MODELS]
        elif WAIFU2X_MODELS:
            ncnn_cmd += ["-m", WAIFU2X_MODELS]
        proc = subprocess.Popen(ncnn_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # ncnn has no machine-readable progress; poll the output frame count.
        while proc.poll() is None:
            done = len(os.listdir(frames_out))
            progress_cb(0.9 * done / total)  # reserve last 10% for re-encode
            time.sleep(2)
        if proc.returncode != 0:
            raise UpscaleError(f"{binary} exited {proc.returncode}")

        _run_ok(
            ["ffmpeg", "-y", "-framerate", fps, "-i", os.path.join(frames_out, "%08d.png"),
             "-i", src, "-map", "0:v:0", "-map", "1:a?", "-map", "1:s?",
             "-c:v", "libx264", "-crf", "18", "-preset", "medium",
             "-pix_fmt", "yuv420p", "-c:a", "copy", "-c:s", "copy", tmp_out],
            "re-encode failed",
        )
        progress_cb(1.0)
        _replace(src, tmp_out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_video2x(src: str, scale: int, progress_cb):
    ext = os.path.splitext(src)[1] or ".mkv"
    fd, tmp_out = tempfile.mkstemp(suffix=ext, prefix=".upscale_", dir=os.path.dirname(src))
    os.close(fd)
    try:
        _run_ok([VIDEO2X_BIN, "-i", src, "-o", tmp_out, "-s", str(scale)],
                "video2x failed")
        progress_cb(1.0)
        _replace(src, tmp_out)
    except Exception:
        _cleanup(tmp_out)
        raise


def _run_ok(cmd: list[str], errmsg: str):
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise UpscaleError(f"{errmsg}: {proc.stderr.strip()[:300]}")


def _cleanup(path: str):
    try:
        os.remove(path)
    except OSError:
        pass
