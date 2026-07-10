import json
import os
import sqlite3
from config import DATA_DIR, DEFAULT_CATS
from lang import ru, en

_LANGS = {"ru": ru.M, "en": en.M}
_lang = "ru"

DB_PATH = f"{DATA_DIR}/media_server.db"
_conn: sqlite3.Connection | None = None


def _create_tables():
    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS categories (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            path    TEXT NOT NULL,
            jf_type TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS torrent_states (
            hash  TEXT PRIMARY KEY,
            state TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_states (
            user_id         INTEGER PRIMARY KEY,
            state           TEXT,
            pending_json    TEXT,
            pending_torrent BLOB
        );
        CREATE TABLE IF NOT EXISTS rename_jobs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            torrent_hash TEXT NOT NULL,
            src_path     TEXT NOT NULL,
            cat_path     TEXT NOT NULL,
            jf_type      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS disk_entries (
            disk_id  TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            cat_id   INTEGER NOT NULL,
            size     INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS upscale_jobs (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            disk_id  TEXT NOT NULL,
            src_path TEXT NOT NULL,
            upscaler TEXT NOT NULL,
            scale    INTEGER NOT NULL DEFAULT 2,
            status   TEXT NOT NULL DEFAULT 'queued',
            progress REAL NOT NULL DEFAULT 0,
            error    TEXT,
            user_id  INTEGER,
            notified INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS done_notified (
            hash TEXT PRIMARY KEY
        );
    """)
    _conn.commit()


def _migrate():
    # Drop old rename_jobs schema (had dst_path/status) and recreate.
    try:
        _conn.execute("SELECT dst_path FROM rename_jobs LIMIT 1")
        _conn.execute("DROP TABLE rename_jobs")
        _conn.execute("""
            CREATE TABLE rename_jobs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                torrent_hash TEXT NOT NULL,
                src_path     TEXT NOT NULL,
                cat_path     TEXT NOT NULL,
                jf_type      TEXT NOT NULL
            )
        """)
        _conn.commit()
    except Exception:
        pass


def init():
    global _conn, _lang
    os.makedirs(DATA_DIR, exist_ok=True)
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _create_tables()
    _migrate()

    _conn.execute("INSERT OR IGNORE INTO config VALUES ('lang', 'ru')")
    _conn.execute("INSERT OR IGNORE INTO config VALUES ('qb_user', 'admin')")
    _conn.execute("INSERT OR IGNORE INTO config VALUES ('qb_pass', 'adminadmin')")
    _conn.commit()

    # Persist default categories to DB if never explicitly configured.
    if not _conn.execute("SELECT 1 FROM config WHERE key='cats_init'").fetchone():
        for c in DEFAULT_CATS:
            _conn.execute(
                "INSERT OR IGNORE INTO categories (name, path, jf_type) VALUES (?, ?, ?)",
                (c["name"], c["path"], c["jf_type"]),
            )
        _conn.execute("INSERT OR IGNORE INTO config VALUES ('cats_init', '1')")
        _conn.commit()

    row = _conn.execute("SELECT value FROM config WHERE key='lang'").fetchone()
    _lang = row[0] if row else "ru"


# ---- generic config ----

def get_config(key: str, default: str = "") -> str:
    row = _conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row[0] if row and row[0] is not None else default


def set_config(key: str, value: str):
    _conn.execute("INSERT OR REPLACE INTO config VALUES (?, ?)", (key, value))
    _conn.commit()


# ---- i18n ----

def t(key, **kw) -> str:
    s = _LANGS[_lang][key]
    return s.format(**kw) if kw else s


def set_lang(code: str):
    global _lang
    _lang = code
    set_config("lang", code)


# ---- qBittorrent credentials ----

def get_creds() -> tuple[str, str]:
    return get_config("qb_user", "admin"), get_config("qb_pass", "adminadmin")


def get_qb_status() -> str:
    return get_config("qb_conn_status", "unknown")


def set_qb_status(status: str):
    set_config("qb_conn_status", status)


# ---- categories ----

def load_cats() -> list[dict]:
    rows = _conn.execute("SELECT id, name, path, jf_type FROM categories ORDER BY id").fetchall()
    return [{"id": r[0], "name": r[1], "path": r[2], "jf_type": r[3]} for r in rows]


def save_cats(cats: list[dict]):
    existing_ids = {r[0] for r in _conn.execute("SELECT id FROM categories").fetchall()}
    new_ids = {c["id"] for c in cats if "id" in c}

    for cid in existing_ids - new_ids:
        _conn.execute("DELETE FROM categories WHERE id=?", (cid,))

    for c in cats:
        if "id" in c:
            _conn.execute(
                "UPDATE categories SET name=?, path=?, jf_type=? WHERE id=?",
                (c["name"], c["path"], c["jf_type"], c["id"]),
            )
        else:
            _conn.execute(
                "INSERT INTO categories (name, path, jf_type) VALUES (?, ?, ?)",
                (c["name"], c["path"], c["jf_type"]),
            )

    _conn.execute("INSERT OR IGNORE INTO config VALUES ('cats_init', '1')")
    _conn.commit()


# ---- torrent states ----

def load_states() -> dict:
    return {r[0]: r[1] for r in _conn.execute("SELECT hash, state FROM torrent_states").fetchall()}


def save_states(states: dict):
    if states:
        _conn.executemany(
            "INSERT OR REPLACE INTO torrent_states VALUES (?, ?)", states.items()
        )
        placeholders = ",".join("?" * len(states))
        _conn.execute(
            f"DELETE FROM torrent_states WHERE hash NOT IN ({placeholders})",
            list(states.keys()),
        )
    else:
        _conn.execute("DELETE FROM torrent_states")
    _conn.commit()


def has_done_notified(torrent_hash: str) -> bool:
    return bool(_conn.execute("SELECT 1 FROM done_notified WHERE hash=?", (torrent_hash,)).fetchone())


def mark_done_notified(torrent_hash: str):
    _conn.execute("INSERT OR IGNORE INTO done_notified VALUES (?)", (torrent_hash,))
    _conn.commit()


def clear_done_notified(torrent_hash: str):
    _conn.execute("DELETE FROM done_notified WHERE hash=?", (torrent_hash,))
    _conn.commit()


# ---- user conversation state ----

def get_user_state(user_id: int) -> str | None:
    row = _conn.execute("SELECT state FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    return row[0] if row else None


def set_user_state(user_id: int, state: str):
    _conn.execute(
        "INSERT INTO user_states (user_id, state) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state",
        (user_id, state),
    )
    _conn.commit()


def clear_user_state(user_id: int):
    _conn.execute("UPDATE user_states SET state=NULL WHERE user_id=?", (user_id,))
    _conn.commit()


def get_pending(user_id: int, key: str, default=None):
    row = _conn.execute("SELECT pending_json FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    if not row or not row[0]:
        return default
    return json.loads(row[0]).get(key, default)


def set_pending(user_id: int, key: str, value):
    row = _conn.execute("SELECT pending_json FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    data = json.loads(row[0]) if row and row[0] else {}
    data[key] = value
    _conn.execute(
        "INSERT INTO user_states (user_id, pending_json) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET pending_json=excluded.pending_json",
        (user_id, json.dumps(data)),
    )
    _conn.commit()


def pop_pending(user_id: int, key: str, default=None):
    row = _conn.execute("SELECT pending_json FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    if not row or not row[0]:
        return default
    data = json.loads(row[0])
    val = data.pop(key, default)
    _conn.execute(
        "UPDATE user_states SET pending_json=? WHERE user_id=?",
        (json.dumps(data) if data else None, user_id),
    )
    _conn.commit()
    return val


def get_pending_torrent(user_id: int) -> bytes | None:
    row = _conn.execute("SELECT pending_torrent FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    return bytes(row[0]) if row and row[0] else None


def set_pending_torrent(user_id: int, data: bytes):
    _conn.execute(
        "INSERT INTO user_states (user_id, pending_torrent) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET pending_torrent=excluded.pending_torrent",
        (user_id, data),
    )
    _conn.commit()


def pop_pending_torrent(user_id: int) -> bytes | None:
    row = _conn.execute("SELECT pending_torrent FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    if not row or not row[0]:
        return None
    data = bytes(row[0])
    _conn.execute("UPDATE user_states SET pending_torrent=NULL WHERE user_id=?", (user_id,))
    _conn.commit()
    return data


# ---- rename jobs ----

def _row_to_job(row) -> dict:
    return {
        "id": row[0], "torrent_hash": row[1], "src_path": row[2],
        "cat_path": row[3], "jf_type": row[4],
    }


def add_rename_job(torrent_hash: str, src_path: str, cat_path: str, jf_type: str) -> int:
    cur = _conn.execute(
        "INSERT INTO rename_jobs (torrent_hash, src_path, cat_path, jf_type) VALUES (?, ?, ?, ?)",
        (torrent_hash, src_path, cat_path, jf_type),
    )
    _conn.commit()
    return cur.lastrowid


def get_rename_job(job_id: int) -> dict | None:
    row = _conn.execute(
        "SELECT id, torrent_hash, src_path, cat_path, jf_type FROM rename_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    return _row_to_job(row) if row else None


def get_rename_jobs_by_hash(torrent_hash: str) -> list[dict]:
    rows = _conn.execute(
        "SELECT id, torrent_hash, src_path, cat_path, jf_type FROM rename_jobs WHERE torrent_hash=?",
        (torrent_hash,),
    ).fetchall()
    return [_row_to_job(r) for r in rows]


def get_pending_rename_jobs() -> list[dict]:
    rows = _conn.execute(
        "SELECT id, torrent_hash, src_path, cat_path, jf_type FROM rename_jobs"
    ).fetchall()
    return [_row_to_job(r) for r in rows]


def delete_rename_job(job_id: int):
    _conn.execute("DELETE FROM rename_jobs WHERE id=?", (job_id,))
    _conn.commit()


def delete_rename_jobs_by_hash(torrent_hash: str):
    _conn.execute("DELETE FROM rename_jobs WHERE torrent_hash=?", (torrent_hash,))
    _conn.commit()


def delete_all_rename_jobs():
    _conn.execute("DELETE FROM rename_jobs")
    _conn.commit()


# ---- disk entries ----

def upsert_disk_entry(disk_id: str, name: str, cat_id: int, size: int):
    _conn.execute(
        "INSERT OR REPLACE INTO disk_entries (disk_id, name, cat_id, size) VALUES (?, ?, ?, ?)",
        (disk_id, name, cat_id, size),
    )
    _conn.commit()


def upsert_disk_entries_batch(rows: list[tuple[str, str, int, int]]):
    _conn.executemany(
        "INSERT OR REPLACE INTO disk_entries (disk_id, name, cat_id, size) VALUES (?, ?, ?, ?)",
        rows,
    )
    _conn.commit()


def delete_disk_entry(disk_id: str):
    _conn.execute("DELETE FROM disk_entries WHERE disk_id=?", (disk_id,))
    _conn.commit()


def update_disk_entry_size(disk_id: str, size: int):
    _conn.execute("UPDATE disk_entries SET size=? WHERE disk_id=?", (size, disk_id))
    _conn.commit()


def load_disk_entries() -> dict[str, dict]:
    rows = _conn.execute("SELECT disk_id, name, cat_id, size FROM disk_entries").fetchall()
    return {r[0]: {"name": r[1], "cat_id": r[2], "size": r[3]} for r in rows}


# ---- upscale jobs ----
#
# The upscaler worker container writes to this same table (status/progress/error)
# over the shared SQLite file; the bot only queues jobs, reads state for the UI,
# and finalises finished ones (relink + Jellyfin refresh + notify).

def _row_to_upscale_job(row) -> dict:
    return {
        "id": row[0], "disk_id": row[1], "src_path": row[2], "upscaler": row[3],
        "scale": row[4], "status": row[5], "progress": row[6], "error": row[7],
        "user_id": row[8], "notified": row[9],
    }


_UPSCALE_COLS = "id, disk_id, src_path, upscaler, scale, status, progress, error, user_id, notified"


def add_upscale_job(disk_id: str, src_path: str, upscaler: str, user_id: int | None, scale: int = 2) -> int:
    cur = _conn.execute(
        "INSERT INTO upscale_jobs (disk_id, src_path, upscaler, scale, user_id) VALUES (?, ?, ?, ?, ?)",
        (disk_id, src_path, upscaler, scale, user_id),
    )
    _conn.commit()
    return cur.lastrowid


def get_upscale_jobs_by_disk_id(disk_id: str) -> list[dict]:
    rows = _conn.execute(
        f"SELECT {_UPSCALE_COLS} FROM upscale_jobs WHERE disk_id=?", (disk_id,)
    ).fetchall()
    return [_row_to_upscale_job(r) for r in rows]


def get_active_upscale_disk_ids() -> dict[str, float]:
    """Map disk_id -> mean progress for torrents with queued/running jobs (for the UI).

    Averages over *all* jobs of the batch (finished ones count as progress=1.0), so
    the bar climbs toward 100% as files complete. Averaging only queued/running jobs
    dropped finished ones from the mean, pinning multi-file batches near zero."""
    rows = _conn.execute(
        "SELECT disk_id, AVG(progress) FROM upscale_jobs "
        "WHERE disk_id IN (SELECT disk_id FROM upscale_jobs "
        "WHERE status IN ('queued', 'running')) GROUP BY disk_id"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_finished_upscale_disk_ids() -> list[str]:
    """disk_ids where no job is still queued/running but at least one is unnotified."""
    rows = _conn.execute(
        "SELECT disk_id FROM upscale_jobs GROUP BY disk_id "
        "HAVING SUM(status IN ('queued', 'running')) = 0 AND SUM(notified = 0) > 0"
    ).fetchall()
    return [r[0] for r in rows]


def mark_upscale_disk_notified(disk_id: str):
    _conn.execute("UPDATE upscale_jobs SET notified=1 WHERE disk_id=?", (disk_id,))
    _conn.commit()


def delete_upscale_jobs_by_disk_id(disk_id: str):
    _conn.execute("DELETE FROM upscale_jobs WHERE disk_id=?", (disk_id,))
    _conn.commit()


# ---- update notifications ----

def has_notified_update(version: str) -> bool:
    return bool(_conn.execute(
        "SELECT 1 FROM config WHERE key=?", (f"notified_v{version}",)
    ).fetchone())


def mark_update_notified(version: str):
    _conn.execute("INSERT OR IGNORE INTO config VALUES (?, '1')", (f"notified_v{version}",))
    _conn.commit()
