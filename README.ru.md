# Media Server

> [English version](README.md)

Jellyfin + qBittorrent + Telegram-бот.

## Быстрый старт

```bash
git clone https://github.com/YOUR_USERNAME/mediaserver.git ~/media-server
cd ~/media-server
bash setup.sh
```

`setup.sh` делает всё сам: устанавливает Docker, запрашивает настройки, автоматически конфигурирует qBittorrent и Jellyfin, запускает контейнеры.

## CI/CD

Добавь секреты: Settings → Secrets → Actions

| Секрет | Значение |
|--------|----------|
| `SERVER_HOST` | IP сервера |
| `SERVER_USER` | Пользователь SSH |
| `SERVER_SSH_KEY` | Приватный SSH ключ |
| `SSH_PORT` | SSH порт |

Каждый пуш в `main` деплоит автоматически.

## Команды бота

| Команда | Действие |
|---------|----------|
| `magnet:...` | Добавить торрент — спросит категорию |
| `/list` | Список торрентов с кнопками удаления и перемещения |
| `/status` | Статус qBittorrent |
| `/settings` | Настройки: категории, язык, пароль qBittorrent |

## Как работает медиа

```
Бот (magnet) → qBittorrent → ./media/<категория>/ ← Jellyfin
```

Категории управляются через `/settings`. При добавлении или удалении категории библиотека в Jellyfin создаётся или удаляется автоматически.

## Сброс

```bash
bash teardown.sh
```

Удаляет контейнеры, образы, volumes, `media/`, `data/`, `.env`, `creds.json`. Файлы репозитория не трогает.

## Доступ

- Jellyfin: `http://SERVER_IP:8096`
- qBittorrent: `http://SERVER_IP:8080`
