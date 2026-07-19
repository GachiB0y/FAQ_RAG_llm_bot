from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    BACKEND_URL: str = "http://backend:8000"
    TELEGRAM_BOT_EMAIL: str
    TELEGRAM_BOT_PASSWORD: str
    REQUEST_TIMEOUT: float = 30.0

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    return Settings()
