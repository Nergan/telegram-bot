import html
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from bot.bot_setup import bot
from bot.states import ContactRequest
from bot.keyboards import (
    main_menu_kb, browse_kb, browse_inline_kb, skip_message_kb, 
    contact_share_selection_kb, contact_decision_kb
)
from bot.helpers import send_profile
from infrastructure.locales import _, _btn
from application.services import UserService, ProfileService, BrowseService, ContactRequestService, TagService

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.startswith("🔍") | F.text.in_(_btn("btn_next")))
async def browse_next(
    message: types.Message, state: FSMContext, lang: str,
    profile_service: ProfileService, browse_service: BrowseService, contact_req_service: ContactRequestService, tag_service: TagService
):
    try:
        user_id = message.from_user.id
        active = await profile_service.get_active_profile(user_id)
        if not active:
            return await message.answer(_("browse_req_create", lang))
            
        await profile_service.sync_telegram_username(active, message.from_user.username)
        active = await profile_service.get_active_profile(user_id)
        
        target, all_seen = await browse_service.get_next_profile(user_id, active)
        
        if not target:
            pool_size = await profile_service.get_pool_size(user_id, active.get("filters", {}))
            return await message.answer(_("browse_none", lang), reply_markup=main_menu_kb(lang, pool_size))
            
        if all_seen:
            await message.answer(_("browse_all_seen", lang))
            
        await message.answer(_("browsing", lang), reply_markup=browse_kb(lang))
        
        target_uuid = target.get('public_uuid', '')
        target_id = target.get('user_id', 0)
        
        pending_actions = await contact_req_service.get_pending_actions(user_id, target_id)
        
        private_contacts = [c for c in active.get("contacts", []) if not c.get("is_public")]
        target_private_contacts = [c for c in target.get("contacts", []) if not c.get("is_public")]
        
        await send_profile(
            message.chat.id, 
            target, 
            browse_inline_kb(
                lang, target_uuid, 
                has_self_private=len(private_contacts) > 0, 
                has_target_private=len(target_private_contacts) > 0,
                pending_actions=pending_actions
            ),
            lang, tag_service
        )
    except Exception as e:
        logger.exception("Error during browse_next execution")
        await message.answer(_("err_render", lang, html.escape(str(e))), parse_mode="HTML")

@router.callback_query(F.data == "pending_alert")
async def pending_alert_cb(callback: types.CallbackQuery, lang: str):
    await callback.answer(_("alert_pending", lang), show_alert=True)

@router.callback_query(F.data == "no_private_alert")
async def no_private_alert_cb(callback: types.CallbackQuery, lang: str):
    await callback.answer(_("alert_no_priv", lang), show_alert=True)

@router.callback_query(F.data == "target_no_private_alert")
async def target_no_private_alert_cb(callback: types.CallbackQuery, lang: str):
    await callback.answer(_("alert_tgt_no_priv", lang), show_alert=True)

@router.callback_query(F.data.startswith("req_") | F.data.startswith("reqmsg_") | F.data.startswith("send_") | F.data.startswith("sendmsg_"))
async def init_contact_inline(
    callback: types.CallbackQuery, state: FSMContext, lang: str,
    profile_service: ProfileService, contact_req_service: ContactRequestService
):
    parts = callback.data.split("_")
    action_type = parts[0]
    target_uuid = parts[1]
    
    target_prof = await profile_service.get_profile_by_uuid(target_uuid)
    if not target_prof:
        return await callback.answer(_("prof_not_found", lang), show_alert=True)
        
    is_send = action_type.startswith("send")
    has_msg = action_type.endswith("msg")
    db_action = "send" if is_send else "req"
    
    if await contact_req_service.has_pending_request(callback.from_user.id, target_prof['user_id'], db_action):
        req_type_str = _("str_oneway", lang) if db_action == "send" else _("str_mutual", lang)
        return await callback.answer(_("alert_already_req", lang, req_type_str), show_alert=True)
    
    await state.update_data(target_uuid=target_uuid, action=db_action, selected_contact_ids=[])
    
    if has_msg:
        await state.set_state(ContactRequest.waiting_for_message)
        prompt_msg = await callback.message.answer(_("attach_msg", lang), reply_markup=skip_message_kb(lang))
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        await callback.answer()
    else:
        await show_contact_selection(callback, state, lang, profile_service)

