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

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.startswith("🔍 Browse") | (F.text == "⏩ Next Profile"))
async def browse_next(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        active = await Database.get_active_profile(user_id)
        if not active:
            return await message.answer("❌ You must create and activate a profile before browsing others!")
            
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
                return await message.answer("No matching profiles found!", reply_markup=main_menu_kb(pool_size))
            else:
                await Database.clear_seen_profiles(user_id)
                await message.answer("🔄 You have viewed all matching profiles. Showing them a second time.")
                profiles = all_profiles

        target = profiles[0]
        target_uuid = target.get('public_uuid', '')
        await Database.add_seen_profile(user_id, target_uuid)
        
        # Send the browsing text
        await message.answer("🔍 Browsing...", reply_markup=browse_kb())
        
        # Defensive fallback for target ID checks
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
                target_uuid, 
                has_self_private=has_self_private, 
                has_target_private=has_target_private,
                pending_actions=pending_actions
            )
        )
    except Exception as e:
        logger.exception("Error during browse_next execution")
        # Diagnostic report back to the user to prevent silent hanging
        tb = traceback.format_exc()
        await message.answer(
            f"⚠️ <b>An internal rendering error occurred:</b>\n"
            f"<code>{html.escape(str(e))}</code>\n\n"
            f"Please check your server logs for more details.", 
            parse_mode="HTML"
        )

@router.callback_query(F.data == "pending_alert")
async def pending_alert_cb(callback: types.CallbackQuery):
    await callback.answer(
        "⏳ You already have a pending request of this type with this user.",
        show_alert=True
    )

@router.callback_query(F.data == "no_private_alert")
async def no_private_alert_cb(callback: types.CallbackQuery):
    await callback.answer(
        "⚠️ You must add at least one private contact via 'Manage Contacts' before you can initiate a mutual exchange request.",
        show_alert=True
    )

@router.callback_query(F.data == "target_no_private_alert")
async def target_no_private_alert_cb(callback: types.CallbackQuery):
    await callback.answer(
        "⚠️ You cannot send an exchange request to this user because they have no private contacts to share in return.",
        show_alert=True
    )

