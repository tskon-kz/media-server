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
        "RETURNING id, disk_id, src_path, upscaler, scale, compression"
    )
    row = cur.fetchone()
    _conn.commit()
    if not row:
        return None
    return {"id": row[0], "disk_id": row[1], "src_path": row[2],
            "upscaler": row[3], "scale": row[4], "compression": row[5]}


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
