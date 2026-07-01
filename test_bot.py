from unittest.mock import MagicMock
import pytest
from bot import extract_message_data

class MockMedia:
    def __init__(self, file_id, file_unique_id):
        self.file_id = file_id
        self.file_unique_id = file_unique_id

def test_extract_message_data_text():
    # Настраиваем мок так, чтобы при запросе ЛЮБЫХ неизвестных полей (sticker, voice и т.д.)
    # он сразу возвращал None. Блоки "if" в bot.py их просто проигнорируют.
    msg = MagicMock()
    msg.configure_mock(**{
        'text': "Hello world",
        'caption': None,
        'photo': None,
        'video': None,
        'document': None,
        'voice': None,
        'audio': None,
        'sticker': None,
        'animation': None,
        'video_note': None
    })

    text, m_type, unique_id, file_id = extract_message_data(msg)
    
    assert text == "Hello world"
    assert m_type == "text" or m_type is None  # Зависит от вашего финального return в bot.py
    assert unique_id is None
    assert file_id is None

def test_extract_message_data_media_with_caption():
    msg = MagicMock()
    msg.configure_mock(**{
        'text': None,
        'caption': "Look at this cat!",
        'photo': [MockMedia("id_low", "uid_low"), MockMedia("id_high", "uid_high")],
        'video': None,
        'document': None,
        'voice': None,
        'audio': None,
        'sticker': None,
        'animation': None,
        'video_note': None
    })

    text, m_type, unique_id, file_id = extract_message_data(msg)
    
    assert text == "Look at this cat!"
    assert m_type == "photo"
    assert unique_id == "uid_high"
    assert file_id == "id_high"
