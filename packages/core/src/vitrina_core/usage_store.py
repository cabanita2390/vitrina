"""UsageCostStore sobre Postgres (tabla usage_costs)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from psycopg import AsyncConnection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from vitrina_core.budget import UsageCost
from vitrina_core.db import TenantDB


class PostgresUsageCostStore:
    def __init__(self, pool: AsyncConnectionPool[AsyncConnection[DictRow]]) -> None:
        self._pool = pool
        self._db = TenantDB(pool)

    async def platform_spend_since(self, since: datetime) -> Decimal:
        # ÚNICA consulta deliberadamente global (sin organization_id): el
        # presupuesto diario es de toda la plataforma. Solo lee un agregado.
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select coalesce(sum(usd_cost), 0) as total "
                "from public.usage_costs where created_at >= %(since)s",
                {"since": since},
            )
            row = await cur.fetchone()
        return Decimal(row["total"]) if row else Decimal(0)

    async def record(self, cost: UsageCost) -> None:
        async with self._db.scoped(cost.organization_id) as conn:
            await conn.execute(
                "insert into public.usage_costs (organization_id, job_id, provider, model, "
                "operation, input_tokens, output_tokens, characters, seconds, usd_cost, metadata) "
                "values (%(organization_id)s, %(job_id)s, %(provider)s, %(model)s, %(operation)s, "
                "%(input_tokens)s, %(output_tokens)s, %(characters)s, %(seconds)s, %(usd_cost)s, "
                "%(metadata)s)",
                {
                    "job_id": cost.job_id,
                    "provider": cost.provider,
                    "model": cost.model,
                    "operation": cost.operation,
                    "input_tokens": cost.input_tokens,
                    "output_tokens": cost.output_tokens,
                    "characters": cost.characters,
                    "seconds": cost.seconds,
                    "usd_cost": cost.usd_cost,
                    "metadata": Jsonb(cost.metadata),
                },
            )
