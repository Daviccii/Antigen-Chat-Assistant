from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    OPENAI_API_KEY: str | None = None
    DATABASE_URL: str = "postgresql+psycopg2://antigen:antigen@localhost:5432/antigen"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    class Config:
        env_file = [
            str(Path(__file__).resolve().parents[1] / ".env"),
            str(Path(__file__).resolve().parents[1].parent / ".env"),
        ]
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

if not settings.OPENAI_API_KEY:
    settings.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
