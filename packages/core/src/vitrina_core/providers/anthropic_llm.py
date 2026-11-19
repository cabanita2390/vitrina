"""LLMProvider real con Claude (Anthropic SDK).

Sin ANTHROPIC_API_KEY la app arranca igual: el error aparece solo al llamar.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import anthropic

from vitrina_core.providers.base import (
    LLMRequest,
    LLMResponse,
    ProviderError,
    ProviderNotConfiguredError,
)
from vitrina_core.providers.pricing import cost_usd

MISSING_KEY_MESSAGE = "falta ANTHROPIC_API_KEY"
CHARS_PER_TOKEN = 3  # estimación conservadora para español


class AnthropicLLMProvider:
    name = "anthropic"

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._client: anthropic.AsyncAnthropic | None = None

    def resolve_model(self, request: LLMRequest) -> str:
        return request.model or self._default_model

    def estimate_cost(self, request: LLMRequest) -> Decimal:
        chars = len(request.system) + sum(len(m.content) for m in request.messages)
        input_tokens = chars // CHARS_PER_TOKEN + 50
        # Peor caso: el modelo usa todo max_tokens (incluye razonamiento).
        return cost_usd(self.resolve_model(request), input_tokens, request.max_tokens)

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if not self._api_key:
            raise ProviderNotConfiguredError(MISSING_KEY_MESSAGE)
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        model = self.resolve_model(request)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.system:
            kwargs["system"] = request.system
        if request.effort:
            kwargs["output_config"] = {"effort": request.effort}

        try:
            message = await client.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise ProviderNotConfiguredError("ANTHROPIC_API_KEY inválida") from exc
        except anthropic.APIError as exc:
            raise ProviderError(f"error de Anthropic: {exc}") from exc

        usage = message.usage
        cache_write = usage.cache_creation_input_tokens or 0
        cache_read = usage.cache_read_input_tokens or 0
        usd = cost_usd(model, usage.input_tokens, usage.output_tokens, cache_write, cache_read)

        # Una negativa (stop_reason="refusal") se devuelve igual: tiene costo y
        # MeteredLLM la registra antes de convertirla en ProviderRefusalError.
        text = "".join(block.text for block in message.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=message.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            usd_cost=usd,
            stop_reason=message.stop_reason,
            raw_usage={
                "cache_creation_input_tokens": cache_write,
                "cache_read_input_tokens": cache_read,
                "request_id": message._request_id,
            },
        )
