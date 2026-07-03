import uuid
import html
import logging
import traceback
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from bot.bot_setup import bot
from bot.states import ContactRequest
from bot.keyboards import (
    main_menu_kb,
    browse_kb,
    browse_inline_kb,
    skip_message_kb,
    contact_share_selection_kb,
    contact_decision_kb
)
from bot.helpers import send_profile
from core.database import Database
from core.locales import _, _btn

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.startswith("🔍") | F.text.in_(_btn("btn_next")))
async def browse_next(message: types.Message, state: FSMContext, lang: str):
    try:
        user_id = message.from_user.id
        active = await Database.get_active_profile(user_id)
        if not active:
            return await message.answer(_("browse_req_create", lang))
            
        await Database.sync_telegram_username(active, message.from_user.username)
        active = await Database.get_active_profile(user_id)
        
        seen_uuids = await Database.get_seen_profiles(user_id)
        
        filters = active.get("filters", {})
        and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}]
        if filters.get("require_tags"): 
            and_clauses.append({"tags": {"$all": filters["require_tags"]}})
        if filters.get("exclude_tags"): 
            and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
        if filters.get("any_tags"): 
            and_clauses.append({"tags": {"$in": filters["any_tags"]}})
            
        pipeline = [{"$match": {"$and": and_clauses + [{"public_uuid": {"$nin": seen_uuids}}]}}, {"$sample": {"size": 1}}]
        cursor = Database.db.profiles.aggregate(pipeline)
        profiles = await cursor.to_list(length=1)
        
        if not profiles:
            pipeline_all = [{"$match": {"$and": and_clauses}}, {"$sample": {"size": 1}}]
            cursor_all = Database.db.profiles.aggregate(pipeline_all)
            all_profiles = await cursor_all.to_list(length=1)
            
            if not all_profiles:
                pool_size = await Database.get_pool_size(user_id)
                return await message.answer(_("browse_none", lang), reply_markup=main_menu_kb(lang, pool_size))
            else:
                await Database.clear_seen_profiles(user_id)
                await message.answer(_("browse_all_seen", lang))
                profiles = all_profiles

        target = profiles[0]
        target_uuid = target.get('public_uuid', '')
        await Database.add_seen_profile(user_id, target_uuid)
        
        await message.answer(_("browsing", lang), reply_markup=browse_kb(lang))
        
        target_id = target.get('user_id', 0)
        
        # Check for pending requests specifically for these inline buttons
        pending_cursor = Database.db.contact_requests.find({
            "initiator_id": user_id,
            "target_id": target_id,
            "status": "pending"
        })
        pending_docs = await pending_cursor.to_list(length=10)
        pending_actions = [doc.get("action") for doc in pending_docs if doc.get("action")]
        
        private_contacts = [c for c in active.get("contacts", []) if not c.get("is_public")]
        has_self_private = len(private_contacts) > 0
        
        target_private_contacts = [c for c in target.get("contacts", []) if not c.get("is_public")]
        has_target_private = len(target_private_contacts) > 0
        
        await send_profile(
            message.chat.id, 
            target, 
            browse_inline_kb(
                lang,
                target_uuid, 
                has_self_private=has_self_private, 
                has_target_private=has_target_private,
                pending_actions=pending_actions
            ),
            lang
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
async def init_contact_inline(callback: types.CallbackQuery, state: FSMContext, lang: str):
    parts = callback.data.split("_")
    action_type = parts[0]
    target_uuid = parts[1]
    
    target_prof = await Database.get_profile_by_uuid(target_uuid)
    if not target_prof:
        return await callback.answer(_("prof_not_found", lang), show_alert=True)
        
    is_send = action_type.startswith("send")
    has_msg = action_type.endswith("msg")
    db_action = "send" if is_send else "req"
    
    existing_req = await Database.db.contact_requests.find_one({
        "initiator_id": callback.from_user.id,
        "target_id": target_prof['user_id'],
        "status": "pending",
        "action": db_action
    })
    if existing_req:
        req_type_str = _("str_oneway", lang) if db_action == "send" else _("str_mutual", lang)
        return await callback.answer(_("alert_already_req", lang, req_type_str), show_alert=True)
    
    await state.update_data(
        target_uuid=target_uuid, 
        action=db_action,
        selected_contact_ids=[] 
    )
    
    if has_msg:
        await state.set_state(ContactRequest.waiting_for_message)
        await callback.message.answer(_("attach_msg_prompt", lang), reply_markup=skip_message_kb(lang))
        await callback.answer()
    else:
        await show_contact_selection(callback, state, lang)

async def show_contact_selection(event: types.CallbackQuery | types.Message, state: FSMContext, lang: str):
    user_id = event.from_user.id
    active_prof = await Database.get_active_profile(user_id)
    await Database.sync_telegram_username(active_prof, event.from_user.username)
    active_prof = await Database.get_active_profile(user_id)
    
    data = await state.get_data()
    action = data.get("action")
    
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    
    if not private_contacts and action == "req":
        await state.clear()
        msg_err = _("err_no_priv_to_share", lang)
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg_err)
        else:
            await event.answer(msg_err)
        return
        
    selected_ids = data.get("selected_contact_ids", [])
    if not selected_ids and private_contacts:
        selected_ids = [private_contacts[0]["id"]]
        await state.update_data(selected_contact_ids=selected_ids)
        
    kb = contact_share_selection_kb(lang, private_contacts, selected_ids, action)
    
    if action == "req":
        text = _("select_mutual_contacts_prompt", lang)
    else:
        text = _("select_send_contacts_prompt", lang)
        
    await state.set_state(ContactRequest.selecting_contacts)
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("selcon_"), ContactRequest.selecting_contacts)
async def toggle_share_selection(callback: types.CallbackQuery, state: FSMContext, lang: str):
    cid = callback.data.replace("selcon_", "", 1)
    
    data = await state.get_data()
    action = data.get("action")
    selected_ids = data.get("selected_contact_ids", [])
    
    if cid in selected_ids:
        if action == "req" and len(selected_ids) <= 1:
            return await callback.answer(_("err_mut_min", lang), show_alert=True)
        selected_ids.remove(cid)
    else:
        selected_ids.append(cid)
        
    await state.update_data(selected_contact_ids=selected_ids)
    
    active_prof = await Database.get_active_profile(callback.from_user.id)
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    await callback.message.edit_reply_markup(
        reply_markup=contact_share_selection_kb(lang, private_contacts, selected_ids, action)
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_share_contacts", ContactRequest.selecting_contacts)
async def confirm_share_contacts_cb(callback: types.CallbackQuery, state: FSMContext, lang: str):
    data = await state.get_data()
    action = data.get("action")
    accepting_req_id = data.get("accepting_req_id")
    
    selected_ids = data.get("selected_contact_ids", [])
    active_prof = await Database.get_active_profile(callback.from_user.id)
    shared_contacts = [c["value"] for c in active_prof.get("contacts", []) if c["id"] in selected_ids]
    
    if action == "req" and not shared_contacts:
        return await callback.answer(_("err_mut_min", lang), show_alert=True)
        
    if accepting_req_id:
        if not shared_contacts:
            return await callback.answer(_("err_mut_req", lang), show_alert=True)
            
        req = await Database.db.contact_requests.find_one({"req_id": accepting_req_id})
        if not req or req['status'] != 'pending':
            await state.clear()
            return await callback.answer(_("req_expired", lang), show_alert=True)
            
        await Database.db.contact_requests.update_one(
            {"req_id": accepting_req_id}, 
            {"$set": {
                "status": "accepted",
                "target_shared_contacts": shared_contacts
            }}
        )
        
        # Localize initiator profile message
        init_lang = await Database.get_user_lang(req['initiator_id'])
        b_profile = await Database.get_active_profile(callback.from_user.id)
        await send_profile(req['initiator_id'], b_profile, kb=None, lang=init_lang, custom_prefix=_("lbl_exchanged", init_lang))
        
        contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_contacts)
        await bot.send_message(
            req['initiator_id'], 
            _("mut_accepted", init_lang, contacts_text)
        )
        
        initiator_shared = req.get("shared_contacts", [])
        if initiator_shared:
            a_profile = await Database.get_active_profile(req['initiator_id'])
            await send_profile(callback.from_user.id, a_profile, kb=None, lang=lang, custom_prefix=_("lbl_exchanged", lang))
            init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
            await callback.message.answer(
                _("mut_complete", lang, init_contacts_text)
            )
            
        await callback.message.delete()
        await state.clear()
        
    else:
        target_uuid = data.get("target_uuid")
        await state.update_data(shared_contacts=shared_contacts)
        success = await execute_contact_request(callback.from_user.id, state, message=None, lang=lang)
        
        await callback.message.delete()
        if success:
            msg = _("req_sent_send", lang, target_uuid) if action == "send" else _("req_sent_mut", lang, target_uuid)
            await callback.message.answer(msg, reply_markup=browse_kb(lang))
        else:
            req_type_str = _("str_oneway", lang) if action == "send" else _("str_mutual", lang)
            await callback.message.answer(_("alert_already_req", lang, req_type_str), reply_markup=browse_kb(lang))