@router.callback_query(F.data.startswith("req_") | F.data.startswith("reqmsg_") | F.data.startswith("send_") | F.data.startswith("sendmsg_"))
async def init_contact_inline(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    action_type = parts[0]
    target_uuid = parts[1]
    
    target_prof = await Database.get_profile_by_uuid(target_uuid)
    if not target_prof:
        return await callback.answer("Profile no longer exists.", show_alert=True)
        
    is_send = action_type.startswith("send")
    has_msg = action_type.endswith("msg")
    db_action = "send" if is_send else "req"
    
    # 1. Pre-Check for Spam duplicate requests
    existing_req = await Database.db.contact_requests.find_one({
        "initiator_id": callback.from_user.id,
        "target_id": target_prof['user_id'],
        "status": "pending",
        "action": db_action
    })
    if existing_req:
        req_type_str = "one-way share" if db_action == "send" else "exchange request"
        return await callback.answer(f"⏳ You already have a pending {req_type_str} with this user.", show_alert=True)
    
    await state.update_data(
        target_uuid=target_uuid, 
        action=db_action,
        selected_contact_ids=[] 
    )
    
    if has_msg:
        await state.set_state(ContactRequest.waiting_for_message)
        await callback.message.answer("Attach a message (or click skip):", reply_markup=skip_message_kb())
        await callback.answer()
    else:
        await show_contact_selection(callback, state)

async def show_contact_selection(event: types.CallbackQuery | types.Message, state: FSMContext):
    user_id = event.from_user.id
    active_prof = await Database.get_active_profile(user_id)
    await Database.sync_telegram_username(active_prof, event.from_user.username)
    active_prof = await Database.get_active_profile(user_id)
    
    data = await state.get_data()
    action = data.get("action")
    
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    
    if not private_contacts and action == "req":
        await state.clear()
        msg_err = "❌ You have no private contacts to share. Please add one first."
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg_err)
        else:
            await event.answer(msg_err)
        return
        
    selected_ids = data.get("selected_contact_ids", [])
    if not selected_ids and private_contacts:
        selected_ids = [private_contacts[0]["id"]]
        await state.update_data(selected_contact_ids=selected_ids)
        
    kb = contact_share_selection_kb(private_contacts, selected_ids, action)
    
    if action == "req":
        text = "🔒 <b>Select Private Contacts for Mutual Exchange</b>\nChoose which private contacts you will share if they agree to the exchange:"
    else:
        text = "🔒 <b>Select Private Contacts to Send (Optional)</b>\nChoose private contacts to send alongside your profile, or send the profile only:"
        
    await state.set_state(ContactRequest.selecting_contacts)
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("selcon_"), ContactRequest.selecting_contacts)
async def toggle_share_selection(callback: types.CallbackQuery, state: FSMContext):
    cid = callback.data.replace("selcon_", "", 1)
    
    data = await state.get_data()
    action = data.get("action")
    selected_ids = data.get("selected_contact_ids", [])
    
    if cid in selected_ids:
        if action == "req" and len(selected_ids) <= 1:
            return await callback.answer("⚠️ You must select at least one contact for a mutual request.", show_alert=True)
        selected_ids.remove(cid)
    else:
        selected_ids.append(cid)
        
    await state.update_data(selected_contact_ids=selected_ids)
    
    active_prof = await Database.get_active_profile(callback.from_user.id)
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    await callback.message.edit_reply_markup(
        reply_markup=contact_share_selection_kb(private_contacts, selected_ids, action)
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_share_contacts", ContactRequest.selecting_contacts)
async def confirm_share_contacts_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    action = data.get("action")
    accepting_req_id = data.get("accepting_req_id")
    
    selected_ids = data.get("selected_contact_ids", [])
    active_prof = await Database.get_active_profile(callback.from_user.id)
    shared_contacts = [c["value"] for c in active_prof.get("contacts", []) if c["id"] in selected_ids]
    
    if action == "req" and not shared_contacts:
        return await callback.answer("⚠️ You must select at least one contact for a mutual request.", show_alert=True)
        
    if accepting_req_id:
        if not shared_contacts:
            return await callback.answer("⚠️ You must select at least one contact to exchange.", show_alert=True)
            
        req = await Database.db.contact_requests.find_one({"req_id": accepting_req_id})
        if not req or req['status'] != 'pending':
            await state.clear()
            return await callback.answer("This request has expired or was already handled.", show_alert=True)
            
        await Database.db.contact_requests.update_one(
            {"req_id": accepting_req_id}, 
            {"$set": {
                "status": "accepted",
                "target_shared_contacts": shared_contacts
            }}
        )
        
        b_profile = await Database.get_active_profile(callback.from_user.id)
        await send_profile(req['initiator_id'], b_profile, kb=None, custom_prefix="👤 <b>Exchanged Profile:</b>\n\n")
        
        contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_contacts)
        await bot.send_message(
            req['initiator_id'], 
            f"✅ <b>Request Accepted!</b>\nThe user shared their contact details:\n\n{contacts_text}"
        )
        
        initiator_shared = req.get("shared_contacts", [])
        if initiator_shared:
            a_profile = await Database.get_active_profile(req['initiator_id'])
            await send_profile(callback.from_user.id, a_profile, kb=None, custom_prefix="👤 <b>Exchanged Profile:</b>\n\n")
            init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
            await callback.message.answer(
                f"🤝 <b>Mutual Exchange Complete!</b>\nHere are the contact details of the user you accepted:\n\n{init_contacts_text}"
            )
            
        await callback.message.delete()
        await state.clear()
        
    else:
        target_uuid = data.get("target_uuid")
        await state.update_data(shared_contacts=shared_contacts)
        success = await execute_contact_request(callback.from_user.id, state, message=None)
        
        await callback.message.delete()
        if success:
            msg = f"✅ Message and contacts sent to <code>{target_uuid}</code>!" if action == "send" else f"✅ Mutual request sent to <code>{target_uuid}</code>!"
            await callback.message.answer(msg, reply_markup=browse_kb())
        else:
            req_type_str = "one-way share" if action == "send" else "exchange request"
            await callback.message.answer(f"⏳ You already have a pending {req_type_str} with this user.", reply_markup=browse_kb())

