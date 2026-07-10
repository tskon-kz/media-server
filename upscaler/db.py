"""Thin sqlite3 access to the shared bot database (stdlib only).

The bot owns the schema (``store._create_tables`` creates ``upscale_jobs``); this
worker only claims queued jobs and reports progress/result back over the same
WAL-mode file on the shared ``bot-data`` volume.
"""
import os
import sqlite3
import time

DB_PATH = os.environ.get("DB_PATH", "/app/data/media_server.db")

_conn: sqlite3.Connection | None = None


def connect():
    global _conn
    _conn = sqlite3.connect(DB_PATH, timeout=30)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA busy_timeout=30000")
    return _conn


def table_ready() -> bool:
    try:
        _conn.execute("SELECT 1 FROM upscale_jobs LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False


def claim_next_job() -> dict | None:
    """Atomically move the oldest queued job to 'running' and return it."""
    cur = _conn.execute(
        "UPDATE upscale_jobs SET status='running' "
        "WHERE id = (SELECT id FROM upscale_jobs WHERE status='queued' ORDER BY id LIMIT 1) "
        "RETURNING id, disk_id, src_path, upscaler, scale, compression, target"
    )
    row = cur.fetchone()
    _conn.commit()
    if not row:
        return None
    return {"id": row[0], "disk_id": row[1], "src_path": row[2],
            "upscaler": row[3], "scale": row[4], "compression": row[5],
            "target": row[6]}


def reset_stuck_running() -> list[str]:
    """Return jobs stuck in 'running' to the queue and report their src paths.

    The worker processes one file at a time and only ever moves a job to 'running'
    just before encoding it. So any 'running' row seen at startup is a job whose
    encode was killed (container stopped) — its temp output was discarded and the
    original file is untouched, so it's safe to re-queue and run again from scratch.
    Returns the src_paths so the caller can clean their leftover temp files."""
    rows = _conn.execute(
        "SELECT src_path FROM upscale_jobs WHERE status='running'"
    ).fetchall()
    _conn.execute(
        "UPDATE upscale_jobs SET status='queued', progress=0 WHERE status='running'"
    )
    _conn.commit()
    return [r[0] for r in rows]


def is_paused() -> bool:
    """Global pause flag set by the bot (config table). When true, the worker
    stops claiming new jobs; the currently-running file finishes normally."""
    try:
        row = _conn.execute(
            "SELECT value FROM config WHERE key='upscale_paused'"
        ).fetchone()
        return bool(row) and row[0] == "1"
    except sqlite3.OperationalError:
        return False


def set_progress(job_id: int, progress: float):
    _conn.execute("UPDATE upscale_jobs SET progress=? WHERE id=?",
                  (max(0.0, min(1.0, progress)), job_id))
    _conn.commit()


def finish(job_id: int, error: str | None = None):
    _conn.execute(
        "UPDATE upscale_jobs SET status=?, progress=?, error=? WHERE id=?",
        ("error" if error else "done", 0 if error else 1.0, error, job_id),
    )
    _conn.commit()
