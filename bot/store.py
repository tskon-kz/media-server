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
            dst_path     TEXT,
            cat_path     TEXT NOT NULL,
            jf_type      TEXT NOT NULL,
            status       TEXT NOT NULL
        );
    """)
    _conn.commit()


def init():
    global _conn, _lang
    os.makedirs(DATA_DIR, exist_ok=True)
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _create_tables()

    # seed defaults (INSERT OR IGNORE — won't overwrite existing values)
    _conn.execute("INSERT OR IGNORE INTO config VALUES ('lang', 'ru')")
    _conn.execute("INSERT OR IGNORE INTO config VALUES ('qb_user', 'admin')")
    _conn.execute("INSERT OR IGNORE INTO config VALUES ('qb_pass', 'adminadmin')")
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
    """Returns 'unknown', 'ok', or 'error'."""
    return get_config("qb_conn_status", "unknown")


def set_qb_status(status: str):
    set_config("qb_conn_status", status)


# ---- categories ----

def load_cats() -> list[dict]:
    if not _conn.execute("SELECT 1 FROM config WHERE key='cats_init'").fetchone():
        return DEFAULT_CATS.copy()
    rows = _conn.execute("SELECT name, path, jf_type FROM categories ORDER BY id").fetchall()
    return [{"name": r[0], "path": r[1], "jf_type": r[2]} for r in rows]


def save_cats(cats: list[dict]):
    _conn.execute("DELETE FROM categories")
    for c in cats:
        _conn.execute(
            "INSERT INTO categories (name, path, jf_type) VALUES (?, ?, ?)",
            (c["name"], c["path"], c["jf_type"])
        )
    _conn.execute("INSERT OR IGNORE INTO config VALUES ('cats_init', '1')")
    _conn.commit()


# ---- torrent states ----

def load_states() -> dict:
    return {r[0]: r[1] for r in _conn.execute("SELECT hash, state FROM torrent_states").fetchall()}


def save_states(states: dict):
    _conn.execute("DELETE FROM torrent_states")
    _conn.executemany("INSERT INTO torrent_states VALUES (?, ?)", states.items())
    _conn.commit()


# ---- user conversation state ----

def get_user_state(user_id: int) -> str | None:
    row = _conn.execute("SELECT state FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    return row[0] if row else None


def set_user_state(user_id: int, state: str):
    _conn.execute(
        "INSERT INTO user_states (user_id, state) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state",
        (user_id, state)
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
        (user_id, json.dumps(data))
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
        (json.dumps(data) if data else None, user_id)
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
        (user_id, data)
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
        "dst_path": row[3], "cat_path": row[4], "jf_type": row[5], "status": row[6],
    }


def add_rename_job(torrent_hash: str, src_path: str, cat_path: str, jf_type: str,
                   status: str, dst_path: str | None = None) -> int:
    cur = _conn.execute(
        "INSERT INTO rename_jobs (torrent_hash, src_path, dst_path, cat_path, jf_type, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (torrent_hash, src_path, dst_path, cat_path, jf_type, status),
    )
    _conn.commit()
    return cur.lastrowid


def get_rename_job(job_id: int) -> dict | None:
    row = _conn.execute(
        "SELECT id, torrent_hash, src_path, dst_path, cat_path, jf_type, status "
        "FROM rename_jobs WHERE id=?", (job_id,)
    ).fetchone()
    return _row_to_job(row) if row else None


def get_rename_jobs_by_hash(torrent_hash: str) -> list[dict]:
    rows = _conn.execute(
        "SELECT id, torrent_hash, src_path, dst_path, cat_path, jf_type, status "
        "FROM rename_jobs WHERE torrent_hash=?", (torrent_hash,)
    ).fetchall()
    return [_row_to_job(r) for r in rows]


def get_pending_rename_jobs() -> list[dict]:
    rows = _conn.execute(
        "SELECT id, torrent_hash, src_path, dst_path, cat_path, jf_type, status "
        "FROM rename_jobs WHERE status='pending_manual'"
    ).fetchall()
    return [_row_to_job(r) for r in rows]


def update_rename_job(job_id: int, status: str, dst_path: str | None = None):
    _conn.execute(
        "UPDATE rename_jobs SET status=?, dst_path=? WHERE id=?",
        (status, dst_path, job_id),
    )
    _conn.commit()


def delete_rename_jobs_by_hash(torrent_hash: str):
    _conn.execute("DELETE FROM rename_jobs WHERE torrent_hash=?", (torrent_hash,))
    _conn.commit()


# ---- update notifications ----

def has_notified_update(version: str) -> bool:
    return bool(_conn.execute(
        "SELECT 1 FROM config WHERE key=?", (f"notified_v{version}",)
    ).fetchone())


def mark_update_notified(version: str):
    _conn.execute("INSERT OR IGNORE INTO config VALUES (?, '1')", (f"notified_v{version}",))
    _conn.commit()
