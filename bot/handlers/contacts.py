import uuid
import html
import logging
import re
import urllib.parse
import aiohttp
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

async def verify_contact(val: str) -> tuple[bool, str]:
    val = val.strip()

    # 1. Email Check
    if re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', val):
        return True, val

    # 2. Phone Number Check
    if re.match(r'^\+?[0-9\s\-\(\)]{7,20}$', val) and any(c.isdigit() for c in val):
        try:
            import phonenumbers
            # Parse the number, appending '+' if the user forgot it (assumes international format)
            parsed = phonenumbers.parse(val if val.startswith('+') else '+' + val, None)
            if phonenumbers.is_valid_number(parsed):
                formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                return True, formatted
            else:
                return False, "❌ Invalid phone number format or routing. Please include a valid country code (e.g., +1...)"
        except ImportError:
            # Graceful fallback if phonenumbers library is missing
            return True, val
        except Exception:
            return False, "❌ Invalid phone number."

    # 3. Link / URL Check
    url_pattern = re.compile(r'^(https?://)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?$')
    match = url_pattern.match(val)
    if match:
        test_url = val if val.startswith('http') else 'https://' + val
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, timeout=5, allow_redirects=True) as resp:
                    # 404 is the primary "does not exist" indicator for handles and pages
                    if resp.status != 404:
                        return True, test_url
                    else:
                        return False, "❌ The link returned a 404 Not Found error (it doesn't exist)."
        except aiohttp.ClientError:
            return False, "❌ Unreachable link. Make sure the domain exists."
        except Exception:
            return False, "❌ Could not verify the link."

    # 4. Address / Geographic Location Check
    try:
        async with aiohttp.ClientSession() as session:
            # We provide a User-Agent to respect OpenStreetMap's ToS
            headers = {"User-Agent": "DayDatingBot/1.0 (Contact Verification)"}
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(val)}&format=json&limit=1"
            async with session.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        # Grab the neatly formatted standard display name of the location
                        display_name = data[0].get("display_name", val)
                        return True, display_name
    except Exception as e:
        logger.error(f"Geocoding error: {e}")

    # Fallback rejection for made up strings / gibberish
    return False, "❌ Contact could not be verified. Please send a valid link, email, phone number (with + code), or a recognizable geographic address."

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
    await callback.message.answer(
        "Please send the contact detail.\n\n"
        "<b>Supported formats:</b>\n"
        "• 🔗 <b>Link/Handle</b> (e.g., t.me/username, instagram.com/username)\n"
        "• 📱 <b>Phone Number</b> (must include country code, e.g., +1...)\n"
        "• 📍 <b>Address/Location</b> (e.g., New York, NY)\n"
        "• 📧 <b>Email</b>", 
        reply_markup=cancel_fsm_kb()
    )
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
    
    # Validation step
    wait_msg = await message.answer("⏳ <i>Verifying contact formatting and existence... Please wait.</i>")
    is_valid, result_val = await verify_contact(contact_val)
    await wait_msg.delete()
    
    if not is_valid:
        return await message.answer(f"{result_val}\n\nPlease try again:")
        
    # Prevent over-filling database if OSM resolves an extremely long address string
    if len(result_val) > 100:
        result_val = result_val[:97] + "..."
    
    cid = uuid.uuid4().hex[:8]
    new_contact = {
        "id": cid,
        "type": "custom",
        "value": result_val,
        "is_public": False 
    }
    
    await Database.db.profiles.update_one(
        {"public_uuid": active_prof['public_uuid']},
        {"$push": {"contacts": new_contact}}
    )
    
    await message.answer("✅ Contact successfully verified and added! You can toggle its visibility in the manager.", reply_markup=edit_info_menu_kb())
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