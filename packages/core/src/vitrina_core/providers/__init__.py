"""Proveedores externos detrás de interfaces. Selección por configuración."""

from __future__ import annotations

from vitrina_core.config import Settings
from vitrina_core.providers.anthropic_llm import AnthropicLLMProvider
from vitrina_core.providers.base import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            default_model=settings.llm_default_model,
        )
    raise ValueError(f"LLM_PROVIDER desconocido: {settings.llm_provider}")
