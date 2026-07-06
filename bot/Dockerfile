# --- Stage 1: build the React SPA (no Node in the final image) ---
FROM node:20-slim AS webapp
WORKDIR /webapp
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci
COPY webapp/ ./
RUN npm run build

# --- Stage 2: Python bot + built SPA ---
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
RUN uv pip install --system --no-cache .

COPY bot/main.py bot/config.py bot/store.py bot/api.py bot/keyboards.py ./
COPY bot/parser/ ./parser/
COPY bot/handlers/ ./handlers/
COPY bot/webapp/ ./webapp/
COPY lang/ ./lang/
COPY --from=webapp /webapp/dist ./webapp-dist

ARG VERSION=dev
ENV APP_VERSION=$VERSION

CMD ["python", "main.py"]
