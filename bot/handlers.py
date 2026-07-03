import uuid
import html
import asyncio
import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from bot.bot_setup import bot
from bot.states import ProfileSetup, ContactRequest
from bot.keyboards import *
from bot.helpers import send_profile
from core.database import Database

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
@router.message(F.text == "🏠 View Active Profile")
async def show_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    logger.info(f"User {message.from_user.id} accessed main menu.")
    active_profile = await Database.get_or_create_active_profile(message.from_user.id, message.from_user.username)
    await message.answer("🏠 View Active Profile 🏠", reply_markup=main_menu_kb())
    await send_profile(message.chat.id, active_profile, profile_inline_kb(active_profile['public_uuid']))

@router.message(F.text == "🔒 View Private Contacts")
async def view_private_contacts(message: types.Message):
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.sync_telegram_username(active_prof, message.from_user.username)
    active_prof = await Database.get_active_profile(message.from_user.id)
    
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    if private_contacts:
        text = "🔒 <b>Your Private Contacts:</b>\n\n"
        for c in private_contacts:
            text += f"• <code>{html.escape(c['value'])}</code>\n"
        await message.answer(text)
    else:
        await message.answer("🔒 You have not set any Private Contacts yet.")

# --- FSM CAPTURE ---

@router.message(F.text == "📝 Edit Info")
async def edit_info_menu(message: types.Message):
    await message.answer("What would you like to edit?", reply_markup=edit_info_menu_kb())

@router.message(F.text == "✏️ Bio")
async def init_edit_bio(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_bio)
    await message.answer("Send your new Bio:", reply_markup=edit_fsm_kb())

# --- UNIFIED CONTACTS MANAGER ---

@router.message(F.text == "📞 Manage Contacts")
async def manage_contacts_menu(message: types.Message):
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.sync_telegram_username(active_prof, message.from_user.username)
    active_prof = await Database.get_active_profile(message.from_user.id)
    
    contacts = active_prof.get("contacts", [])
    text = "📞 <b>Manage Your Contacts</b>\n\n"
    if contacts:
        for i, c in enumerate(contacts):
            visibility = "🌐 Public" if c.get("is_public") else "🔒 Private"
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
    else:
        text += "You have no contacts set yet."
        
    kb = manage_contacts_inline_kb(contacts)
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "add_contact_fsm")
async def add_contact_fsm_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_contact_val)
    await callback.message.answer("Please send the contact detail (e.g. phone, email, link):", reply_markup=edit_fsm_kb())
    await callback.answer()

@router.message(ProfileSetup.waiting_for_contact_val)
async def capture_new_contact(message: types.Message, state: FSMContext):
    if message.text in ["❌ Cancel", "🗑️ Clear Field"]: return
    if message.content_type != 'text': return await message.answer("❌ Please send text only.")
    
    user_id = message.from_user.id
    active_prof = await Database.get_active_profile(user_id)
    
    cid = uuid.uuid4().hex[:8]
    new_contact = {
        "id": cid,
        "type": "custom",
        "value": message.text,
        "is_public": False 
    }
    
    await Database.db.profiles.update_one(
        {"public_uuid": active_prof['public_uuid']},
        {"$push": {"contacts": new_contact}}
    )
    
    await message.answer("✅ Contact added as Private! You can toggle its visibility in the manager.", reply_markup=main_menu_kb())
    await state.clear()
    await manage_contacts_menu(message)

@router.callback_query(F.data.startswith("togglecon_"))
async def toggle_contact_visibility(callback: types.CallbackQuery):
    # Безопасное извлечение ID контакта, поддерживающее символы подчеркивания (tg_username)
    cid = callback.data.replace("togglecon_", "", 1)
    active_prof = await Database.get_active_profile(callback.from_user.id)
    
    contacts = active_prof.get("contacts", [])
    updated = False
    for c in contacts:
        if c.get("id") == cid:
            c["is_public"] = not c.get("is_public", False)
            updated = True
            break
            
    if updated:
        await Database.db.profiles.update_one({"_id": active_prof["_id"]}, {"$set": {"contacts": contacts}})
        await callback.answer("Visibility toggled!")
        
        active_prof = await Database.get_profile_by_uuid(active_prof["public_uuid"])
        contacts = active_prof.get("contacts", [])
        text = "📞 <b>Manage Your Contacts</b>\n\n"
        for i, c in enumerate(contacts):
            visibility = "🌐 Public" if c.get("is_public") else "🔒 Private"
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
            
        await callback.message.edit_text(text, reply_markup=manage_contacts_inline_kb(contacts))
    else:
        await callback.answer("Contact not found.", show_alert=True)

