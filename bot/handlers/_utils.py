import asyncio
import logging
from functools import wraps

from telegram import Update, LinkPreviewOptions
from telegram.ext import ContextTypes

from config import ALLOWED
import store
from store import t
from api import self_update

log = logging.getLogger(__name__)


async def _notify_admins(bot, message: str):
    for uid in ALLOWED:
        try:
            await bot.send_message(uid, message)
        except Exception:
            pass


def guard(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ALLOWED:
            await update.message.reply_text(t("no_access"))
            return
        await func(update, ctx)
    return wrapper


async def _edit(query, text, keyboard=None, parse_mode="Markdown", disable_preview=False):
    kwargs = {}
    if disable_preview:
        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
    await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=keyboard, **kwargs)


async def _do_self_update(message, tag: str):
    """Blue/green swap ONLY the bot container to `tag` (stable | edge) and report.

    `api.self_update` starts the replacement, health-checks it, and — on success
    — retires this container, which kills this process mid-flight. The fresh
    bot's `_post_init` then reports success via the persisted `update_pending`
    flag, so on success this coroutine simply never returns.

    On failure `self_update` returns an error string and nothing destructive
    happened (the old bot keeps running); we clear the flag and report why.
    Infrastructure/topology changes are out of scope here — they go through
    update.sh on the host.
    """
    result = await asyncio.to_thread(self_update, tag)
    # Reaching here means the swap did not replace us → it failed.
    store.set_config("update_pending", "")
    try:
        await message.reply_text(t("update_failed_self", err=str(result)[:300]))
    except Exception:
        pass
