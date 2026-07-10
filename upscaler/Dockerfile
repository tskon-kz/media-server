# Upscaler worker: jellyfin-ffmpeg (libplacebo + VAAPI, AMD/Intel via /dev/dri).
# Pinned to bookworm so the base debian release can't drift out from under the
# hardcoded `bookworm` jellyfin apt line below.
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# jellyfin-ffmpeg ships the `libplacebo` filter the Anime4K backend needs (stock
# Debian ffmpeg has none) plus VAAPI H.264 encode and libx264. Pulled from the
# Jellyfin apt repo. Mesa Vulkan/VAAPI drivers + vulkan-tools/vainfo stay so the
# runtime `vulkaninfo`/`vainfo` probes reflect the host GPU's real capability.
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends \
        gnupg curl wget ca-certificates \
        libvulkan1 mesa-vulkan-drivers vulkan-tools \
        mesa-va-drivers vainfo; \
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://repo.jellyfin.org/jellyfin_team.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/jellyfin.gpg; \
    echo "deb [signed-by=/etc/apt/keyrings/jellyfin.gpg] https://repo.jellyfin.org/debian bookworm main" \
        > /etc/apt/sources.list.d/jellyfin.list; \
    apt-get update && apt-get install -y --no-install-recommends jellyfin-ffmpeg7; \
    rm -rf /var/lib/apt/lists/*

# Anime4K neural GLSL shaders, concatenated into one libplacebo hook file (Mode A:
# clamp highlights -> CNN restore -> CNN 2x upscale, medium variants — light enough
# for an iGPU). Pinned to a release tag so the build is reproducible.
RUN set -eux; \
    mkdir -p /opt/anime4k; \
    base="https://raw.githubusercontent.com/bloc97/Anime4K/v4.0.1/glsl"; \
    for f in Restore/Anime4K_Clamp_Highlights.glsl \
             Restore/Anime4K_Restore_CNN_M.glsl \
             Upscale/Anime4K_Upscale_CNN_x2_M.glsl; do \
        wget -q "$base/$f" -O - >> /opt/anime4k/anime4k.glsl; \
        echo >> /opt/anime4k/anime4k.glsl; \
    done; \
    test -s /opt/anime4k/anime4k.glsl

ENV FFMPEG_BIN=/usr/lib/jellyfin-ffmpeg/ffmpeg \
    FFPROBE_BIN=/usr/lib/jellyfin-ffmpeg/ffprobe \
    ANIME4K_SHADER=/opt/anime4k/anime4k.glsl \
    DB_PATH=/app/data/media_server.db \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY upscaler/db.py upscaler/runners.py upscaler/main.py ./

CMD ["python", "main.py"]