@router.callback_query(F.data.startswith("delcon_"))
async def delete_contact(callback: types.CallbackQuery):
    # Безопасное извлечение ID
    cid = callback.data.replace("delcon_", "", 1)
    if cid == "tg_username":
        return await callback.answer("❌ You cannot delete your Telegram username contact.", show_alert=True)
        
    active_prof = await Database.get_active_profile(callback.from_user.id)
    await Database.db.profiles.update_one(
        {"_id": active_prof["_id"]},
        {"$pull": {"contacts": {"id": cid}}}
    )
    await callback.answer("Contact deleted!")
    
    active_prof = await Database.get_profile_by_uuid(active_prof["public_uuid"])
    contacts = active_prof.get("contacts", [])
    text = "📞 <b>Manage Your Contacts</b>\n\n"
    if contacts:
        for i, c in enumerate(contacts):
            visibility = "🌐 Public" if c.get("is_public") else "🔒 Private"
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
    else:
        text += "You have no contacts set yet."
        
    await callback.message.edit_text(text, reply_markup=manage_contacts_inline_kb(contacts))

# --- MEDIA EDIT ---

@router.message(F.text == "📸 Edit Media")
async def init_edit_media(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_media)
    await message.answer("Send a single media file, OR an album of up to 10 photos/videos in one message.", reply_markup=edit_fsm_kb())

@router.message(F.text == "❌ Cancel", flags={"state": "*"})
async def fsm_cancel(message: types.Message, state: FSMContext):
    await show_main_menu(message, state)

@router.message(F.text == "🗑️ Clear Field")
async def fsm_clear(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    field_map = {
        ProfileSetup.waiting_for_bio: "text",
        ProfileSetup.waiting_for_contact_val: "contacts",
        ProfileSetup.waiting_for_media: "media"
    }
    field = field_map.get(curr_state)
    if field:
        active_prof = await Database.get_active_profile(message.from_user.id)
        val = [] if field in ["media", "contacts"] else None
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {field: val}})
        logger.info(f"User {message.from_user.id} cleared {field}.")
    await show_main_menu(message, state)

@router.message(ProfileSetup.waiting_for_bio)
async def capture_text(message: types.Message, state: FSMContext):
    if message.text in ["❌ Cancel", "🗑️ Clear Field"]: return
    if message.content_type != 'text': return await message.answer("❌ Please send text only.")
    
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"text": message.text}})
    logger.info(f"User {message.from_user.id} updated bio.")
    await message.answer("✅ Saved!", reply_markup=main_menu_kb())
    updated = await Database.get_active_profile(message.from_user.id)
    await send_profile(message.chat.id, updated, profile_inline_kb(updated['public_uuid']))
    await state.clear()

@router.message(ProfileSetup.waiting_for_media)
async def capture_media(message: types.Message, state: FSMContext):
    if message.text in ["❌ Cancel", "🗑️ Clear Field"]: return
    valid_types = ['photo', 'video', 'voice', 'animation', 'audio', 'document']
    if message.content_type not in valid_types:
        return await message.answer("❌ Invalid media type.")
        
    active_prof = await Database.get_active_profile(message.from_user.id)
    media_doc = {"type": message.content_type}
    if message.photo: media_doc['file_id'] = message.photo[-1].file_id
    elif message.video: media_doc['file_id'] = message.video.file_id
    elif message.voice: media_doc['file_id'] = message.voice.file_id
    elif message.animation: media_doc['file_id'] = message.animation.file_id
    elif message.audio: media_doc['file_id'] = message.audio.file_id
    elif message.document: media_doc['file_id'] = message.document.file_id
    
    if message.media_group_id:
        data = await state.get_data()
        mg_id = data.get("current_mg_id")
        if mg_id != message.media_group_id:
            await state.update_data(current_mg_id=message.media_group_id)
            await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"media": [media_doc]}})
            await message.answer("✅ Processing album...", reply_markup=main_menu_kb())
            
            async def show_updated_profile_after_delay():
                await asyncio.sleep(1.5)
                curr_state = await state.get_state()
                if curr_state == ProfileSetup.waiting_for_media:
                    updated = await Database.get_active_profile(message.from_user.id)
                    await send_profile(message.chat.id, updated, profile_inline_kb(updated['public_uuid']))
                    await state.clear()
            
            asyncio.create_task(show_updated_profile_after_delay())
        else:
            await Database.db.profiles.update_one(
                {"public_uuid": active_prof['public_uuid']}, 
                {"$push": {"media": {"$each": [media_doc], "$slice": 10}}}
            )
    else:
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"media": [media_doc]}})
        await message.answer("✅ Media saved!", reply_markup=main_menu_kb())
        updated = await Database.get_active_profile(message.from_user.id)
        await send_profile(message.chat.id, updated, profile_inline_kb(updated['public_uuid']))
        await state.clear()

