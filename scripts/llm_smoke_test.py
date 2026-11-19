"""Prueba manual con Claude REAL (gasta centavos). Requiere ANTHROPIC_API_KEY en .env.

Uso:
    uv run python scripts/llm_smoke_test.py            # modelo por defecto (Haiku)
    uv run python scripts/llm_smoke_test.py --quality  # modelo de calidad (Sonnet)

Pasa por el presupuesto diario (Redis) pero NO escribe en usage_costs: usa un
almacén en memoria para no ensuciar la base con una organización ficticia.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime
from decimal import Decimal

from redis.asyncio import Redis

from vitrina_core.budget import DailyBudget, UsageCost
from vitrina_core.config import get_settings
from vitrina_core.providers import build_llm_provider
from vitrina_core.providers.base import LLMMessage, LLMRequest, ProviderNotConfiguredError
from vitrina_core.providers.metered import MeteredLLM

PROMPT = (
    "Eres el asistente de contenido de una panadería en Sogamoso, Boyacá. "
    "Propón 3 ideas de video corto para Instagram esta semana, una línea cada una."
)


class _PrintStore:
    async def platform_spend_since(self, since: datetime) -> Decimal:
        return Decimal(0)

    async def record(self, cost: UsageCost) -> None:
        print(
            f"[costo] {cost.model}: {cost.input_tokens} in / {cost.output_tokens} out "
            f"= USD {cost.usd_cost}"
        )


async def main(quality: bool) -> int:
    settings = get_settings()
    provider = build_llm_provider(settings)
    redis = Redis.from_url(settings.redis_url)
    try:
        budget = DailyBudget(redis, _PrintStore(), settings.ai_daily_budget_usd)
        llm = MeteredLLM(provider, budget)
        request = LLMRequest(
            messages=[LLMMessage("user", PROMPT)],
            model=settings.llm_quality_model if quality else None,
            max_tokens=1000,
            effort="low",
        )
        print(
            f"Modelo: {provider.resolve_model(request)} · "
            f"estimado máx. USD {provider.estimate_cost(request)}"
        )
        response = await llm.complete(
            request, organization_id=uuid.UUID(int=0), job_id="smoke-test"
        )
    except ProviderNotConfiguredError as exc:
        print(f"ERROR: {exc}. Crea la clave en platform.claude.com y ponla en .env.")
        return 1
    finally:
        await redis.aclose()
    print("\n" + response.text)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality", action="store_true", help="usar LLM_QUALITY_MODEL")
    sys.exit(asyncio.run(main(parser.parse_args().quality)))
