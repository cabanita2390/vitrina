"""Tarea de ejemplo contra Supabase local: idempotente y acotada por organización."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest

from vitrina_core.credits import InsufficientCreditsError
from vitrina_core.db import TenantConnection, TenantDB
from vitrina_worker.tasks import example_charge

pytestmark = pytest.mark.db


@pytest.fixture
async def ctx(settings: Any) -> AsyncIterator[dict[str, Any]]:
    pool = TenantDB.create_pool(settings.database_url, max_size=2)
    await pool.open()
    yield {"db": TenantDB(pool), "job_id": "test-job"}
    await pool.close()


@pytest.fixture
def orgs(make_user: Any, db: psycopg.Connection[Any]) -> tuple[str, str]:
    a = make_user("Restaurante A")
    b = make_user("Restaurante B")
    for org in (a.organization_id, b.organization_id):
        db.execute(
            "insert into public.credit_ledger (organization_id, delta, reason, idempotency_key) "
            "values (%s, 10, 'manual_topup', 'seed')",
            (org,),
        )
    return a.organization_id, b.organization_id


def _balance(db: psycopg.Connection[Any], org: str) -> int:
    row = db.execute(
        "select balance from public.credit_balances where organization_id = %s", (org,)
    ).fetchone()
    return int(row[0]) if row else 0


async def test_charges_once_and_only_job_org(
    ctx: dict[str, Any], orgs: tuple[str, str], db: psycopg.Connection[Any]
) -> None:
    org_a, org_b = orgs
    payload = {"organization_id": org_a, "credits": 4}

    first = await example_charge(ctx, payload, "video-1")
    retry = await example_charge(ctx, payload, "video-1")

    assert first == {"status": "charged", "balance": 6}
    assert retry == {"status": "already_charged", "balance": 6}
    assert _balance(db, org_a) == 6
    assert _balance(db, org_b) == 10  # la otra organización no se toca


async def test_insufficient_credits(ctx: dict[str, Any], orgs: tuple[str, str]) -> None:
    org_a, _ = orgs
    with pytest.raises(InsufficientCreditsError):
        await example_charge(ctx, {"organization_id": org_a, "credits": 11}, "video-big")


async def test_every_worker_query_filters_by_job_org(
    ctx: dict[str, Any], orgs: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    org_a, _ = orgs
    seen: list[tuple[str, Any]] = []
    original = TenantConnection._params

    def spy(self: TenantConnection, sql: str, params: Any) -> dict[str, Any]:
        merged = original(self, sql, params)
        seen.append((sql, merged["organization_id"]))
        return merged

    monkeypatch.setattr(TenantConnection, "_params", spy)
    await example_charge(ctx, {"organization_id": org_a, "credits": 1}, f"k-{uuid.uuid4()}")

    assert seen, "la tarea no ejecutó consultas"
    for sql, org in seen:
        assert "%(organization_id)s" in sql
        assert str(org) == org_a
