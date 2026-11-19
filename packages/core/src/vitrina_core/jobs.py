"""Cola de trabajos detrás de una interfaz propia.

La API y las tareas solo conocen `JobQueue`. La implementación actual usa arq;
cambiar de librería = escribir otra clase que cumpla el protocolo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from arq.connections import ArqRedis


class TenantJobPayload(BaseModel):
    """Base de todo payload de trabajo: siempre lleva la organización dueña."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: UUID


@dataclass(frozen=True)
class EnqueueResult:
    job_id: str
    enqueued: bool  # False si ya existía un trabajo con la misma clave (duplicado)


class JobQueue(Protocol):
    async def enqueue(
        self, job_name: str, payload: TenantJobPayload, idempotency_key: str
    ) -> EnqueueResult: ...


def make_job_id(job_name: str, payload: TenantJobPayload, idempotency_key: str) -> str:
    """Id determinista: el mismo trabajo lógico produce siempre el mismo id."""
    if not idempotency_key or len(idempotency_key) > 150:
        raise ValueError("idempotency_key debe tener entre 1 y 150 caracteres")
    return f"{job_name}:{payload.organization_id}:{idempotency_key}"


class ArqJobQueue:
    """Implementación con arq. arq descarta un job_id que ya está en cola o con
    resultado guardado; la idempotencia definitiva la garantiza cada tarea
    (p. ej., la clave única de credit_ledger)."""

    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue(
        self, job_name: str, payload: TenantJobPayload, idempotency_key: str
    ) -> EnqueueResult:
        job_id = make_job_id(job_name, payload, idempotency_key)
        job = await self._redis.enqueue_job(
            job_name, payload.model_dump(mode="json"), idempotency_key, _job_id=job_id
        )
        return EnqueueResult(job_id=job_id, enqueued=job is not None)