@router.callback_query(F.data == "cancel_share_contacts", ContactRequest.selecting_contacts)
async def cancel_share_contacts_cb(callback: types.CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(_("cancel_share", lang), reply_markup=browse_kb(lang))
    await callback.answer()

@router.callback_query(F.data == "skip_req_msg", ContactRequest.waiting_for_message)
async def skip_contact_msg(callback: types.CallbackQuery, state: FSMContext, lang: str):
    await show_contact_selection(callback, state, lang)

@router.message(ContactRequest.waiting_for_message)
async def capture_contact_msg(message: types.Message, state: FSMContext, lang: str):
    if message.content_type != 'text': return await message.answer(_("invalid_text", lang))
    await state.update_data(message_text=message.text)
    await show_contact_selection(message, state, lang)

async def execute_contact_request(user_id: int, state: FSMContext, message=None, lang: str = "en") -> bool:
    data = await state.get_data()
    target_prof = await Database.get_profile_by_uuid(data['target_uuid'])
    if not target_prof: return False
    
    action = data['action']
    target_lang = await Database.get_user_lang(target_prof['user_id'])
    
    existing_req = await Database.db.contact_requests.find_one({
        "initiator_id": user_id,
        "target_id": target_prof['user_id'],
        "status": "pending",
        "action": action
    })
    if existing_req:
        await state.clear()
        return False

    msg_text = message.text if message else data.get("message_text")
    shared_contacts = data.get("shared_contacts", [])
    initiator = await Database.get_active_profile(user_id)
    
    req_id = uuid.uuid4().hex
    req_doc = {
        "req_id": req_id, 
        "initiator_id": user_id, 
        "target_id": target_prof['user_id'], 
        "action": action, 
        "status": "pending", 
        "message": msg_text,
        "shared_contacts": shared_contacts
    }
    await Database.db.contact_requests.insert_one(req_doc)
    
    if action == "send":
        logger.info(f"One-way share {req_id} initiated by {user_id} to {target_prof['user_id']}")
        prefix = _("notif_send", target_lang)
        if msg_text: prefix += _("notif_msg", target_lang, html.escape(msg_text))
        if shared_contacts:
            prefix += _("notif_send_priv", target_lang)
            
        prefix += _("notif_send_footer", target_lang)
        await send_profile(target_prof['user_id'], initiator, None, target_lang, custom_prefix=prefix)
    
    else:
        logger.info(f"Mutual Contact Request {req_id} initiated by {user_id} to {target_prof['user_id']}")
        prefix = _("notif_mut", target_lang)
        if msg_text: prefix += _("notif_msg", target_lang, html.escape(msg_text))
        prefix += _("notif_mut_footer", target_lang)
        
        await send_profile(target_prof['user_id'], initiator, contact_decision_kb(target_lang, req_id), target_lang, custom_prefix=prefix)
        
    await state.clear()
    return True

@router.callback_query(F.data.startswith("accept_") | F.data.startswith("decline_"))
async def contact_decisions(callback: types.CallbackQuery, state: FSMContext, lang: str):
    parts = callback.data.split("_")
    decision = parts[0]
    req_id = parts[1]
    
    req = await Database.db.contact_requests.find_one({"req_id": req_id})
    if not req or req['status'] != 'pending':
        return await callback.answer(_("req_expired", lang), show_alert=True)
        
    if decision == "decline":
        await Database.db.contact_requests.update_one({"req_id": req_id}, {"$set": {"status": "declined"}})
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(_("mut_declined", lang))
        logger.info(f"Request {req_id} declined.")
        return await callback.answer()
        
    elif decision == "accept":
        active_prof = await Database.get_active_profile(callback.from_user.id)
        private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
        if not private_contacts:
            return await callback.answer(_("con_add_instr", lang), show_alert=True)
            
        await state.update_data(
            accepting_req_id=req_id,
            action="accept",
            selected_contact_ids=[private_contacts[0]["id"]]
        )
        await state.set_state(ContactRequest.selecting_contacts)
        
        kb = contact_share_selection_kb(lang, private_contacts, [private_contacts[0]["id"]], action="accept")
        await callback.message.answer(
            _("mut_select_accept", lang),
            reply_markup=kb
        )
        await callback.answer()