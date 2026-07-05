"""Application configuration.

All values are read from environment variables (or a local .env file) with safe
defaults. The generation settings here are the *enforced* server-side values;
they are never overridable by the browser.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- OpenRouter / provider ---
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemma-3-27b-it"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    MAX_OUTPUT_TOKENS: int = 1000
    TEMPERATURE: float = 0.2
    TOP_P: float = 0.95
    REQUEST_TIMEOUT_SECONDS: float = 60.0

    # Prices for the cost dashboard ($ per 1M tokens). Defaults match
    # google/gemma-3-27b-it on OpenRouter; override in .env if the model changes.
    PRICE_PROMPT_PER_1M: float = 0.08
    PRICE_COMPLETION_PER_1M: float = 0.16

    # --- Limits ---
    MAX_INPUT_CHARS: int = 50000
    MAX_CONTEXT_MESSAGES: int = 20
    RPM_PER_PARTICIPANT: int = 5
    RPH_PER_PARTICIPANT: int = 100
    TOTAL_REQUESTS_PER_PARTICIPANT: int = 300

    # --- Auth ---
    JWT_SECRET: str = ""
    JWT_TTL_HOURS: int = 12

    # --- Storage ---
    DATABASE_URL: str = "sqlite:///./data/app.db"
    REDIS_URL: str = ""  # reserved for a future distributed rate limiter; unused

    # --- Admin / serving ---
    ADMIN_TOKEN: str = ""
    CORS_ORIGINS: str = ""  # comma-separated; empty = same-origin only
    FRONTEND_DIST: str = ""  # override path to built frontend; empty = auto-detect


@lru_cache
def get_settings() -> Settings:
    return Settings()
