"""Aislamiento multi-tenant vía Supabase directo (PostgREST con JWT reales).

Un usuario de la organización A no puede leer ni escribir datos de la organización B.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.db


@pytest.fixture
def tenants(make_user: Any, service_headers: dict[str, str], settings: Any) -> tuple[Any, Any]:
    a = make_user("Panadería A")
    b = make_user("Ferretería B")
    base = f"{settings.supabase_url}/rest/v1"
    # Datos de B creados por el sistema
    r = httpx.post(
        f"{base}/brand_kits",
        headers={**service_headers, "Prefer": "return=representation"},
        json={"organization_id": b.organization_id, "name": "Marca B"},
        timeout=10,
    )
    r.raise_for_status()
    r = httpx.post(
        f"{base}/credit_ledger",
        headers=service_headers,
        json={
            "organization_id": b.organization_id,
            "delta": 100,
            "reason": "manual_topup",
            "idempotency_key": "topup-test-b",
        },
        timeout=10,
    )
    r.raise_for_status()
    r = httpx.post(
        f"{base}/usage_costs",
        headers=service_headers,
        json={
            "organization_id": b.organization_id,
            "provider": "anthropic",
            "operation": "llm_call",
            "usd_cost": "0.001",
        },
        timeout=10,
    )
    r.raise_for_status()
    return a, b


def test_signup_creates_org_and_owner_membership(make_user: Any, rest: Any) -> None:
    u = make_user("Tienda Sogamoso")
    with rest(u.token) as c:
        orgs = c.get("/organizations", params={"select": "id,name,kind"}).json()
        members = c.get("/memberships", params={"select": "user_id,role"}).json()
    assert orgs == [{"id": u.organization_id, "name": "Tienda Sogamoso", "kind": "business"}]
    assert members == [{"user_id": u.user_id, "role": "owner"}]


@pytest.mark.parametrize(
    "table", ["organizations", "memberships", "brand_kits", "credit_ledger", "credit_balances"]
)
def test_user_a_cannot_read_org_b(tenants: tuple[Any, Any], rest: Any, table: str) -> None:
    a, b = tenants
    org_col = "id" if table == "organizations" else "organization_id"
    with rest(a.token) as c:
        rows = c.get(f"/{table}", params={"select": "*"}).json()
        targeted = c.get(f"/{table}", params={org_col: f"eq.{b.organization_id}"}).json()
    assert all(r[org_col] == a.organization_id for r in rows)
    assert targeted == []


def test_usage_costs_hidden_from_all_users(tenants: tuple[Any, Any], rest: Any) -> None:
    a, b = tenants
    for user in (a, b):
        with rest(user.token) as c:
            r = c.get("/usage_costs")
        assert r.status_code in (200, 401, 403)
        assert r.status_code != 200 or r.json() == []


def test_user_a_cannot_write_brand_kit_of_org_b(tenants: tuple[Any, Any], rest: Any) -> None:
    a, b = tenants
    with rest(a.token) as c:
        ins = c.post("/brand_kits", json={"organization_id": b.organization_id, "name": "Intruso"})
        upd = c.patch(
            "/brand_kits",
            params={"organization_id": f"eq.{b.organization_id}"},
            json={"name": "Hackeado"},
            headers={"Prefer": "return=representation"},
        )
        dele = c.delete(
            "/brand_kits",
            params={"organization_id": f"eq.{b.organization_id}"},
            headers={"Prefer": "return=representation"},
        )
    assert ins.status_code in (401, 403)
    assert upd.json() == []
    assert dele.json() == []


def test_user_a_can_write_own_brand_kit(tenants: tuple[Any, Any], rest: Any) -> None:
    a, _ = tenants
    with rest(a.token) as c:
        r = c.post(
            "/brand_kits",
            json={"organization_id": a.organization_id, "name": "Marca A"},
            headers={"Prefer": "return=representation"},
        )
    assert r.status_code == 201
    assert r.json()[0]["organization_id"] == a.organization_id


def test_user_a_cannot_rename_org_b(tenants: tuple[Any, Any], rest: Any) -> None:
    a, b = tenants
    with rest(a.token) as c:
        r = c.patch(
            "/organizations",
            params={"id": f"eq.{b.organization_id}"},
            json={"name": "Robada"},
            headers={"Prefer": "return=representation"},
        )
    assert r.json() == []
    with rest(b.token) as c:
        assert c.get("/organizations").json()[0]["name"] == "Ferretería B"


def test_users_cannot_grant_credits_or_join_orgs(tenants: tuple[Any, Any], rest: Any) -> None:
    a, b = tenants
    with rest(a.token) as c:
        credit = c.post(
            "/credit_ledger",
            json={
                "organization_id": a.organization_id,
                "delta": 999,
                "reason": "manual_topup",
                "idempotency_key": "self-grant",
            },
        )
        join = c.post(
            "/memberships",
            json={"organization_id": b.organization_id, "user_id": a.user_id, "role": "owner"},
        )
    assert credit.status_code in (401, 403)
    assert join.status_code in (401, 403)


@pytest.mark.parametrize(
    "table", ["organizations", "memberships", "brand_kits", "credit_ledger", "usage_costs"]
)
def test_anon_sees_nothing(tenants: tuple[Any, Any], rest: Any, table: str) -> None:
    with rest(None) as c:
        r = c.get(f"/{table}")
    assert r.status_code in (401, 403) or r.json() == []
