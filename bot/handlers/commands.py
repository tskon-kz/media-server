import asyncio

from store import t
from config import APP_VERSION, current_channel
from api import gh_latest_release_tag
import keyboards as kb
from ._utils import guard


@guard
async def cmd_start(update, ctx):
    await update.message.reply_text(t("start"), parse_mode="Markdown", reply_markup=kb.start_kb())


@guard
async def cmd_update(update, ctx):
    remote = await asyncio.to_thread(gh_latest_release_tag)
    text, markup = kb.update_view(APP_VERSION, remote, current_channel(), show_back=False)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
