# Media Server

> [Русская версия](README.ru.md)

Jellyfin + qBittorrent + Telegram Bot.

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/mediaserver.git ~/mediaserver
cd ~/mediaserver
bash setup.sh
```

`setup.sh` installs Docker, asks for credentials, writes `.env`, starts containers.

## CI/CD

Add GitHub secrets: Settings → Secrets → Actions

| Secret | Value |
|--------|-------|
| `SERVER_HOST` | Server IP |
| `SERVER_USER` | SSH username |
| `SERVER_SSH_KEY` | Private SSH key |
| `SSH_PORT` | SSH port |

Every push to `main` deploys automatically.

## Bot commands

| Command | Action |
|---------|--------|
| `magnet:...` | Add torrent |
| `/list` | Torrent list |
| `/status` | Server status |
| `/setpass <pass>` | Change qBittorrent password |
| `/lang` | Switch language |

## Access

- Jellyfin: `http://SERVER_IP:8096`
- qBittorrent: `http://SERVER_IP:8080`
