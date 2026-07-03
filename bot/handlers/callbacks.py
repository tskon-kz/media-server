import asyncio
import os
from html import escape

from config import ALLOWED, APP_VERSION
from store import (
    t, set_lang, load_cats, save_cats,
    get_user_state, set_user_state, clear_user_state,
    set_pending, pop_pending, pop_pending_torrent, set_pending_torrent,
    get_rename_job, get_rename_jobs_by_hash, get_pending_rename_jobs,
    delete_rename_job, delete_rename_jobs_by_hash,
    set_config, get_config, set_qb_status,
)
from api import jf, jf_add_library, jf_remove_library, qb, qb_restart, qb_set_password, qb_temp_password, remote_version, invalidate_qb, jackett_download_torrent, jackett_set_password
from parser import (
    process_torrent_rename, create_flat_hardlinks, create_flat_hardlink_for_job,
    delete_torrent_links, delete_all_cat_contents,
)
import keyboards as kb
from ._utils import (
    _edit, _show_list, _show_torrent_actions, _run_pretty_parse,
    _do_trigger_update, _dl_path, log,
)
from .jobs import job_qb_restart_check


async def on_callback(update, ctx):
    query = update.callback_query
    uid   = update.effective_user.id
    if uid not in ALLOWED:
        await query.answer(t("no_access"))
        return
    await query.answer()

    action, _, value = query.data.partition(":")

    match action:
        case "noop":
            pass

        case "list":
            if value.startswith("manage:"):
                page = int(value[7:])
                try:
                    torrents = qb().torrents_info()
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                if not torrents:
                    await _edit(query, t("empty"))
                    return
                set_user_state(uid, "await_torrent_select")
                set_pending(uid, "pending_list_chat_id", query.message.chat_id)
                set_pending(uid, "pending_list_msg_id", query.message.message_id)
                prompt = kb.list_text(torrents, page) + f"\n\n{t('list_select_prompt', n=len(torrents))}"
                await _edit(query, prompt, parse_mode="HTML")
            elif value.startswith("page:"):
                await _show_list(query, int(value[5:]))
            elif value == "search":
                set_user_state(uid, "await_search_query")
                await _edit(query, t("search_ask_query"))
            else:
                await _show_list(query, 0)

        case "settings":
            match value:
                case "menu":
                    await _edit(query, t("settings_main"), kb.main_menu_kb())
                case "cats":
                    await _edit(query, *kb.cats_view(load_cats()))
                case "lang":
                    await _edit(query, t("lang_pick"), kb.lang_kb())
                case "qb":
                    txt, kb_val = kb.qb_view()
                    await _edit(query, txt, kb_val, parse_mode="HTML")
                case "jf_users":
                    await _edit(query, *kb.jf_users_view(jf("GET", "/Users") or []))
                case "update":
                    await _edit(query, *kb.update_view(APP_VERSION, remote_version()))
                case "media":
                    await _edit(query, t("media_mgmt_title"), kb.global_structure_menu_kb())
                case "jackett":
                    await _edit(query, *kb.jackett_view())

        case "toggle_rename_mode":
            current = get_config("rename_mode", "flat")
            new_mode = "pretty" if current == "flat" else "flat"
            set_config("rename_mode", new_mode)
            key = "rename_mode_set_pretty" if new_mode == "pretty" else "rename_mode_set_flat"
            await _edit(query, t(key), kb.main_menu_kb())

        case "qb":
            if value == "fetch_temp":
                temp = qb_temp_password()
                if temp:
                    set_config("qb_pass", temp)
                    set_config("qb_pass_is_perm", "")
                    set_qb_status("unknown")
                    invalidate_qb()
                    try:
                        await _edit(
                            query,
                            t("qb_temp_pass", pass_=escape(temp)),
                            kb.qb_settings_kb(is_perm=False),
                            parse_mode="HTML",
                        )
                    except Exception:
                        await query.answer(temp, show_alert=True)
                else:
                    await _edit(query, t("qb_no_temp_pass"), kb.qb_settings_kb(is_perm=True))
            elif value == "change_pass":
                set_user_state(uid, "await_qb_pass")
                await _edit(query, t("qb_change_pass_prompt"))
            elif value == "restart":
                if qb_restart():
                    set_qb_status("unknown")
                    invalidate_qb()
                    await _edit(query, t("qb_restart_started"), kb.qb_settings_kb())
                    ctx.job_queue.run_once(
                        job_qb_restart_check,
                        when=20,
                        data={"chat_id": query.message.chat_id},
                    )
                else:
                    await query.answer(t("qb_restart_error"), show_alert=True)

        case "lang":
            set_lang(value)
            await _edit(query, t("settings_main"), kb.main_menu_kb())

        case "update":
            if value == "start":
                set_config("update_pending", "1")
                await _edit(query, t("update_started"))
                asyncio.create_task(_do_trigger_update(query.message))

        case "tor_action":
            await _show_torrent_actions(query, value)

        case "del":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if not torrents:
                await _show_list(query, 0)
                return
            name = kb.short_name(torrents[0].name)
            await _edit(
                query,
                t("del_confirm", name=escape(name)),
                kb.del_torrent_confirm_kb(value),
                parse_mode="HTML",
            )

        case "del_confirm":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
                if torrents:
                    delete_torrent_links(torrents[0], load_cats())
                qb().torrents_delete(delete_files=True, torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("add_error", e=e))
                return
            await _show_list(query, 0)

        case "addmagnet":
            magnet = pop_pending(uid, "pending_magnet")
            if not magnet:
                await _edit(query, t("add_error", e="expired"))
                return
            cat_id = int(value)
            cat = next((c for c in load_cats() if c["id"] == cat_id), None)
            if not cat:
                await _edit(query, t("add_error", e="category not found"))
                return
            try:
                qb().torrents_add(urls=magnet, save_path=_dl_path(cat))
                await _edit(query, t("added"))
            except Exception as e:
                await _edit(query, t("add_error", e=e))

        case "addtorrent":
            torrent = pop_pending_torrent(uid)
            if not torrent:
                await _edit(query, t("add_error", e="expired"))
                return
            cat_id = int(value)
            cat = next((c for c in load_cats() if c["id"] == cat_id), None)
            if not cat:
                await _edit(query, t("add_error", e="category not found"))
                return
            try:
                qb().torrents_add(torrent_files=torrent, save_path=_dl_path(cat))
                await _edit(query, t("added"))
            except Exception as e:
                await _edit(query, t("add_error", e=e))

        case "move":
            if not load_cats():
                await query.answer(t("no_cats"))
            else:
                await query.edit_message_reply_markup(reply_markup=kb.move_cats_kb(value))

        case "moveto":
            tor_hash, _, cat_id_str = value.partition(":")
            cats = load_cats()
            new_cat = next((c for c in cats if c["id"] == int(cat_id_str)), None)
            if not new_cat:
                await _edit(query, t("add_error", e="category not found"))
                return
            try:
                torrents = qb().torrents_info(torrent_hashes=tor_hash)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if torrents:
                tor = torrents[0]
                delete_torrent_links(tor, cats)
                if get_config("rename_mode", "flat") == "pretty":
                    process_torrent_rename(tor, cats, target_cat=new_cat)
                else:
                    create_flat_hardlinks(tor, cats, target_cat=new_cat)
                jf("POST", "/Library/Refresh")
            try:
                qb().torrents_set_location(torrent_hashes=tor_hash, location=_dl_path(new_cat))
            except Exception as e:
                await _edit(query, t("add_error", e=e))
                return
            await _show_list(query, 0)

        case "editcat":
            set_pending(uid, "pending_cat_id", int(value))
            set_user_state(uid, "await_cat_rename")
            await _edit(query, t("cat_rename_prompt"))

        case "delcat":
            cats = load_cats()
            cat  = next((c for c in cats if c["id"] == int(value)), None)
            if not cat:
                await _edit(query, *kb.cats_view(cats))
                return
            await _edit(
                query,
                t("delcat_confirm", name=escape(cat["name"])),
                kb.delcat_confirm_kb(cat["id"]),
                parse_mode="HTML",
            )

        case "delcat_confirm":
            cats = load_cats()
            cat  = next((c for c in cats if c["id"] == int(value)), None)
            if cat:
                save_cats([c for c in cats if c["id"] != cat["id"]])
                jf_remove_library(cat["name"])
            await _edit(query, *kb.cats_view(load_cats()))

        case "cattype":
            name = pop_pending(uid, "pending_cat_name", "")
            path = pop_pending(uid, "pending_cat_path", "")
            clear_user_state(uid)
            if path:
                dl = _dl_path({"path": path})
                for d in (path, dl):
                    os.makedirs(d, exist_ok=True)
                    try:    os.chown(d, 1000, 1000)
                    except: os.chmod(d, 0o777)
            cats = load_cats()
            cats.append({"name": name, "path": path, "jf_type": value})
            save_cats(cats)
            jf_add_library(name, path, value)
            await _edit(query, *kb.cats_view(load_cats()))

        case "structure":
            await _edit(query, t("structure_menu_title"), kb.structure_menu_kb(value))

        case "struct_pretty":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if not torrents:
                await query.answer("Not found")
                return
            await _run_pretty_parse(query, ctx, torrents[0])

        case "struct_flat":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if not torrents:
                await query.answer(t("unlink_nothing"), show_alert=True)
                return
            cats = load_cats()
            delete_torrent_links(torrents[0], cats)
            errors = create_flat_hardlinks(torrents[0], cats)
            jf("POST", "/Library/Refresh")
            if errors and "cross-device" in errors[0].lower():
                await _edit(query, t("rename_xdev"))
            else:
                await _edit(query, t("unlink_done"))

        case "struct_del":
            try:
                torrents = qb().torrents_info(torrent_hashes=value)
            except Exception as e:
                await _edit(query, t("qb_error", e=e))
                return
            if torrents:
                delete_torrent_links(torrents[0], load_cats())
            await _edit(query, t("media_del_done"))

        case "media":
            cats = load_cats()
            if value == "pretty":
                try:
                    torrents = qb().torrents_info()
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                delete_all_cat_contents(cats)
                all_linked, all_pending, all_errors = 0, [], []
                for tor in torrents:
                    linked, pids, errs = process_torrent_rename(tor, cats)
                    all_linked += linked
                    all_pending.extend(pids)
                    all_errors.extend(errs)
                jf("POST", "/Library/Refresh")
                for _ in all_errors:
                    await ctx.bot.send_message(query.message.chat_id, t("rename_xdev"))
                await _edit(query, t("media_pretty_done", linked=all_linked, pending=len(all_pending)))
            elif value == "flat":
                try:
                    torrents = qb().torrents_info()
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                delete_all_cat_contents(cats)
                errors = []
                for tor in torrents:
                    errors.extend(create_flat_hardlinks(tor, cats))
                jf("POST", "/Library/Refresh")
                if errors and "cross-device" in errors[0].lower():
                    await _edit(query, t("rename_xdev"))
                else:
                    await _edit(query, t("media_flat_done"))
            elif value == "del":
                await _edit(query, t("del_links_confirm"), kb.del_links_confirm_kb())
            elif value == "del_confirm":
                delete_all_cat_contents(cats)
                await _edit(query, t("media_del_done"))

        case "rename":
            sub, _, job_id_str = value.partition(":")
            if sub == "skipall":
                pending = get_pending_rename_jobs()
                for j in pending:
                    delete_rename_job(j["id"])
                await _edit(query, t("rename_skipall_done", n=len(pending)))
                return
            if sub == "flatall":
                pending = get_pending_rename_jobs()
                n = 0
                for j in pending:
                    dst = create_flat_hardlink_for_job(j)
                    delete_rename_job(j["id"])
                    if dst:
                        n += 1
                jf("POST", "/Library/Refresh")
                await _edit(query, t("rename_flatall_done", n=n))
                return
            job = get_rename_job(int(job_id_str))
            if not job:
                await query.answer("Not found")
                return
            if sub == "skip":
                delete_rename_job(job["id"])
                await _edit(query, t("rename_skipped"))
            elif sub == "flat":
                dst = create_flat_hardlink_for_job(job)
                delete_rename_job(job["id"])
                if dst:
                    jf("POST", "/Library/Refresh")
                    await _edit(query, t("rename_done", dst=dst), parse_mode="Markdown")
                else:
                    await _edit(query, t("rename_xdev"))
            elif sub == "manual":
                jf_type = job["jf_type"]
                filename = os.path.basename(job["src_path"])
                key = "rename_manual_prompt_tv" if jf_type == "tvshows" else "rename_manual_prompt_movie"
                set_user_state(uid, "await_episode_manual")
                set_pending(uid, "pending_rename_id", job["id"])
                await _edit(query, t(key, filename=filename), parse_mode="Markdown")

        case "rename_tor":
            sub, _, tor_hash = value.partition(":")
            if sub == "keep_flat":
                try:
                    torrents = qb().torrents_info(torrent_hashes=tor_hash)
                except Exception as e:
                    await _edit(query, t("qb_error", e=e))
                    return
                cats = load_cats()
                if torrents:
                    delete_torrent_links(torrents[0], cats)
                    create_flat_hardlinks(torrents[0], cats)
                    jf("POST", "/Library/Refresh")
                delete_rename_jobs_by_hash(tor_hash)
                await _edit(query, t("rename_tor_kept_flat"))
            elif sub == "manual":
                pending = get_rename_jobs_by_hash(tor_hash)
                if not pending:
                    await _edit(query, t("rename_tor_kept_flat"))
                    return
                await _edit(query, t("rename_tor_sending_manual", n=len(pending)))
                for job in pending:
                    await ctx.bot.send_message(
                        query.message.chat_id,
                        t("rename_failed_parse", filename=os.path.basename(job["src_path"])),
                        parse_mode="Markdown",
                        reply_markup=kb.rename_manual_kb(job["id"], len(pending)),
                    )
            elif sub == "skip":
                pending = get_rename_jobs_by_hash(tor_hash)
                for job in pending:
                    delete_rename_job(job["id"])
                await _edit(query, t("rename_tor_skipped", n=len(pending)))

        case "jf_deluser":
            if jf("DELETE", f"/Users/{value}") is not None:
                await _edit(query, *kb.jf_users_view(jf("GET", "/Users") or []))
            else:
                await query.answer(t("jf_user_error"))

        case "jf_adduser":
            set_user_state(uid, "await_jf_user_name")
            await _edit(query, t("jf_add_user_name"))

        case "addcat":
            set_user_state(uid, "await_cat_name")
            await _edit(query, t("cat_add_name"))

        case "jackett":
            if value == "set_key":
                set_user_state(uid, "await_jackett_key")
                await _edit(query, t("jackett_ask_key"))
            elif value == "change_pass":
                set_user_state(uid, "await_jackett_pass")
                await _edit(query, t("jackett_ask_pass"))
            elif value == "remove_pass":
                result = jackett_set_password("")
                if result is True:
                    await _edit(query, *kb.jackett_view())
                else:
                    await query.answer(f"{t('jackett_pass_error')}: {result}", show_alert=True)

        case "search":
            results = pop_pending(uid, "search_results")
            if not results:
                await _edit(query, t("add_error", e="expired"))
                return
            idx = int(value)
            result = results[idx]
            cats = load_cats()
            magnet = result.get("magnet")
            if magnet:
                if not cats:
                    try:
                        qb().torrents_add(urls=magnet, save_path="/media/downloads")
                        await _edit(query, t("added"))
                    except Exception as e:
                        await _edit(query, t("add_error", e=e))
                    return
                set_pending(uid, "pending_magnet", magnet)
                await _edit(query, t("pick_cat"), kb.cats_pick_kb(cats, "addmagnet"))
            else:
                link = result.get("link")
                if not link:
                    await _edit(query, t("add_error", e="no torrent link"))
                    return
                torrent_bytes = await asyncio.to_thread(jackett_download_torrent, link)
                if torrent_bytes is None:
                    await _edit(query, t("jackett_error"))
                    return
                if not cats:
                    try:
                        qb().torrents_add(torrent_files=torrent_bytes, save_path="/media/downloads")
                        await _edit(query, t("added"))
                    except Exception as e:
                        await _edit(query, t("add_error", e=e))
                    return
                set_pending_torrent(uid, torrent_bytes)
                await _edit(query, t("pick_cat"), kb.cats_pick_kb(cats, "addtorrent"))