# --- PROFILES MANAGEMENT ---

@router.message(F.text == "👥 Profiles")
async def profiles_menu(message: types.Message):
    cursor = Database.db.profiles.find({"user_id": message.from_user.id})
    profiles = await cursor.to_list(length=100)
    count = len(profiles)
    
    inline_kb = []
    for p in profiles:
        status = "🌟 Active" if p.get("is_active") else "⚪ Inactive"
        if p.get("is_hidden"): status += " 👻 Hidden"
        inline_kb.append([InlineKeyboardButton(text=f"{p['public_uuid']} [{status}]", callback_data=f"manage_prof_{p['public_uuid']}")])
        
    await message.answer("👥 Profiles", reply_markup=profiles_menu_kb())
    if inline_kb:
        await message.answer(
            f"👥 <b>Your Profiles Pool ({count}/100)</b>\nSelect an identity below to manage it:", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb)
        )

@router.message(F.text == "➕ Create Profile")
async def create_profile_cmd(message: types.Message):
    prof = await Database.create_profile(message.from_user.id, message.from_user.username)
    if not prof:
        return await message.answer("❌ You have reached the maximum limit of 100 profiles.")
    await message.answer("✅ New profile created!")
    await profiles_menu(message)

@router.message(F.text == "🗑️ Delete All But Active")
async def del_all_but_active(message: types.Message):
    await Database.delete_all_but_active(message.from_user.id)
    await message.answer("✅ All inactive profiles deleted.")
    await profiles_menu(message)

# --- BROWSING & CONTACT REQUESTS ---

@router.message(F.text.in_({"🔍 Browse", "⏩ Next Profile"}))
async def browse_next(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    active = await Database.get_active_profile(user_id)
    await Database.sync_telegram_username(active, message.from_user.username)
    active = await Database.get_active_profile(user_id)
    
    seen_uuids = await Database.get_seen_profiles(user_id)
    
    filters = active.get("filters", {})
    and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}, {"is_hidden": False}]
    if filters.get("require_tags"): and_clauses.append({"tags": {"$all": filters["require_tags"]}})
    if filters.get("exclude_tags"): and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
    if filters.get("any_tags"): and_clauses.append({"tags": {"$in": filters["any_tags"]}})
        
    pipeline = [{"$match": {"$and": and_clauses + [{"public_uuid": {"$nin": seen_uuids}}]}}, {"$sample": {"size": 1}}]
    cursor = Database.db.profiles.aggregate(pipeline)
    profiles = await cursor.to_list(length=1)
    
    if not profiles:
        pipeline_all = [{"$match": {"$and": and_clauses}}, {"$sample": {"size": 1}}]
        cursor_all = Database.db.profiles.aggregate(pipeline_all)
        all_profiles = await cursor_all.to_list(length=1)
        
        if not all_profiles:
            return await message.answer("No matching profiles found!", reply_markup=main_menu_kb())
        else:
            await Database.clear_seen_profiles(user_id)
            await message.answer("🔄 You have viewed all matching profiles. Showing them a second time.")
            profiles = all_profiles

    target = profiles[0]
    await Database.add_seen_profile(user_id, target['public_uuid'])
    
    await message.answer("🔍 Browsing...", reply_markup=browse_kb())
    
    private_contacts = [c for c in active.get("contacts", []) if not c.get("is_public")]
    has_private = len(private_contacts) > 0
    
    await send_profile(message.chat.id, target, browse_inline_kb(target['public_uuid'], has_private=has_private))

