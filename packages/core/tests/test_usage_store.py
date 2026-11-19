"""PostgresUsageCostStore contra Supabase local (fuente de verdad del presupuesto)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from vitrina_core.budget import UsageCost
from vitrina_core.db import TenantDB
from vitrina_core.usage_store import PostgresUsageCostStore

pytestmark = pytest.mark.db


async def test_record_and_sum(settings: Any, make_user: Any) -> None:
    org = uuid.UUID(make_user("Heladería Paipa").organization_id)
    pool = TenantDB.create_pool(settings.database_url, max_size=1)
    await pool.open()
    try:
        store = PostgresUsageCostStore(pool)
        since = datetime.now(UTC) - timedelta(seconds=1)
        before = await store.platform_spend_since(since)
        await store.record(
            UsageCost(
                organization_id=org,
                provider="anthropic",
                operation="llm_call",
                usd_cost=Decimal("0.004321"),
                model="claude-haiku-5-5",
                input_tokens=100,
                output_tokens=50,
                metadata={"stop_reason": "end_turn"},
            )
        )
        after = await store.platform_spend_since(since)
    finally:
        await pool.close()
    assert after - before == Decimal("0.004321")