async def show_contact_selection(event: types.CallbackQuery | types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    user_id = event.from_user.id
    active_prof = await profile_service.get_active_profile(user_id)
    if not active_prof:
        await state.clear()
        msg_err = _("menu_no_active", lang)
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg_err)
            await event.answer()
        else:
            await event.answer(msg_err)
        return

    await profile_service.sync_telegram_username(active_prof, event.from_user.username)
    active_prof = await profile_service.get_active_profile(user_id)
    
    data = await state.get_data()
    action = data.get("action")
    
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    
    if not private_contacts and action == "req":
        await state.clear()
        msg_err = _("err_no_priv", lang)
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg_err)
            await event.answer()
        else:
            await event.answer(msg_err)
        return
        
    selected_ids = data.get("selected_contact_ids", [])
    if not selected_ids and private_contacts:
        selected_ids = [private_contacts[0]["id"]]
        await state.update_data(selected_contact_ids=selected_ids)
        
    kb = contact_share_selection_kb(lang, private_contacts, selected_ids, action)
    text = _("req_select_mut", lang) if action == "req" else _("req_select_send", lang)
        
    await state.set_state(ContactRequest.selecting_contacts)
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("selcon_"), ContactRequest.selecting_contacts)
async def toggle_share_selection(callback: types.CallbackQuery, state: FSMContext, lang: str, profile_service: ProfileService):
    cid = callback.data.replace("selcon_", "", 1)
    data = await state.get_data()
    action = data.get("action")
    selected_ids = data.get("selected_contact_ids", [])
    
    active_prof = await profile_service.get_active_profile(callback.from_user.id)
    if not active_prof:
        await state.clear()
        return await callback.answer(_("menu_no_active", lang), show_alert=True)
        
    if cid in selected_ids:
        if action in ("req", "accept") and len(selected_ids) <= 1:
            return await callback.answer(_("err_mut_min", lang), show_alert=True)
        selected_ids.remove(cid)
    else:
        selected_ids.append(cid)
        
    await state.update_data(selected_contact_ids=selected_ids)
    
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    await callback.message.edit_reply_markup(
        reply_markup=contact_share_selection_kb(lang, private_contacts, selected_ids, action)
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_share_contacts", ContactRequest.selecting_contacts)
async def confirm_share_contacts_cb(
    callback: types.CallbackQuery, state: FSMContext, lang: str, 
    profile_service: ProfileService, contact_req_service: ContactRequestService, user_service: UserService, tag_service: TagService
):
    data = await state.get_data()
    action = data.get("action")
    accepting_req_id = data.get("accepting_req_id")
    
    selected_ids = data.get("selected_contact_ids", [])
    active_prof = await profile_service.get_active_profile(callback.from_user.id)
    if not active_prof:
        await state.clear()
        return await callback.answer(_("menu_no_active", lang), show_alert=True)
        
    shared_contacts = [c["value"] for c in active_prof.get("contacts", []) if c["id"] in selected_ids]
    
    if action == "req" and not shared_contacts:
        return await callback.answer(_("err_mut_min", lang), show_alert=True)
        
    if accepting_req_id:
        if not shared_contacts:
            return await callback.answer(_("err_mut_req", lang), show_alert=True)
            
        req = await contact_req_service.get_request(accepting_req_id)
        if not req or req['status'] != 'pending':
            await state.clear()
            return await callback.answer(_("req_expired", lang), show_alert=True)
            
        initiator_prof = await profile_service.get_active_profile(req['initiator_id'])
        if not initiator_prof:
            await state.clear()
            return await callback.answer(_("prof_not_found", lang), show_alert=True)
            
        await contact_req_service.update_status(accepting_req_id, "accepted", {"target_shared_contacts": shared_contacts})
        
        init_lang = await user_service.get_lang(req['initiator_id'])
        try:
            await send_profile(req['initiator_id'], active_prof, kb=None, lang=init_lang, tag_service=tag_service, custom_prefix=_("lbl_exchanged", init_lang))
            contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_contacts)
            await bot.send_message(req['initiator_id'], _("mut_accepted", init_lang, contacts_text))
        except Exception as e:
            logger.warning(f"Could not notify request initiator {req['initiator_id']}: {e}")
            
        initiator_shared = req.get("shared_contacts", [])
        if initiator_shared:
            try:
                await send_profile(callback.from_user.id, initiator_prof, kb=None, lang=lang, tag_service=tag_service, custom_prefix=_("lbl_exchanged", lang))
                init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
                await callback.message.answer(_("mut_complete", lang, init_contacts_text))
            except Exception as e:
                logger.warning(f"Could not deliver completed mutual exchange to acceptor {callback.from_user.id}: {e}")
            
        try:
            await callback.message.delete()
        except Exception:
            pass
        await state.clear()
        
    else:
        target_uuid = data.get("target_uuid")
        await state.update_data(shared_contacts=shared_contacts)
        
        target_prof = await profile_service.get_profile_by_uuid(target_uuid)
        if not target_prof:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(_("prof_not_found", lang), reply_markup=browse_kb(lang))
            await state.clear()
            return
            
        if await contact_req_service.has_pending_request(callback.from_user.id, target_prof['user_id'], action):
            try:
                await callback.message.delete()
            except Exception:
                pass
            req_type_str = _("str_oneway", lang) if action == "send" else _("str_mutual", lang)
            await callback.message.answer(_("alert_already_req", lang, req_type_str), reply_markup=browse_kb(lang))
            await state.clear()
            return
            
        msg_text = data.get("message_text")
        req_id = await contact_req_service.create_request(callback.from_user.id, target_prof['user_id'], action, msg_text, shared_contacts)
        
        target_lang = await user_service.get_lang(target_prof['user_id'])
        success = False
        try:
            if action == "send":
                prefix = _("notif_send", target_lang)
                if msg_text: prefix += _("notif_msg", target_lang, html.escape(msg_text))
                if shared_contacts: prefix += _("notif_send_priv", target_lang)
                prefix += _("notif_send_footer", target_lang)
                await send_profile(target_prof['user_id'], active_prof, None, target_lang, tag_service, custom_prefix=prefix)
            else:
                prefix = _("notif_mut", target_lang)
                if msg_text: prefix += _("notif_msg", target_lang, html.escape(msg_text))
                prefix += _("notif_mut_footer", target_lang)
                await send_profile(target_prof['user_id'], active_prof, contact_decision_kb(target_lang, req_id), target_lang, tag_service, custom_prefix=prefix)
            success = True
        except Exception as e:
            logger.warning(f"Failed to transmit request notification to recipient user {target_prof['user_id']}: {e}")
            success = True
        
        try:
            await callback.message.delete()
        except Exception:
            pass
        if success:
            msg = _("req_sent_send", lang, target_uuid) if action == "send" else _("req_sent_mut", lang, target_uuid)
            await callback.message.answer(msg, reply_markup=browse_kb(lang))
        else:
            await callback.message.answer(_("err_render", lang, "Failed to deliver request notification."), reply_markup=browse_kb(lang))
        await state.clear()

