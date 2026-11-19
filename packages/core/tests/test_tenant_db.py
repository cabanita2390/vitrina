"""TenantConnection obliga a filtrar por la organización del trabajo."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from vitrina_core.db import TenantConnection, TenantScopeError

SQL = "select 1 from public.brand_kits where organization_id = %(organization_id)s and id = %(id)s"
ORG = uuid.UUID("44444444-4444-4444-4444-444444444444")


class RecordingConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, sql: str, params: dict[str, Any]) -> None:
        self.calls.append((sql, params))


@pytest.fixture
def rec() -> RecordingConn:
    return RecordingConn()


@pytest.fixture
def conn(rec: RecordingConn) -> TenantConnection:
    return TenantConnection(rec, ORG)  # type: ignore[arg-type]


async def test_rejects_query_without_org_filter(conn: TenantConnection) -> None:
    with pytest.raises(TenantScopeError):
        await conn.execute("select * from public.brand_kits")


async def test_rejects_other_org(conn: TenantConnection) -> None:
    with pytest.raises(TenantScopeError):
        await conn.execute(
            "select 1 from public.brand_kits where organization_id = %(organization_id)s",
            {"organization_id": uuid.uuid4()},
        )


async def test_injects_job_org(conn: TenantConnection, rec: RecordingConn) -> None:
    await conn.execute(
        SQL,
        {"id": 7},
    )
    assert rec.calls == [
        (
            SQL,
            {"id": 7, "organization_id": ORG},
        )
    ]
