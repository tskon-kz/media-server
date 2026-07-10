"""Upscaler worker: poll the shared SQLite queue, run one job at a time.

Kept deliberately dumb — it only rewrites video files. The bot owns everything
else (removing the torrent from qBittorrent before queueing, rebuilding library
hardlinks and refreshing Jellyfin once a batch finishes).
"""
import logging
import os
import time

import db
import runners

POLL_INTERVAL = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("upscaler")


def _recover():
    """Once the table exists, re-queue jobs left 'running' by an interrupted
    encode and delete their leftover temp files, so a `docker restart` mid-batch
    resumes on its own instead of leaving a job stuck forever."""
    stuck = db.reset_stuck_running()
    if stuck:
        log.info("re-queued %d stuck running job(s) after restart", len(stuck))
    runners.cleanup_temp_files(os.path.dirname(p) for p in stuck)


def main():
    db.connect()
    log.info("upscaler worker started (Vulkan=%s)", runners.has_vulkan())
    recovered = False
    while True:
        if not db.table_ready():
            time.sleep(POLL_INTERVAL)
            continue
        if not recovered:
            _recover()
            recovered = True
        # Global pause: don't claim the next file. A file already running is left
        # to finish (its progress is never discarded).
        if db.is_paused():
            time.sleep(POLL_INTERVAL)
            continue
        job = db.claim_next_job()
        if job is None:
            time.sleep(POLL_INTERVAL)
            continue

        log.info("job %d: %s %s", job["id"], job["upscaler"], job["src_path"])
        try:
            runners.run(job, lambda p: db.set_progress(job["id"], p))
            db.mark_upscaled(job["disk_id"], job["src_path"])
            db.finish(job["id"])
            log.info("job %d done", job["id"])
        except Exception as e:
            log.exception("job %d failed", job["id"])
            db.finish(job["id"], error=str(e)[:500])


if __name__ == "__main__":
    main()