@router.callback_query(F.data == "cancel_share_contacts", ContactRequest.selecting_contacts)
async def cancel_share_contacts_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Sharing cancelled.", reply_markup=browse_kb())
    await callback.answer()

@router.callback_query(F.data == "skip_req_msg", ContactRequest.waiting_for_message)
async def skip_contact_msg(callback: types.CallbackQuery, state: FSMContext):
    await show_contact_selection(callback, state)

@router.message(ContactRequest.waiting_for_message)
async def capture_contact_msg(message: types.Message, state: FSMContext):
    if message.content_type != 'text': return await message.answer("Please send text only.")
    await state.update_data(message_text=message.text)
    await show_contact_selection(message, state)

async def execute_contact_request(user_id: int, state: FSMContext, message=None) -> bool:
    data = await state.get_data()
    target_prof = await Database.get_profile_by_uuid(data['target_uuid'])
    if not target_prof: return False
    
    action = data['action']
    
    # Strict double-check before saving to database (Protects against parallel API race conditions)
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
        prefix = f"🔔 <b>A USER SHARED THEIR PROFILE WITH YOU!</b>\n"
        if msg_text: prefix += f"💬 <b>Message:</b> {html.escape(msg_text)}\n\n"
        if shared_contacts:
            prefix += "🤝 <b>They also shared private contacts with you!</b>\n"
            
        prefix += "Open '📥 Requests' from your active profile to view details.\n\n"
        await send_profile(target_prof['user_id'], initiator, kb=None, custom_prefix=prefix)
    
    else:
        logger.info(f"Mutual Contact Request {req_id} initiated by {user_id} to {target_prof['user_id']}")
        prefix = f"🔔 <b>NEW CONTACT EXCHANGE REQUEST!</b>\n"
        if msg_text: prefix += f"💬 <b>Message:</b> {html.escape(msg_text)}\n\n"
        prefix += "They want to exchange private contacts simultaneously. Accept to select yours and view theirs.\n\n"
        
        await send_profile(target_prof['user_id'], initiator, contact_decision_kb(req_id), custom_prefix=prefix)
        
    await state.clear()
    return True

@router.callback_query(F.data.startswith("accept_") | F.data.startswith("decline_"))
async def contact_decisions(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    decision = parts[0]
    req_id = parts[1]
    
    req = await Database.db.contact_requests.find_one({"req_id": req_id})
    if not req or req['status'] != 'pending':
        return await callback.answer("This request has expired or was already handled.", show_alert=True)
        
    if decision == "decline":
        await Database.db.contact_requests.update_one({"req_id": req_id}, {"$set": {"status": "declined"}})
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("❌ Request declined and hidden.")
        logger.info(f"Request {req_id} declined.")
        return await callback.answer()
        
    elif decision == "accept":
        active_prof = await Database.get_active_profile(callback.from_user.id)
        private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
        if not private_contacts:
            return await callback.answer("⚠️ You must set at least one private contact under '📝 Edit Active Profile' -> '📞 Manage Contacts' before accepting a mutual request.", show_alert=True)
            
        await state.update_data(
            accepting_req_id=req_id,
            action="accept",
            selected_contact_ids=[private_contacts[0]["id"]]
        )
        await state.set_state(ContactRequest.selecting_contacts)
        
        kb = contact_share_selection_kb(private_contacts, [private_contacts[0]["id"]], action="accept")
        await callback.message.answer(
            "🔒 <b>Select Private Contacts to Exchange</b>\n"
            "Choose which of your private contact details you want to share with this user to complete the mutual exchange:",
            reply_markup=kb
        )
        await callback.answer()