@router.callback_query(F.data == "no_private_alert")
async def no_private_alert_cb(callback: types.CallbackQuery):
    await callback.answer(
        "⚠️ You have no private contacts to share!\n"
        "Please add a private contact under '📝 Edit Info' -> '📞 Manage Contacts' first.",
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
        
    existing_req = await Database.db.contact_requests.find_one({
        "initiator_id": callback.from_user.id,
        "target_id": target_prof['user_id'],
        "status": "pending"
    })
    if existing_req:
        return await callback.answer("⏳ You already have a pending request with this user.", show_alert=True)
        
    is_send = action_type.startswith("send")
    has_msg = action_type.endswith("msg")
    db_action = "send" if is_send else "req"
    
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
        if db_action == "send":
            await show_contact_selection(callback, state)
        else:
            await callback.answer("Sending request...")
            await execute_contact_request(callback.from_user.id, state, message=None)
            await callback.message.answer(f"✅ Request sent to {target_uuid}!", reply_markup=browse_kb())

async def show_contact_selection(event: types.CallbackQuery | types.Message, state: FSMContext):
    user_id = event.from_user.id
    active_prof = await Database.get_active_profile(user_id)
    await Database.sync_telegram_username(active_prof, event.from_user.username)
    active_prof = await Database.get_active_profile(user_id)
    
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    
    if not private_contacts:
        await state.clear()
        msg_err = "❌ You have no private contacts to share. Please add one first."
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg_err)
        else:
            await event.answer(msg_err)
        return
        
    data = await state.get_data()
    selected_ids = data.get("selected_contact_ids", [])
    if not selected_ids:
        selected_ids = [private_contacts[0]["id"]]
        await state.update_data(selected_contact_ids=selected_ids)
        
    kb = contact_share_selection_kb(private_contacts, selected_ids)
    text = "🔒 <b>Select Private Contacts to Share</b>\nChoose which of your private contact details you want to share:"
    
    await state.set_state(ContactRequest.selecting_contacts)
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("selcon_"), ContactRequest.selecting_contacts)
async def toggle_share_selection(callback: types.CallbackQuery, state: FSMContext):
    cid = callback.data.split("_")[1]
    data = await state.get_data()
    selected_ids = data.get("selected_contact_ids", [])
    
    if cid in selected_ids:
        if len(selected_ids) <= 1:
            return await callback.answer("⚠️ You must select at least one contact to share.", show_alert=True)
        selected_ids.remove(cid)
    else:
        selected_ids.append(cid)
        
    await state.update_data(selected_contact_ids=selected_ids)
    
    active_prof = await Database.get_active_profile(callback.from_user.id)
    private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
    await callback.message.edit_reply_markup(
        reply_markup=contact_share_selection_kb(private_contacts, selected_ids)
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_share_contacts", ContactRequest.selecting_contacts)
async def confirm_share_contacts_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    accepting_req_id = data.get("accepting_req_id")
    
    selected_ids = data.get("selected_contact_ids", [])
    active_prof = await Database.get_active_profile(callback.from_user.id)
    shared_contacts = [c["value"] for c in active_prof.get("contacts", []) if c["id"] in selected_ids]
    
    if accepting_req_id:
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
        
        contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_contacts)
        
        await bot.send_message(
            req['initiator_id'], 
            f"✅ <b>Request Accepted!</b>\nThe user shared their contact details:\n\n{contacts_text}"
        )
        
        initiator_shared = req.get("shared_contacts", [])
        if initiator_shared:
            init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
            await callback.message.answer(
                f"🤝 <b>You shared your contact details.</b>\nHere are the contact details they shared with you:\n\n{init_contacts_text}"
            )
        else:
            await callback.message.answer("✅ You accepted the request. They received your contact info.")
            
        await callback.message.delete()
        await state.clear()
        
    else:
        target_uuid = data.get("target_uuid")
        await state.update_data(shared_contacts=shared_contacts)
        await execute_contact_request(callback.from_user.id, state, message=None)
        await callback.message.delete()
        await callback.message.answer(f"✅ Contact details shared with {target_uuid}!", reply_markup=browse_kb())

@router.callback_query(F.data == "cancel_share_contacts", ContactRequest.selecting_contacts)
async def cancel_share_contacts_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Sharing cancelled.", reply_markup=browse_kb())
    await callback.answer()

