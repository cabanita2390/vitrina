"""Operaciones sobre el libro de créditos (siempre acotadas por organización)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vitrina_core.db import TenantConnection


class InsufficientCreditsError(Exception):
    pass


@dataclass(frozen=True)
class ChargeResult:
    status: Literal["charged", "already_charged"]
    balance: int


async def get_balance(conn: TenantConnection) -> int:
    row = await conn.fetchone(
        "select coalesce(sum(delta), 0)::bigint as balance "
        "from public.credit_ledger where organization_id = %(organization_id)s"
    )
    return int(row["balance"]) if row else 0


async def charge(
    conn: TenantConnection, credits: int, idempotency_key: str, job_id: str | None = None
) -> ChargeResult:
    """Cobra `credits` una sola vez por idempotency_key.

    Serializa los cobros de la misma organización con un advisory lock de
    transacción para que dos trabajos concurrentes no dejen el saldo negativo.
    """
    if credits <= 0:
        raise ValueError("credits debe ser positivo")

    await conn.execute(
        "select pg_advisory_xact_lock(hashtextextended(%(organization_id)s::text, 0))"
    )
    existing = await conn.fetchone(
        "select 1 from public.credit_ledger "
        "where organization_id = %(organization_id)s and idempotency_key = %(key)s",
        {"key": idempotency_key},
    )
    if existing:
        return ChargeResult("already_charged", await get_balance(conn))

    balance = await get_balance(conn)
    if balance < credits:
        raise InsufficientCreditsError(f"saldo {balance} < {credits}")

    await conn.execute(
        "insert into public.credit_ledger "
        "(organization_id, delta, reason, idempotency_key, job_id) "
        "values (%(organization_id)s, %(delta)s, 'job_charge', %(key)s, %(job_id)s)",
        {"delta": -credits, "key": idempotency_key, "job_id": job_id},
    )
    return ChargeResult("charged", balance - credits)
