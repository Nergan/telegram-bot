import uuid
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.bot_setup import bot
from bot.keyboards import main_menu_kb, profile_card_kb, skip_message_kb, contact_decision_kb
from bot.states import ContactRequest
from core.database import Database

router = Router()

def format_profile(profile_data: dict) -> str:
    text = f"<b>Profile ID:</b> {profile_data.get('public_uuid')}\n\n"
    if profile_data.get('text'):
        text += f"📝 {profile_data['text']}\n\n"
    if profile_data.get('tags'):
        text += f"🏷️ <b>Tags:</b> #{' #'.join(profile_data['tags'])}"
    return text

@router.message(Command("start", "menu"))
async def start_cmd(message: types.Message):
    await Database.get_or_create_profile(message.from_user.id)
    await message.answer(
        "Welcome! Discover people by interests or traits.\n"
        "Fill out as much (or as little) as you want.",
        reply_markup=main_menu_kb()
    )

# --- BROWSING ---

@router.callback_query(F.data == "next_profile")
async def next_profile(callback: types.CallbackQuery):
    # In a real app, retrieve user's search session cursor. 
    # For now, we fetch a random profile they haven't seen.
    pipeline = [{"$match": {"user_id": {"$ne": callback.from_user.id}}}, {"$sample": {"size": 1}}]
    cursor = Database.db.profiles.aggregate(pipeline)
    profiles = await cursor.to_list(length=1)
    
    if not profiles:
        await callback.answer("No more profiles found!", show_alert=True)
        return

    profile = profiles[0]
    text = format_profile(profile)
    kb = profile_card_kb(profile['public_uuid'])

    try:
        # Edit current message to avoid chat spam
        if profile.get('media'):
            media_id = profile['media']['file_id']
            # Example assumes photo. You'd check media_type here.
            media = types.InputMediaPhoto(media=media_id, caption=text)
            await callback.message.edit_media(media=media, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        # Fallback if message types differ (e.g. text -> photo)
        await callback.message.delete()
        if profile.get('media'):
            await callback.message.answer_photo(photo=profile['media']['file_id'], caption=text, reply_markup=kb)
        else:
            await callback.message.answer(text, reply_markup=kb)
    
    await callback.answer()

# --- CONTACT REQUESTS ---

@router.callback_query(F.data.startswith("req_") | F.data.startswith("send_"))
async def init_contact_request(callback: types.CallbackQuery, state: FSMContext):
    action, target_uuid = callback.data.split("_")
    
    await state.update_data(target_uuid=target_uuid, action=action)
    await state.set_state(ContactRequest.waiting_for_message)
    
    prompt = "Attach a message (text, photo, voice) to your request, or skip:"
    await callback.message.answer(prompt, reply_markup=skip_message_kb())
    await callback.answer()

async def execute_contact_request(user_id: int, state: FSMContext, message: types.Message = None):
    data = await state.get_data()
    target_uuid = data['target_uuid']
    action = data['action'] # 'req' or 'send'
    
    target_profile = await Database.db.profiles.find_one({"public_uuid": target_uuid})
    if not target_profile:
        return
        
    req_id = uuid.uuid4().hex
    request_doc = {
        "req_id": req_id,
        "initiator_id": user_id,
        "target_id": target_profile['user_id'],
        "action": action,
        "status": "pending",
        "message": None
    }
    
    if message:
        request_doc['message'] = message.text or message.caption or "[Media]"
        # Here you would also extract file_id if media was sent

    await Database.db.contact_requests.insert_one(request_doc)
    await state.clear()

    # Notify Target
    initiator = await Database.get_or_create_profile(user_id)
    text = f"🔔 <b>New Contact Request!</b>\nFrom Profile: {initiator['public_uuid']}\n"
    if request_doc['message']:
        text += f"💬 Message: <i>{request_doc['message']}</i>\n"
        
    if action == "send":
        text = f"🤝 <b>User shared their contact with you!</b>\n" + text
        
    await bot.send_message(
        target_profile['user_id'], 
        text, 
        reply_markup=contact_decision_kb(req_id, is_sending=(action=="send"))
    )

@router.callback_query(F.data == "skip_req_msg", ContactRequest.waiting_for_message)
async def skip_contact_msg(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await execute_contact_request(callback.from_user.id, state)
    await callback.message.answer("✅ Request sent!")
    await callback.answer()

@router.message(ContactRequest.waiting_for_message)
async def capture_contact_msg(message: types.Message, state: FSMContext):
    await execute_contact_request(message.from_user.id, state, message)
    await message.answer("✅ Request sent with message!")

# --- CONTACT ACCEPTANCE ---

@router.callback_query(F.data.startswith("accept_"))
async def accept_contact(callback: types.CallbackQuery):
    req_id = callback.data.split("_")[1]
    req = await Database.db.contact_requests.find_one({"req_id": req_id})
    
    if not req or req['status'] != 'pending':
        await callback.answer("Request expired.", show_alert=True)
        return
        
    await Database.db.contact_requests.update_one({"req_id": req_id}, {"$set": {"status": "accepted"}})
    
    target_user = await bot.get_chat(callback.from_user.id)
    target_contact = f"@{target_user.username}" if target_user.username else f"<a href='tg://user?id={target_user.id}'>Link</a>"
    
    # Notify Initiator
    await bot.send_message(
        req['initiator_id'], 
        f"✅ <b>Contact Accepted!</b>\nHere is their contact: {target_contact}"
    )
    
    await callback.message.edit_text(callback.message.text + f"\n\n✅ <i>You shared your contact.</i>")
    await callback.answer()