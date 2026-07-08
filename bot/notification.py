from domain.interfaces import INotificationService    
from domain.models import Profile
from bot.bot_setup import bot
from bot.helpers import send_profile
from application.services import TagService

class TelegramNotificationService(INotificationService):
    def __init__(self, tag_service: TagService):
        self.tag_service = tag_service

    async def notify_text(self, user_id: int, text: str) -> None:
        try:
            await bot.send_message(user_id, text)
        except Exception:
            pass

    async def notify_profile(self, user_id: int, profile: Profile, lang: str, custom_prefix: str = "") -> None:
        try:
            await send_profile(user_id, profile, None, lang, self.tag_service, custom_prefix)
        except Exception:
            pass