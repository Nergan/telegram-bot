from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str
    netlazy_api_url: str
    netlazy_bot_token: str
    webhook_base_url: str
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()