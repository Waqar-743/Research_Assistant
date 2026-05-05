"""
Configuration management for the Research Assistant.
Loads environment variables and provides settings for all components.
"""

import json
import os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional, Union
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # FastAPI Configuration
    app_name: str = "Multi-Agent Research Assistant"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="FASTAPI_DEBUG")
    host: str = Field(default="0.0.0.0", alias="FASTAPI_HOST")
    port: int = Field(default=8000, alias="FASTAPI_PORT")
    workers: int = Field(default=1, alias="FASTAPI_WORKERS")

    # MongoDB Configuration
    mongodb_url: str = Field(
        default="mongodb://localhost:27017",
        alias="MONGODB_URL"
    )
    mongodb_database: str = Field(
        default="research_assistant_db",
        alias="MONGODB_DATABASE"
    )

    # Redis Cache (optional — app works without it)
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    cache_ttl: int = Field(default=86400, alias="CACHE_TTL")

    # Sentry Error Tracking (optional)
    sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")

    # LLM Configuration (OpenRouter)
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL"
    )

    # Model selections for different agents
    researcher_model: str = Field(default="deepseek/deepseek-chat", alias="RESEARCHER_MODEL")
    analyst_model: str = Field(default="anthropic/claude-3.5-sonnet", alias="ANALYST_MODEL")
    fact_checker_model: str = Field(default="openai/gpt-4o", alias="FACT_CHECKER_MODEL")
    report_generator_model: str = Field(default="deepseek/deepseek-chat", alias="REPORT_GENERATOR_MODEL")

    # External Search APIs (all optional — fallbacks exist)
    serpapi_key: Optional[str] = Field(default=None, alias="SERPAPI_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    google_search_engine_id: Optional[str] = Field(default=None, alias="GOOGLE_SEARCH_ENGINE_ID")
    newsapi_key: Optional[str] = Field(default=None, alias="NEWSAPI_KEY")

    # Academic API base URLs
    arxiv_api_base: str = Field(
        default="https://export.arxiv.org/api/query",
        alias="ARXIV_API_BASE"
    )
    pubmed_api_base: str = Field(
        default="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        alias="PUBMED_API_BASE"
    )
    wikipedia_api_base: str = Field(
        default="https://en.wikipedia.org/api/rest_v1",
        alias="WIKIPEDIA_API_BASE"
    )

    # Security
    secret_key: str = Field(
        default="change-this-in-production-use-strong-key",
        alias="SECRET_KEY"
    )
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # CORS — accepts either a JSON array string or a Python list
    allowed_origins: Union[List[str], str] = Field(
        default=["*"],
        alias="ALLOWED_ORIGINS"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Accept both a real list and a JSON-encoded string from env vars."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Comma-separated fallback
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", alias="LOG_FILE")

    # Research Settings
    max_sources_default: int = Field(default=300, alias="MAX_SOURCES_DEFAULT")
    agent_timeout: int = Field(default=120, alias="AGENT_TIMEOUT")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings (call once per process)."""
    return Settings()


settings = get_settings()
