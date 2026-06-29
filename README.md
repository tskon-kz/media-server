# Media Server

> [Русская версия](README.ru.md)

Jellyfin + qBittorrent + Telegram Bot.

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/mediaserver.git ~/media-server
cd ~/media-server
bash setup.sh
```

`setup.sh` handles everything: installs Docker, asks for credentials, configures qBittorrent and Jellyfin automatically, starts all containers.

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
| `magnet:...` | Add torrent — asks for category |
| `/list` | Torrent list with delete and move buttons |
| `/status` | qBittorrent status |
| `/settings` | Settings: categories, language, qBittorrent password |

## Media flow

```
Bot (magnet) → qBittorrent → ./media/<category>/ ← Jellyfin
```

Categories are managed via `/settings`. Adding or removing a category automatically creates or removes the corresponding Jellyfin library.

## Teardown

```bash
bash teardown.sh
```

Removes containers, images, volumes, `media/`, `data/`, `.env`, `creds.json`. Repository files are untouched.

## Access

- Jellyfin: `http://SERVER_IP:8096`
- qBittorrent: `http://SERVER_IP:8080`
