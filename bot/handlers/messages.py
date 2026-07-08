import errno
import os

from store import (
    t, load_cats,
    get_user_state, set_user_state, clear_user_state,
    set_pending, pop_pending,
    get_rename_job, delete_rename_job,
)
from api import jf
from parser import build_target_path, create_hardlink, parse_manual_input
from ._utils import guard


@guard
async def on_message(update, ctx):
    uid   = update.effective_user.id
    text  = update.message.text or ""
    state = get_user_state(uid)

    if state == "await_episode_manual":
        job_id = pop_pending(uid, "pending_rename_id")
        if job_id is None:
            clear_user_state(uid)
            await update.message.reply_text(t("hint"))
            return
        job = get_rename_job(int(job_id))
        if not job:
            clear_user_state(uid)
            await update.message.reply_text(t("hint"))
            return
        cats = load_cats()
        cat = next((c for c in cats if c["path"] == job["cat_path"]), None)
        jf_type = cat["jf_type"] if cat else job["jf_type"]
        filename = os.path.basename(job["src_path"])
        parsed = parse_manual_input(jf_type, text, filename)
        if parsed is None:
            set_user_state(uid, "await_episode_manual")
            set_pending(uid, "pending_rename_id", job_id)
            await update.message.reply_text(t("rename_invalid_input"))
            return
        clear_user_state(uid)
        dst_path = build_target_path({"path": job["cat_path"], "jf_type": jf_type}, parsed, filename)
        try:
            create_hardlink(job["src_path"], dst_path)
            delete_rename_job(job["id"])
            jf("POST", "/Library/Refresh")
            await update.message.reply_text(t("rename_done", dst=dst_path), parse_mode="Markdown")
        except OSError as e:
            if e.errno == errno.EXDEV:
                await update.message.reply_text(t("rename_xdev"))
            else:
                await update.message.reply_text(t("rename_error", e=e))
        return
