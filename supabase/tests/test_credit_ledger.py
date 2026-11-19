"""credit_ledger es inmutable a nivel de base de datos y nunca cobra dos veces."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import psycopg
import pytest

pytestmark = pytest.mark.db


@pytest.fixture
def ledger_entry(make_user: Any, db: psycopg.Connection[Any]) -> tuple[str, str]:
    u = make_user("Cafetería Paipa")
    key = f"job-{uuid.uuid4().hex}"
    row = db.execute(
        "insert into public.credit_ledger (organization_id, delta, reason, idempotency_key) "
        "values (%s, -5, 'job_charge', %s) returning id",
        (u.organization_id, key),
    ).fetchone()
    assert row is not None
    return str(row[0]), u.organization_id


@pytest.mark.parametrize(
    "sql",
    [
        "update public.credit_ledger set delta = 1000 where id = %s",
        "delete from public.credit_ledger where id = %s",
    ],
)
def test_superuser_cannot_mutate_ledger(
    db: psycopg.Connection[Any], ledger_entry: tuple[str, str], sql: str
) -> None:
    entry_id, _ = ledger_entry
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="inmutable"):
        db.execute(sql, (entry_id,))


def test_truncate_blocked(db: psycopg.Connection[Any]) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="inmutable"):
        db.execute("truncate public.credit_ledger")


@pytest.mark.parametrize("role", ["service_role", "authenticated"])
def test_roles_have_no_update_delete_grant(db: psycopg.Connection[Any], role: str) -> None:
    row = db.execute(
        "select has_table_privilege(%s, 'public.credit_ledger', 'UPDATE'),"
        "       has_table_privilege(%s, 'public.credit_ledger', 'DELETE')",
        (role, role),
    ).fetchone()
    assert row == (False, False)


def test_service_role_rest_cannot_update(
    settings: Any, service_headers: dict[str, str], ledger_entry: tuple[str, str]
) -> None:
    entry_id, _ = ledger_entry
    r = httpx.patch(
        f"{settings.supabase_url}/rest/v1/credit_ledger",
        headers=service_headers,
        params={"id": f"eq.{entry_id}"},
        json={"delta": 1000},
        timeout=10,
    )
    assert r.status_code in (401, 403)


def test_idempotency_key_prevents_double_charge(
    db: psycopg.Connection[Any], make_user: Any
) -> None:
    u = make_user("Droguería Duitama")
    sql = (
        "insert into public.credit_ledger (organization_id, delta, reason, idempotency_key) "
        "values (%s, -3, 'job_charge', 'render-123') on conflict do nothing returning id"
    )
    first = db.execute(sql, (u.organization_id,)).fetchone()
    second = db.execute(sql, (u.organization_id,)).fetchone()
    assert first is not None
    assert second is None
    balance = db.execute(
        "select balance from public.credit_balances where organization_id = %s",
        (u.organization_id,),
    ).fetchone()
    assert balance == (-3,)


def test_signup_trigger_is_security_definer_with_fixed_search_path(
    db: psycopg.Connection[Any],
) -> None:
    row = db.execute(
        "select p.prosecdef, p.proconfig from pg_proc p "
        "join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname = 'private' and p.proname = 'handle_new_user'"
    ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] == ['search_path=""']
