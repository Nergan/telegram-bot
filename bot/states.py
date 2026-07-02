from aiogram.fsm.state import State, StatesGroup

class ContactRequest(StatesGroup):
    waiting_for_message = State()

class ProfileSetup(StatesGroup):
    waiting_for_bio = State()
    waiting_for_media = State()
    waiting_for_pub_contact = State()
    waiting_for_priv_contact = State()