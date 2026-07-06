# Bot Commands

## Adding torrents

Send a **magnet link** or a **.torrent file** directly to the chat. The bot will ask which category to save it to, then add it to qBittorrent. When the download finishes, you get a notification and Jellyfin scans the library automatically.

## Commands

| Command | Description |
|---------|-------------|
| `/list` | Torrent list with status icons and action buttons |
| `/search <query>` | Search all Jackett indexers and pick a torrent to add |
| `/status` | Current download / upload speeds |
| `/scan` | Trigger a Jellyfin library scan |
| `/settings` | Settings menu |

---

## `/search`

Searches all indexers configured in Jackett and shows the top 30 results sorted by seeders.

```
/search Breaking Bad
```

Or just `/search` — the bot will ask for the query.

Results are displayed as a numbered list in the message body (title + seeders · size · indexer · date), paginated 5 per page with `←/→` navigation. Tap the number button for a result to start the normal category-picker flow, identical to sending a magnet link manually.

The search is also accessible directly from `/list` via the **🔍 Поиск Jackett** button.

**Requires:** Jackett running with at least one indexer configured. The API key is read automatically — no manual configuration needed.

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
| 🗂 | Manage file structure (pretty names / original / delete hardlinks) |

The `/list` view also has two search shortcut buttons: **🔍 Search torrents** (opens an external torrent search site) and **🔍 Поиск Jackett** (triggers a Jackett search in-bot).

---

## `/settings`

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

**Auto-structure mode** — the toggle in the main settings menu controls what happens when a torrent finishes downloading:
- **Original structure** (`flat`) — hardlinks are created with the same filenames and folder layout as the download, no parsing.
- **Smart names** (`pretty`) — filenames are parsed and hardlinked to Jellyfin-standard paths (`Show/Season 01/Show - S01E04.mkv`).

The current mode is shown on the toggle button (the checkmark ✓ marks the active one). You can also change the structure of any individual torrent at any time via the 🗂 Structure button in `/list` edit mode, regardless of the active mode.

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

The bot checks for a new version every 6 hours and on startup. When an update is available, it sends a notification. To update manually: `/settings` → **Update** → **Update now**. The bot restarts automatically within ~1 minute.
