# Media Server

Домашний медиасервер: Jellyfin + qBittorrent + Telegram Bot.

## Быстрый старт (на сервере)

```bash
git clone https://github.com/ВАШ_НИКНЕЙМ/mediaserver.git ~/mediaserver
cd ~/mediaserver
bash setup.sh
```

## GitHub Actions (CD)

В настройках репозитория → Settings → Secrets добавь:

| Secret | Значение |
|--------|----------|
| `SERVER_HOST` | IP сервера |
| `SERVER_USER` | Пользователь SSH |
| `SERVER_SSH_KEY` | Приватный SSH ключ |

После этого каждый `git push` в `main` автоматически обновит сервер.

## Команды Telegram бота

| Команда | Действие |
|---------|----------|
| `magnet:...` | Добавить торрент |
| `/list` | Список загрузок |
| `/status` | Статус серверов |

## Доступ

- Jellyfin: `http://SERVER_IP:8096`
- qBittorrent WebUI: `http://SERVER_IP:8080`
