from aiogram.fsm.state import State, StatesGroup

class ContactRequest(StatesGroup):
    waiting_for_message = State()
    selecting_contacts = State()

class ProfileSetup(StatesGroup):
    waiting_for_bio = State()
    waiting_for_media = State()
    waiting_for_contact_val = State()