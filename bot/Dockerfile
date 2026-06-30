FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
RUN uv pip install --system --no-cache .

COPY bot/bot.py .
COPY lang/ ./lang/

ARG VERSION=dev
ENV APP_VERSION=$VERSION

CMD ["python", "bot.py"]
