from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    openai_api_key: str | None = None
    groq_api_key: str | None = None  # <-- Add this line

    class Config:
        env_file = ".env"

settings = Settings()