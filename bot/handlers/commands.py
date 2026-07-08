from store import t
import keyboards as kb
from ._utils import guard


@guard
async def cmd_start(update, ctx):
    await update.message.reply_text(t("start"), parse_mode="Markdown", reply_markup=kb.start_kb())
