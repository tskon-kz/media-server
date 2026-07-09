# Upscaler worker: ffmpeg (CPU) + ncnn-vulkan AI binaries (AMD/Intel via /dev/dri).
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# ffmpeg/ffprobe for classical scaling + frame extract/reassemble; Vulkan loader
# and Mesa drivers so the ncnn binaries can use an AMD/Intel iGPU; vulkan-tools
# for the runtime `vulkaninfo` availability check.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libvulkan1 \
        mesa-vulkan-drivers \
        vulkan-tools \
        libgomp1 \
        wget \
        unzip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Prebuilt ncnn-vulkan upscalers (binary + bundled models). Pinned releases,
# normalised so each lives at /opt/<name>/ with the binary at the root and a
# models/ subdir (some release zips nest everything one level deep).
RUN set -eux; \
    for spec in \
        "realesrgan|https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip|realesrgan-ncnn-vulkan" \
        "waifu2x|https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-ubuntu.zip|waifu2x-ncnn-vulkan" \
    ; do \
        name="${spec%%|*}"; rest="${spec#*|}"; url="${rest%%|*}"; bin="${rest##*|}"; \
        wget -q -O /tmp/dl.zip "$url"; \
        mkdir -p "/opt/$name" && unzip -q /tmp/dl.zip -d "/opt/$name"; \
        found="$(find "/opt/$name" -name "$bin" -type f | head -1)"; \
        srcdir="$(dirname "$found")"; \
        if [ "$srcdir" != "/opt/$name" ]; then mv "$srcdir"/* "/opt/$name/"; fi; \
        chmod +x "/opt/$name/$bin"; \
        ln -s "/opt/$name/$bin" "/usr/local/bin/$bin"; \
        rm -f /tmp/dl.zip; \
    done

# Video2X CLI (best-effort — an optional AI backend; if the pip build is
# unavailable the runner reports a clear error at job time instead of at build).
RUN pip install --no-cache-dir video2x || echo "video2x not installed; backend disabled"

ENV REALESRGAN_BIN=/usr/local/bin/realesrgan-ncnn-vulkan \
    WAIFU2X_BIN=/usr/local/bin/waifu2x-ncnn-vulkan \
    REALESRGAN_MODELS=/opt/realesrgan/models \
    WAIFU2X_MODELS=/opt/waifu2x/models \
    DB_PATH=/app/data/media_server.db \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY upscaler/db.py upscaler/runners.py upscaler/main.py ./

CMD ["python", "main.py"]
