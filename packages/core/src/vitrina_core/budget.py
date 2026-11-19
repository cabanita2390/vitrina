"""Presupuesto diario de IA (toda la plataforma).

* Redis = contador rápido del gasto del día (micro-USD), con reserva atómica.
* usage_costs = fuente de verdad. Si la clave de Redis no existe (reinicio,
  expiración), se reconstruye sumando usage_costs del día.
* Flujo: estimar -> reserve() -> llamar al proveedor -> settle() con el costo
  real (concilia la diferencia y registra en usage_costs) o release() si falla.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from redis.asyncio import Redis

MICROS = Decimal(1_000_000)
KEY_TTL_SECONDS = 2 * 24 * 3600

# Reserva atómica: solo incrementa si no se supera el límite.
_RESERVE_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
if current + amount > limit then
  return -1
end
return redis.call('INCRBY', KEYS[1], amount)
"""


class BudgetExceededError(Exception):
    """Se alcanzó el presupuesto diario de IA; la llamada se corta."""


@dataclass(frozen=True)
class UsageCost:
    organization_id: UUID
    provider: str
    operation: str
    usd_cost: Decimal
    model: str | None = None
    job_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    characters: int | None = None
    seconds: Decimal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class UsageCostStore(Protocol):
    async def platform_spend_since(self, since: datetime) -> Decimal: ...

    async def record(self, cost: UsageCost) -> None: ...


@dataclass(frozen=True)
class Reservation:
    key: str
    micros: int


def to_micros(usd: Decimal) -> int:
    return int((usd * MICROS).to_integral_value(rounding="ROUND_CEILING"))


class DailyBudget:
    def __init__(
        self,
        redis: Redis,
        store: UsageCostStore,
        limit_usd: Decimal,
        tz: str = "America/Bogota",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._redis = redis
        self._store = store
        self._limit = to_micros(limit_usd)
        self._tz = ZoneInfo(tz)
        self._clock = clock or (lambda: datetime.now(self._tz))
        self._script = redis.register_script(_RESERVE_LUA)

    def _day(self) -> tuple[str, datetime]:
        now = self._clock().astimezone(self._tz)
        start = datetime.combine(now.date(), time.min, tzinfo=self._tz)
        return f"ai_budget:{now.date().isoformat()}", start

    async def _ensure_counter(self) -> str:
        key, start = self._day()
        if not await self._redis.exists(key):
            spent = await self._store.platform_spend_since(start)
            # NX: si otro proceso ya lo reconstruyó, no se pisa.
            await self._redis.set(key, to_micros(spent), nx=True, ex=KEY_TTL_SECONDS)
        return key

    async def spent_today(self) -> Decimal:
        key = await self._ensure_counter()
        value = await self._redis.get(key)
        return Decimal(int(value or 0)) / MICROS

    async def reserve(self, estimate_usd: Decimal) -> Reservation:
        key = await self._ensure_counter()
        micros = to_micros(estimate_usd)
        result = await self._script(keys=[key], args=[micros, self._limit])
        if int(result) < 0:
            raise BudgetExceededError(
                "Se alcanzó el presupuesto diario de IA. Intenta de nuevo mañana "
                "o sube AI_DAILY_BUDGET_USD."
            )
        return Reservation(key=key, micros=micros)

    async def settle(self, reservation: Reservation, cost: UsageCost) -> None:
        # Primero la fuente de verdad; luego se concilia el contador.
        await self._store.record(cost)
        delta = to_micros(cost.usd_cost) - reservation.micros
        if delta:
            await self._redis.incrby(reservation.key, delta)

    async def release(self, reservation: Reservation) -> None:
        await self._redis.decrby(reservation.key, reservation.micros)
