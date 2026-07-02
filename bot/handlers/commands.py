from store import t
from api import jf, qb
import keyboards as kb
from ._utils import guard, _show_list


@guard
async def cmd_start(update, ctx):
    await update.message.reply_text(t("start"), parse_mode="Markdown")


@guard
async def cmd_list(update, ctx):
    try:
        torrents = qb().torrents_info()
    except Exception as e:
        await update.message.reply_text(t("qb_error", e=e))
        return
    if not torrents:
        await update.message.reply_text(t("empty"))
        return
    await update.message.reply_text(
        kb.list_text(torrents, 0),
        parse_mode="HTML",
        reply_markup=kb.list_kb(0, len(torrents)),
    )


@guard
async def cmd_status(update, ctx):
    try:
        info = qb().transfer_info()
        msg  = t("status_ok", dl=f"{info.dl_info_speed/1024:.0f}", ul=f"{info.up_info_speed/1024:.0f}")
    except Exception:
        msg = t("status_err")
    await update.message.reply_text(msg, parse_mode="Markdown")


@guard
async def cmd_scan(update, ctx):
    ok = jf("POST", "/Library/Refresh")
    await update.message.reply_text(t("scan_ok") if ok else t("scan_error"))


@guard
async def cmd_settings(update, ctx):
    await update.message.reply_text(t("settings_main"), reply_markup=kb.main_menu_kb())
