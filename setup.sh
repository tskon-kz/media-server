#!/bin/bash
set -e

echo "=== Media Server Setup ==="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "Устанавливаю Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Docker установлен. Перезапусти сессию или выполни: newgrp docker"
fi

# Проверка .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  ВАЖНО: Заполни файл .env перед продолжением:"
    echo "   nano .env"
    echo ""
    echo "Нужно указать:"
    echo "  BOT_TOKEN   — от @BotFather в Telegram"
    echo "  ALLOWED_USER — твой Telegram ID (узнай у @userinfobot)"
    echo "  SERVER_IP   — IP этого сервера"
    echo ""
    read -p "Нажми Enter после заполнения .env..."
fi

# Создаём папки
mkdir -p media data/jellyfin/config data/jellyfin/cache data/qbittorrent/config

# Запуск
echo "Запускаю контейнеры..."
docker compose pull
docker compose up -d

echo ""
echo "=== Готово! ==="
echo "Jellyfin:     http://$(grep SERVER_IP .env | cut -d= -f2):8096"
echo "qBittorrent:  http://$(grep SERVER_IP .env | cut -d= -f2):8080"
echo ""
echo "Первый вход qBittorrent — логин: admin / пароль: adminadmin"
echo "После смени пароль в Settings → Web UI и обнови QB_PASS в .env"
