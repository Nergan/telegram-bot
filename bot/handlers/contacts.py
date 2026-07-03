import uuid
import html
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from bot.states import ProfileSetup
from bot.keyboards import (
    edit_info_menu_kb,
    cancel_fsm_kb,
    manage_contacts_inline_kb
)
from core.database import Database

router = Router()
logger = logging.getLogger(__name__)

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
    await callback.message.answer("Please send the contact detail (e.g. phone, email, link):", reply_markup=cancel_fsm_kb())
    await callback.answer()

@router.message(ProfileSetup.waiting_for_contact_val)
async def capture_new_contact(message: types.Message, state: FSMContext):
    if message.text == "❌ Cancel":
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state)
        return
    if message.content_type != 'text': 
        return await message.answer("❌ Please send text only.")
    
    user_id = message.from_user.id
    active_prof = await Database.get_active_profile(user_id)
    
    contacts = active_prof.get("contacts", [])
    if len(contacts) >= 8:
        await state.clear()
        await message.answer("❌ You can have a maximum of 8 contacts per profile.", reply_markup=edit_info_menu_kb())
        await manage_contacts_menu(message)
        return
        
    contact_val = message.text.strip()
    
    if len(contact_val) > 100:
        return await message.answer("❌ Contact details must be 100 characters or less. Please try again:")
    if "\n" in contact_val or "\r" in contact_val:
        return await message.answer("❌ Contact details must be a single line (no line breaks). Please try again:")
    if len(contact_val) < 3:
        return await message.answer("❌ Contact details are too short. Please try again:")
    
    cid = uuid.uuid4().hex[:8]
    new_contact = {
        "id": cid,
        "type": "custom",
        "value": contact_val,
        "is_public": False 
    }
    
    await Database.db.profiles.update_one(
        {"public_uuid": active_prof['public_uuid']},
        {"$push": {"contacts": new_contact}}
    )
    
    await message.answer("✅ Contact successfully added! You can toggle its visibility in the manager.", reply_markup=edit_info_menu_kb())
    await state.clear()
    await manage_contacts_menu(message)

@router.callback_query(F.data.startswith("togglecon_"))
async def toggle_contact_visibility(callback: types.CallbackQuery):
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