@router.callback_query(F.data == "skip_req_msg", ContactRequest.waiting_for_message)
async def skip_contact_msg(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    action = data.get("action")
    if action == "send":
        await show_contact_selection(callback, state)
    else:
        target_uuid = data['target_uuid']
        await callback.message.delete()
        await execute_contact_request(callback.from_user.id, state, message=None)
        await callback.message.answer(f"✅ Request sent to {target_uuid}!", reply_markup=browse_kb())

@router.message(ContactRequest.waiting_for_message)
async def capture_contact_msg(message: types.Message, state: FSMContext):
    if message.content_type != 'text': return await message.answer("Please send text only.")
    data = await state.get_data()
    action = data.get("action")
    
    await state.update_data(message_text=message.text)
    
    if action == "send":
        await show_contact_selection(message, state)
    else:
        target_uuid = data['target_uuid']
        await execute_contact_request(message.from_user.id, state, message)
        await message.answer(f"✅ Request sent to {target_uuid} with message!", reply_markup=browse_kb())

async def execute_contact_request(user_id: int, state: FSMContext, message=None):
    data = await state.get_data()
    target_prof = await Database.get_profile_by_uuid(data['target_uuid'])
    if not target_prof: return
    
    req_id = uuid.uuid4().hex
    msg_text = message.text if message else data.get("message_text")
    shared_contacts = data.get("shared_contacts", [])
    
    req_doc = {
        "req_id": req_id, 
        "initiator_id": user_id, 
        "target_id": target_prof['user_id'], 
        "action": data['action'], 
        "status": "pending", 
        "message": msg_text,
        "shared_contacts": shared_contacts
    }
    await Database.db.contact_requests.insert_one(req_doc)
    logger.info(f"Contact Request {req_id} initiated by {user_id} to {target_prof['user_id']}")
    
    initiator = await Database.get_active_profile(user_id)
    
    prefix = f"🔔 <b>NEW CONTACT REQUEST!</b>\n"
    if msg_text: prefix += f"💬 <b>Message:</b> {html.escape(msg_text)}\n\n"
    if data['action'] == "send":
        contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_contacts)
        prefix = f"🤝 <b>A USER SHARED THEIR CONTACT!</b>\nShared details:\n{contacts_text}\n\n" + prefix
        
    await send_profile(target_prof['user_id'], initiator, contact_decision_kb(req_id, is_sending=(data['action']=="send")), custom_prefix=prefix)
    await state.clear()

# --- CONTACT DECISION HANDLERS ---

@router.callback_query(F.data.startswith("accept_") | F.data.startswith("decline_") | F.data.startswith("counter_"))
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
        
    elif decision == "accept":
        active_prof = await Database.get_active_profile(callback.from_user.id)
        await Database.sync_telegram_username(active_prof, callback.from_user.username)
        active_prof = await Database.get_active_profile(callback.from_user.id)
        
        private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
        if not private_contacts:
            return await callback.answer("⚠️ You must set at least one private contact under '📝 Edit Info' -> '📞 Manage Contacts' first.", show_alert=True)
            
        await state.update_data(
            accepting_req_id=req_id,
            selected_contact_ids=[private_contacts[0]["id"]]
        )
        await state.set_state(ContactRequest.selecting_contacts)
        
        kb = contact_share_selection_kb(private_contacts, [private_contacts[0]["id"]])
        await callback.message.answer(
            "🔒 <b>Select Private Contacts to Share</b>\n"
            "Choose which of your private contact details you want to share with this user:",
            reply_markup=kb
        )
        await callback.answer()
        
    elif decision == "counter":
        await Database.db.contact_requests.update_one({"req_id": req_id}, {"$set": {"status": "countered"}})
        
        new_req_id = uuid.uuid4().hex
        counter_doc = {
            "req_id": new_req_id,
            "initiator_id": callback.from_user.id,
            "target_id": req['initiator_id'],
            "action": "req",
            "status": "pending",
            "is_counter": True, 
            "message": "[Automated Counter-Request]"
        }
        await Database.db.contact_requests.insert_one(counter_doc)
        
        target_prof = await Database.get_active_profile(callback.from_user.id)
        prefix = f"🔄 <b>COUNTER REQUEST!</b>\nThe user wants you to share your contact first.\n\n"
        
        await send_profile(req['initiator_id'], target_prof, contact_decision_kb(new_req_id, is_sending=False, can_counter=False), custom_prefix=prefix)
        
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("🔄 You asked them to share their contact first. Awaiting response.")
        logger.info(f"Request {req_id} countered.")
        
    await callback.answer()

# --- FALLBACK HANDLER ---
@router.message()
async def unhandled_message(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    if curr_state:
        await message.answer("❌ Invalid input for this step. Please correct it or press '❌ Cancel'.")
    else:
        active = await Database.get_active_profile(message.from_user.id)
        if active:
            await message.answer("🤷 Unrecognized command. Please use the menu buttons below.", reply_markup=main_menu_kb())
        else:
            await message.answer("🤷 Send /start to begin.")