from aiogram.fsm.state import State, StatesGroup

class ContactRequest(StatesGroup):
    waiting_for_message = State()

class ProfileSetup(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()