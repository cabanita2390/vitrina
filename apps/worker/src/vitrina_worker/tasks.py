"""Tareas del worker.

Cada tarea recibe (ctx, payload_dict, idempotency_key), valida el payload con su
modelo y trabaja SOLO con la conexión acotada a la organización del trabajo.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vitrina_core.credits import charge
from vitrina_core.db import TenantDB
from vitrina_core.jobs import TenantJobPayload
from vitrina_core.logging import get_logger

log = get_logger(__name__)


class ExampleChargePayload(TenantJobPayload):
    credits: int = Field(gt=0, le=10_000)
    description: str = Field(default="", max_length=200)


async def example_charge(
    ctx: dict[str, Any], payload: dict[str, Any], idempotency_key: str
) -> dict[str, Any]:
    """Tarea de ejemplo idempotente: cobra créditos una sola vez por clave.

    Si arq la reintenta o se encola dos veces, el cobro no se repite.
    """
    data = ExampleChargePayload.model_validate(payload)
    db: TenantDB = ctx["db"]
    job_id = str(ctx.get("job_id", ""))
    async with db.scoped(data.organization_id) as conn:
        result = await charge(conn, data.credits, idempotency_key, job_id=job_id or None)
    log.info(
        "example_charge",
        organization_id=str(data.organization_id),
        status=result.status,
        balance=result.balance,
        job_id=job_id,
    )
    return {"status": result.status, "balance": result.balance}
