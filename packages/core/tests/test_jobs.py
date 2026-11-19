from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import fakeredis
import pytest
from arq.connections import ArqRedis
from redis.asyncio import ConnectionPool

from vitrina_core.jobs import ArqJobQueue, TenantJobPayload, make_job_id

ORG = uuid.UUID("33333333-3333-3333-3333-333333333333")


class Payload(TenantJobPayload):
    credits: int


@pytest.fixture
async def arq_redis() -> AsyncIterator[ArqRedis]:
    pool = ConnectionPool(
        connection_class=fakeredis.FakeAsyncRedisConnection, server=fakeredis.FakeServer()
    )
    redis = ArqRedis(connection_pool=pool)
    yield redis
    await redis.aclose()


def test_job_id_is_deterministic() -> None:
    p = Payload(organization_id=ORG, credits=1)
    assert make_job_id("x", p, "k1") == make_job_id("x", p, "k1")
    assert make_job_id("x", p, "k1") != make_job_id("x", p, "k2")


@pytest.mark.parametrize("key", ["", "k" * 151])
def test_job_id_rejects_bad_keys(key: str) -> None:
    with pytest.raises(ValueError, match="idempotency_key"):
        make_job_id("x", Payload(organization_id=ORG, credits=1), key)


def test_payload_requires_organization() -> None:
    with pytest.raises(ValueError, match="organization_id"):
        Payload(credits=1)  # type: ignore[call-arg]


async def test_arq_queue_deduplicates(arq_redis: ArqRedis) -> None:
    queue = ArqJobQueue(arq_redis)
    payload = Payload(organization_id=ORG, credits=5)
    first = await queue.enqueue("example_charge", payload, "render-1")
    second = await queue.enqueue("example_charge", payload, "render-1")
    other = await queue.enqueue("example_charge", payload, "render-2")
    assert first.enqueued is True
    assert second.enqueued is False
    assert second.job_id == first.job_id
    assert other.enqueued is True
