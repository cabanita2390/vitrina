"""Configuración desde variables de entorno (.env en local)."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """Busca .env subiendo desde el directorio actual (raíz del monorepo)."""
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Supabase
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: SecretStr = SecretStr("")
    supabase_service_role_key: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr = SecretStr("")
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # LLM
    anthropic_api_key: SecretStr = SecretStr("")
    llm_provider: str = "anthropic"
    llm_default_model: str = "claude-haiku-5-5"
    llm_quality_model: str = "claude-sonnet-5-5"

    # Presupuesto diario de IA (USD, toda la plataforma)
    ai_daily_budget_usd: Decimal = Decimal("1.00")

    # Servicios internos
    tts_url: str = "http://127.0.0.1:8100"
    renderer_url: str = "http://127.0.0.1:8200"

    sentry_dsn: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
