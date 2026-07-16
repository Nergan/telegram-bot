import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    telegram_bot_token: str = ""
    netlazy_api_url: str = ""
    webhook_base_url: Optional[str] = None
    mongodb_uri: str = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    bot_master_key: str = os.environ.get("BOT_MASTER_KEY", "")

    @property
    def resolved_webhook_url(self) -> str:
        return self.webhook_base_url or os.environ.get("RENDER_EXTERNAL_URL", "")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()