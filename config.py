import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    telegram_bot_token: str
    netlazy_api_url: str
    netlazy_bot_token: str
    webhook_base_url: Optional[str] = None

    @property
    def resolved_webhook_url(self) -> str:
        # Fallback to Render's built-in URL if no custom Webhook URL is set
        return self.webhook_base_url or os.environ.get("RENDER_EXTERNAL_URL", "")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()