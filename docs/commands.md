# Bot Commands

## Adding torrents

Open the Mini App (tap **Open App** or the Menu Button) and go to the **Add** tab. Paste a magnet link or upload a `.torrent` file, then pick a category. When the download finishes, you get a notification and Jellyfin scans the library automatically.

## Mini App

All management is done through the **Telegram Mini App** — tap the **Open App** button in the chat (or the Menu Button in the header). No slash commands needed.

| Tab | What you can do |
|-----|-----------------|
| Torrents | Full torrent list with status icons, delete, move, and structure controls |
| Add | Paste a magnet link or upload a `.torrent` file, then pick a category |
| Search | Search all Jackett indexers — tap a result to add it |
| Status | Current download / upload speeds |
| Settings | Categories, rename mode, qBittorrent creds, Jackett password, Jellyfin users, update |

## Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with the **Open App** button |
| `/update` | Check for updates, update now, or switch channel (Stable ↔ Edge) |

Use `/update` when the Mini App is unavailable — it exposes the same update screen as Mini App → Settings → Update, without needing the app to load.

---

## Torrent list (Mini App → Torrents tab)

Shows all torrents with status icons:

| Icon | Meaning |
|------|---------|
| ⬇️ | Downloading |
| ✅ | Done |
| ⏸ | Paused |
| 🌱 | Seeding |
| ❌ | Error |

Per-torrent actions:

| Button | Action |
|--------|--------|
| 🗑 | Delete torrent with files |
| 📁 | Move to a different category |
| 🗂 | Manage file structure (pretty names / original / delete hardlinks) |

---

## Search (Mini App → Search tab)

Searches all indexers configured in Jackett and shows the top 30 results sorted by seeders. Results are displayed as a numbered list (title + seeders · size · indexer · date), paginated 5 per page. Tap a result to start the normal category-picker flow.

**Requires:** Jackett running with at least one indexer configured. The API key is read automatically — no manual configuration needed.

---

## Settings (Mini App → Settings tab)

| Section | What you can do |
|---------|-----------------|
| Categories | Add, rename, delete categories. Each maps to a folder and a Jellyfin library |
| Media Library | Rebuild hardlinks for all torrents: smart names, original structure, or delete |
| Language | Switch between Russian and English |
| Update | Check for updates and apply with one tap |
| qBittorrent | Manage credentials and connection |
| Jackett | Change or remove the admin password for the Jackett web UI |
| Jellyfin users | Add and delete Jellyfin user accounts |
| Auto-structure toggle | Switch between "original structure" and "smart names" for new downloads |
| Quick links | Open qBittorrent / Jellyfin / Jackett web UI directly from the menu |

**Auto-structure mode** — the toggle in settings controls what happens when a torrent finishes downloading:
- **Original structure** (`flat`) — hardlinks are created with the same filenames and folder layout as the download, no parsing.
- **Smart names** (`pretty`) — filenames are parsed and hardlinked to Jellyfin-standard paths (`Show/Season 01/Show - S01E04.mkv`).

You can also change the structure of any individual torrent at any time via the 🗂 Structure button in the Torrents tab, regardless of the active mode.

**Media Library** — applies a structure mode globally to all torrents at once: rebuilds all hardlinks as pretty, as flat, or removes all hardlinks.

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

The bot checks for a new version every 6 hours and on startup. When an update is available, it sends a notification. To update manually: Mini App → **Settings** → **Update** → **Update now**. The bot restarts automatically within ~1 minute.
