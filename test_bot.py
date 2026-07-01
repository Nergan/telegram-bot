import pytest
import time
from bot import extract_message_data, get_user_data, should_update_user_db

# Dummy mock classes for aiogram Types
class MockUser:
    def __init__(self, id, is_bot=False, first_name="Test", last_name=None, username=None, language_code="en", is_premium=False):
        self.id = id
        self.is_bot = is_bot
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.language_code = language_code
        self.is_premium = is_premium

class MockMedia:
    def __init__(self, file_unique_id):
        self.file_unique_id = file_unique_id

class MockMessage:
    def __init__(self, text=None, content_type="text", photo=None, video=None):
        self.text = text
        self.content_type = content_type
        self.photo = photo
        self.video = video

def test_extract_message_data_text():
    msg = MockMessage(text="Hello world")
    text, m_type, unique_id = extract_message_data(msg)
    assert text == "Hello world"
    assert m_type == "text"
    assert unique_id is None

def test_extract_message_data_media():
    msg = MockMessage(content_type="photo", photo=[MockMedia(file_unique_id="def456"), MockMedia(file_unique_id="abc123_max_res")])
    text, m_type, unique_id = extract_message_data(msg)
    assert text == "[photo]"
    assert m_type == "photo"
    assert unique_id == "abc123_max_res" # Always picks the last/highest resolution item

def test_get_user_data():
    user = MockUser(id=999, first_name="John", username="johndoe", is_premium=True)
    data = get_user_data(user)
    assert data["user_id"] == 999
    assert data["is_premium"] is True
    assert data["first_name"] == "John"
    assert "phone_number" not in data # Documenting that this isn't natively available

def test_user_db_rate_limiter():
    user_id = 42
    # First time seeing the user, should trigger DB update
    assert should_update_user_db(user_id) is True
    
    # Second time immediately after, should return False (rate limited)
    assert should_update_user_db(user_id) is False