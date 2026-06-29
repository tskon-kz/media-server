# Media Server

> [English version](README.md)

Jellyfin + qBittorrent + Telegram-бот.

## Быстрый старт

```bash
git clone https://github.com/YOUR_USERNAME/mediaserver.git ~/mediaserver
cd ~/mediaserver
bash setup.sh
```

`setup.sh` устанавливает Docker, запрашивает настройки, пишет `.env`, запускает контейнеры.

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
| `magnet:...` | Добавить торрент |
| `/list` | Список торрентов |
| `/status` | Статус серверов |
| `/setpass <пароль>` | Сменить пароль qBittorrent |
| `/lang` | Сменить язык |

## Сброс

```bash
bash teardown.sh
```

Удаляет контейнеры, образы, volumes, `media/`, `data/`, `.env`, `creds.json`. Файлы репозитория не трогает.

## Как работает медиа

```
Бот (magnet-ссылка) → qBittorrent → ./media/ ← Jellyfin
```

qBittorrent скачивает в папку `./media/` на хосте. Jellyfin читает из той же папки.  
При первом запуске Jellyfin добавь библиотеку и укажи путь `/media`.

## Доступ

- Jellyfin: `http://SERVER_IP:8096`
- qBittorrent: `http://SERVER_IP:8080`
