from aiogram.fsm.state import State, StatesGroup

class ContactRequest(StatesGroup):
    waiting_for_message = State()
    selecting_contacts = State() # Выбор конкретных приватных контактов перед отправкой

class ProfileSetup(StatesGroup):
    waiting_for_bio = State()
    waiting_for_media = State()
    waiting_for_contact_val = State() # Состояние добавления кастомного контакта
    waiting_for_delete_all = State()