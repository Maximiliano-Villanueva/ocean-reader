"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://ocean:ocean@localhost:5432/ocean_read",
        alias="DATABASE_URL",
    )
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    llm_model: str = Field(default="gemma4:e4b", alias="LLM_MODEL")

    # Legacy DB vector column width for ``chunks.embedding`` (pgvector); keep aligned with migrations.
    embedding_dimension: int = Field(default=768, alias="EMBEDDING_DIMENSION")

    upload_root: str = Field(default="./uploads", alias="UPLOAD_ROOT")

    # Dev: Docker log viewer (mount ``/var/run/docker.sock``). Disable in production.
    log_viewer_enabled: bool = Field(default=False, alias="LOG_VIEWER_ENABLED")
    log_viewer_token: str = Field(default="", alias="LOG_VIEWER_TOKEN")
    compose_project_name: str = Field(default="ocean-read", alias="COMPOSE_PROJECT_NAME")

    # Validation pipeline: optional LLM fallback after regex/layout (temperature 0; internal only).
    validation_llm_fallback_enabled: bool = Field(default=False, alias="VALIDATION_LLM_FALLBACK_ENABLED")


@lru_cache
def get_settings() -> Settings:
    return Settings()
