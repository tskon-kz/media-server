# Bot Commands

## Adding torrents

Send a **magnet link** or a **.torrent file** directly to the chat. The bot will ask which category to save it to, then add it to qBittorrent. When the download finishes, you get a notification and Jellyfin scans the library automatically.

## Commands

| Command | Description |
|---------|-------------|
| `/list` | Torrent list with status icons and action buttons |
| `/status` | Current download / upload speeds |
| `/scan` | Trigger a Jellyfin library scan |
| `/settings` | Settings menu |

---

## `/list`

Shows all torrents with status icons:

| Icon | Meaning |
|------|---------|
| ⬇️ | Downloading |
| ✅ | Done |
| ⏸ | Paused |
| 🌱 | Seeding |
| ❌ | Error |

**Edit mode** — switch to per-torrent action buttons:

| Button | Action |
|--------|--------|
| 🗑 | Delete torrent with files |
| 📁 | Move to a different category |
| 🔄 | Re-parse filenames and recreate hardlinks |

---

## `/settings`

| Section | What you can do |
|---------|-----------------|
| Categories | Add, rename, delete categories. Each maps to a folder and a Jellyfin library |
| Language | Switch between Russian and English |
| Jellyfin users | Add and delete Jellyfin user accounts |
| Update | Check for updates and apply with one tap |
| Quick links | Open qBittorrent / Jellyfin web UI directly from the menu |

---

## Automatic media renaming

When a torrent finishes, the bot creates **hardlinks** at Jellyfin-standard paths so the media server identifies them correctly — without touching the original files (qBittorrent keeps seeding normally).

**TV shows:**
```
Series Name/Season 01/Series Name - S01E04.mkv
```

**Movies:**
```
Movie Title (2023)/Movie Title (2023).mkv
```

Filenames are parsed with [guessit](https://guessit.readthedocs.io). If a file can't be parsed automatically, the bot sends a prompt:

| Option | Action |
|--------|--------|
| Enter manually | Type `S01E04` or `Title (Year)` to create the hardlink |
| Keep as-is | Create a flat hardlink without renaming |
| Skip | Leave the file in place, don't create a hardlink |

When a torrent is deleted via the bot, all its hardlinks are removed automatically.

---

## Updates

The bot checks for a new version every 6 hours and on startup. When an update is available, it sends a notification. To update manually: `/settings` → **Update** → **Update now**. The bot restarts automatically within ~1 minute.
