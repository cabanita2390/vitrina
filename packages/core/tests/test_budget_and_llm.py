"""Presupuesto diario, medición de costos y proveedor de Anthropic sin clave.

Los dobles (FakeLLM, MemoryStore) existen SOLO aquí, en pruebas automatizadas.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import fakeredis
import pytest
from redis.asyncio import Redis

from vitrina_core.budget import BudgetExceededError, DailyBudget, UsageCost
from vitrina_core.config import Settings
from vitrina_core.providers import build_llm_provider
from vitrina_core.providers.anthropic_llm import AnthropicLLMProvider
from vitrina_core.providers.base import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRefusalError,
)
from vitrina_core.providers.metered import MeteredLLM
from vitrina_core.providers.pricing import cost_usd

ORG = uuid.UUID("55555555-5555-5555-5555-555555555555")
BOGOTA = ZoneInfo("America/Bogota")
NOW = datetime(2026, 11, 19, 10, 0, tzinfo=BOGOTA)
REQ = LLMRequest(messages=[LLMMessage("user", "Hola")], max_tokens=100)


class MemoryStore:
    def __init__(self, initial: Decimal = Decimal(0)) -> None:
        self.records: list[UsageCost] = []
        self.initial = initial
        self.rebuilds = 0

    async def platform_spend_since(self, since: datetime) -> Decimal:
        self.rebuilds += 1
        return self.initial + sum((r.usd_cost for r in self.records), Decimal(0))

    async def record(self, cost: UsageCost) -> None:
        self.records.append(cost)


class FakeLLM:
    name = "fake"

    def __init__(
        self, estimate: str, actual: str, stop: str = "end_turn", fail: bool = False
    ) -> None:
        self.estimate, self.actual, self.stop, self.fail = (
            Decimal(estimate),
            Decimal(actual),
            stop,
            fail,
        )

    def resolve_model(self, request: LLMRequest) -> str:
        return "fake-model"

    def estimate_cost(self, request: LLMRequest) -> Decimal:
        return self.estimate

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if self.fail:
            raise ProviderError("caído")
        return LLMResponse("ok", "fake-model", 10, 5, self.actual, self.stop)


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    r = fakeredis.FakeAsyncRedis(server=fakeredis.FakeServer())
    yield r
    await r.aclose()


def make_budget(redis: Redis, store: MemoryStore, limit: str = "1.00") -> DailyBudget:
    return DailyBudget(redis, store, Decimal(limit), clock=lambda: NOW)


# ----------------------------------------------------------------------------- precios


def test_haiku_cost() -> None:
    # Prompt bajo el umbral de 100K: 50K x 0,10/M + 50K x 0,50/M
    assert cost_usd("claude-haiku-5-5", 50_000, 50_000) == Decimal("0.030000")


def test_haiku_long_context_price() -> None:
    assert cost_usd("claude-haiku-5-5", 200_000, 0) == Decimal("0.100000")  # 0,50/M


def test_cache_pricing() -> None:
    assert cost_usd("claude-sonnet-5-5", 0, 0, cache_write_tokens=1_000_000) == Decimal("2.5")
    assert cost_usd("claude-sonnet-5-5", 0, 0, cache_read_tokens=1_000_000) == Decimal("0.2")


# ----------------------------------------------------------------------------- presupuesto


async def test_settle_reconciles_with_actual_cost(redis: Redis) -> None:
    store = MemoryStore()
    llm = MeteredLLM(FakeLLM(estimate="0.10", actual="0.02"), make_budget(redis, store))
    await llm.complete(REQ, organization_id=ORG, job_id="j1")
    assert len(store.records) == 1
    assert store.records[0].usd_cost == Decimal("0.02")
    assert store.records[0].organization_id == ORG
    assert await make_budget(redis, store).spent_today() == Decimal("0.02")


async def test_budget_blocks_when_estimate_exceeds_limit(redis: Redis) -> None:
    store = MemoryStore(initial=Decimal("0.95"))
    llm = MeteredLLM(FakeLLM(estimate="0.10", actual="0.10"), make_budget(redis, store))
    with pytest.raises(BudgetExceededError):
        await llm.complete(REQ, organization_id=ORG)
    assert store.records == []


async def test_counter_rebuilds_from_usage_costs_after_redis_restart(redis: Redis) -> None:
    store = MemoryStore()
    budget = make_budget(redis, store)
    llm = MeteredLLM(FakeLLM(estimate="0.30", actual="0.30"), budget)
    await llm.complete(REQ, organization_id=ORG)
    await llm.complete(REQ, organization_id=ORG)

    await redis.flushall()  # Redis se reinicia y pierde el contador

    assert await budget.spent_today() == Decimal("0.60")  # reconstruido desde la BD
    await llm.complete(REQ, organization_id=ORG)  # 0,90 <= 1,00
    with pytest.raises(BudgetExceededError):
        await llm.complete(REQ, organization_id=ORG)  # 1,20 > 1,00


async def test_failed_call_releases_reservation(redis: Redis) -> None:
    store = MemoryStore()
    budget = make_budget(redis, store)
    with pytest.raises(ProviderError):
        await MeteredLLM(FakeLLM("0.50", "0", fail=True), budget).complete(REQ, organization_id=ORG)
    assert await budget.spent_today() == Decimal(0)
    assert store.records == []


async def test_refusal_is_recorded_then_raised(redis: Redis) -> None:
    store = MemoryStore()
    llm = MeteredLLM(FakeLLM("0.10", "0.01", stop="refusal"), make_budget(redis, store))
    with pytest.raises(ProviderRefusalError):
        await llm.complete(REQ, organization_id=ORG)
    assert [r.usd_cost for r in store.records] == [Decimal("0.01")]


async def test_concurrent_reservations_never_exceed_limit(redis: Redis) -> None:
    budget = make_budget(redis, MemoryStore())
    results = await asyncio.gather(
        *(budget.reserve(Decimal("0.30")) for _ in range(10)), return_exceptions=True
    )
    ok = [r for r in results if not isinstance(r, BaseException)]
    assert len(ok) == 3  # 3 x 0,30 = 0,90; la cuarta superaría 1,00


# ----------------------------------------------------------------------------- Anthropic


async def test_anthropic_without_key_fails_clearly() -> None:
    provider = AnthropicLLMProvider(api_key="", default_model="claude-haiku-5-5")
    with pytest.raises(ProviderNotConfiguredError, match="falta ANTHROPIC_API_KEY"):
        await provider.complete(REQ)


def test_app_settings_build_provider_without_key() -> None:
    provider = build_llm_provider(Settings(anthropic_api_key="", llm_provider="anthropic"))
    assert provider.name == "anthropic"
    assert provider.resolve_model(REQ) == "claude-haiku-5-5"
    assert provider.estimate_cost(REQ) > 0
