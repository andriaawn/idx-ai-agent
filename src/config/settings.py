from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str = ""
    admin_id: str = ""
    llm_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./idxagent.db" # Default fallback for local testing if no env provided
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
