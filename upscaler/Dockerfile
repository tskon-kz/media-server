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

# Prebuilt Real-ESRGAN ncnn-vulkan upscaler (binary + bundled models, including
# the video-optimised realesr-animevideov3 model the runner uses). Pinned release,
# normalised to /opt/realesrgan/ with the binary at the root and a models/ subdir
# (the release zip nests everything one level deep).
RUN set -eux; \
    bin="realesrgan-ncnn-vulkan"; \
    url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip"; \
    wget -q -O /tmp/dl.zip "$url"; \
    mkdir -p /opt/realesrgan && unzip -q /tmp/dl.zip -d /opt/realesrgan; \
    found="$(find /opt/realesrgan -name "$bin" -type f | head -1)"; \
    srcdir="$(dirname "$found")"; \
    if [ "$srcdir" != "/opt/realesrgan" ]; then mv "$srcdir"/* /opt/realesrgan/; fi; \
    chmod +x "/opt/realesrgan/$bin"; \
    ln -s "/opt/realesrgan/$bin" "/usr/local/bin/$bin"; \
    rm -f /tmp/dl.zip

ENV REALESRGAN_BIN=/usr/local/bin/realesrgan-ncnn-vulkan \
    REALESRGAN_MODELS=/opt/realesrgan/models \
    DB_PATH=/app/data/media_server.db \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY upscaler/db.py upscaler/runners.py upscaler/main.py ./

CMD ["python", "main.py"]
