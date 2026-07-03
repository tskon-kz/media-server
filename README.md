# Media Server

> [Русская версия](README.ru.md)

Self-hosted media streaming stack: Jellyfin + qBittorrent, fully managed via a Telegram bot. One command to install on any Linux server.

## Features

- Send a magnet link or `.torrent` file to Telegram — bot handles everything
- **Torrent search** via `/search` — searches all Jackett indexers, pick a result to add
- Download notifications with automatic Jellyfin library scan
- Automatic media renaming to Jellyfin-standard paths via hardlinks (no duplicate files)
- Category-based library management (Movies, Series + custom)
- Built-in update system via the bot

## Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/install.sh)
```

## Docs

- [Installation (detailed)](docs/installation.md)
- [Dev Setup](docs/dev-setup.md)
- [Bot Commands](docs/commands.md)
- [Configuration](docs/configuration.md)
- [Troubleshooting & Maintenance](docs/troubleshooting.md)
