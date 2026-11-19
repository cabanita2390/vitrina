"""Configuración del worker arq.

Ejecutar: `arq vitrina_worker.main.WorkerSettings`
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from arq.connections import RedisSettings

from vitrina_core.config import get_settings
from vitrina_core.db import TenantDB
from vitrina_core.logging import configure_logging
from vitrina_worker.tasks import example_charge

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.log_level)
    logging.getLogger("arq").propagate = False  # arq ya tiene su handler
    pool = TenantDB.create_pool(_settings.database_url)
    await pool.open()
    ctx["db_pool"] = pool
    ctx["db"] = TenantDB(pool)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["db_pool"].close()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [example_charge]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_tries = 3
    job_timeout = 600
    keep_result = 24 * 3600  # dedupe de job_id durante 24 h
