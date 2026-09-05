from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    DATABASE_URL: str = "postgresql+psycopg2://antigen:antigen@localhost:5432/antigen"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_NUM_CTX: int = 2048  # Context window size
    OLLAMA_NUM_GPU: int = 0  # Number of GPU layers (0 = CPU only, safer default)
    OLLAMA_TEMPERATURE: float = 0.7  # Generation temperature
    OLLAMA_TOP_P: float = 0.9  # Top-p sampling
    SECRET_KEY: str = "change-this-in-production-use-environment-variable"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    FRONTEND_URL: str = "http://localhost:5173"

    # env_file_encoding='utf-8-sig' strips a leading BOM if one is present
    # (common when a .env is created via PowerShell's Out-File -Encoding utf8),
    # and is harmless for files that don't have one.
    model_config = SettingsConfigDict(env_file=str(ENV_PATH), env_file_encoding="utf-8-sig")


settings = Settings()

if __name__ == "__main__":
    # Quick manual check: run `python -m app.config` from backend/ to confirm
    # the key is actually being picked up, without printing the key itself.
    print(f"Looking for .env at: {ENV_PATH}")
    print(f".env exists: {ENV_PATH.exists()}")
    print(f"OPENAI_API_KEY loaded: {bool(settings.OPENAI_API_KEY)}")

