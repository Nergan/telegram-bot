from unittest.mock import MagicMock
import pytest
from bot import extract_message_data

class MockMedia:
    def __init__(self, file_id, file_unique_id):
        self.file_id = file_id
        self.file_unique_id = file_unique_id

def make_mock_message(**kwargs):
    """
    Вспомогательная функция для создания мока сообщения.
    Гарантирует, что все неиспользуемые свойства будут иметь значение None,
    что предотвращает AttributeError и ложные срабатывания условий в bot.py.
    """
    default_fields = {
        'text': None,
        'caption': None,
        'photo': None,
        'video': None,
        'document': None,
        'voice': None,
        'audio': None,
        'sticker': None,
        'animation': None,
        'video_note': None,
        'content_type': 'text'
    }
    # Обновляем дефолтные поля переданными значениями
    default_fields.update(kwargs)
    
    msg = MagicMock()
    msg.configure_mock(**default_fields)
    return msg

def test_extract_message_data_text():
    msg = make_mock_message(text="Hello world", content_type="text")

    text, m_type, unique_id, file_id = extract_message_data(msg)
    
    assert text == "Hello world"
    assert m_type == "text" or m_type is None
    assert unique_id is None
    assert file_id is None

def test_extract_message_data_media_with_caption():
    msg = make_mock_message(
        caption="Look at this cat!",
        photo=[MockMedia("id_low", "uid_low"), MockMedia("id_high", "uid_high")],
        content_type="photo"
    )

    text, m_type, unique_id, file_id = extract_message_data(msg)
    
    assert text == "Look at this cat!"
    assert m_type == "photo"
    assert unique_id == "uid_high"
    assert file_id == "id_high"

def test_extract_message_data_video_note():
    msg = make_mock_message(
        content_type="video_note",
        video_note=MockMedia("vn_id", "vn_uid")
    )
    
    text, m_type, unique_id, file_id = extract_message_data(msg)
    
    # Видеозаметки в Telegram не имеют подписей, поэтому возвращается стандартный плейсхолдер
    assert text == "[video_note]"
    assert m_type == "video_note"
    assert unique_id == "vn_uid"
    assert file_id == "vn_id"

def test_extract_message_data_animation():
    msg = make_mock_message(
        content_type="animation",
        caption="Funny GIF",
        animation=MockMedia("anim_id", "anim_uid")
    )
    
    text, m_type, unique_id, file_id = extract_message_data(msg)
    
    assert text == "Funny GIF"
    assert m_type == "animation"
    assert unique_id == "anim_uid"
    assert file_id == "anim_id"