@router.callback_query(F.data == "cancel_share_contacts", ContactRequest.selecting_contacts)
async def cancel_share_contacts_cb(callback: types.CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(_("cancel_share", lang), reply_markup=browse_kb(lang))
    await callback.answer()

@router.callback_query(F.data == "skip_req_msg", ContactRequest.waiting_for_message)
async def skip_contact_msg(callback: types.CallbackQuery, state: FSMContext, lang: str, profile_service: ProfileService):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_contact_selection(callback, state, lang, profile_service)

@router.message(ContactRequest.waiting_for_message, ~F.text.startswith("/"))
async def capture_contact_msg(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    if message.content_type != 'text': return await message.answer(_("invalid_text", lang))
    await state.update_data(message_text=message.text)
    
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_message_id")
    if prompt_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        except Exception:
            pass
            
    await show_contact_selection(message, state, lang, profile_service)

@router.callback_query(F.data.startswith("accept_") | F.data.startswith("decline_"))
async def contact_decisions(
    callback: types.CallbackQuery, state: FSMContext, lang: str,
    contact_req_service: ContactRequestService, profile_service: ProfileService
):
    parts = callback.data.split("_")
    decision = parts[0]
    req_id = parts[1]
    
    req = await contact_req_service.get_request(req_id)
    if not req or req['status'] != 'pending':
        return await callback.answer(_("req_expired", lang), show_alert=True)
        
    if decision == "decline":
        await contact_req_service.update_status(req_id, "declined")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(_("mut_declined", lang))
        logger.info(f"Request {req_id} declined.")
        return await callback.answer()
        
    elif decision == "accept":
        active_prof = await profile_service.get_active_profile(callback.from_user.id)
        if not active_prof:
            return await callback.answer(_("menu_no_active", lang), show_alert=True)
            
        private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
        if not private_contacts:
            return await callback.answer(_("con_add_instr", lang), show_alert=True)
            
        await callback.message.edit_reply_markup(reply_markup=None)
            
        await state.update_data(
            accepting_req_id=req_id, action="accept",
            selected_contact_ids=[private_contacts[0]["id"]]
        )
        await state.set_state(ContactRequest.selecting_contacts)
        
        kb = contact_share_selection_kb(lang, private_contacts, [private_contacts[0]["id"]], action="accept")
        await callback.message.answer(_("mut_select_accept", lang), reply_markup=kb)
        await callback.answer()