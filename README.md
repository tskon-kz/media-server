# Media Server

> [Русская версия](README.ru.md)

Self-hosted media streaming stack: Jellyfin + qBittorrent, fully managed via a Telegram bot. One command to install on any Linux server.

## Features

- **Telegram Mini App** — full web UI via the Menu Button in the chat (torrent list, search, add, settings)
- Add torrents by pasting a magnet link or uploading a `.torrent` file in the Mini App
- **Torrent search** via the Mini App — searches all Jackett indexers, pick a result to add
- Jackett admin password management from the bot (change, remove)
- Download notifications with automatic Jellyfin library scan
- **Two hardlink modes**: original file structure (default) or automatic Jellyfin-standard renaming — switchable per-torrent or globally
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
