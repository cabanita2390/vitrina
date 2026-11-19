"""Acceso a Postgres con service role, acotado por organización.

El worker se conecta como superusuario/service role y SALTA la RLS. Para que eso
no rompa el aislamiento, todo acceso pasa por `TenantConnection`, que:
  * exige que cada sentencia filtre por `%(organization_id)s`, y
  * inyecta siempre el organization_id del trabajo (no se puede sobrescribir).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection, AsyncCursor
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

ORG_PLACEHOLDER = "%(organization_id)s"


class TenantScopeError(RuntimeError):
    """Una consulta intentó saltarse el filtro por organización."""


class TenantConnection:
    def __init__(self, conn: AsyncConnection[DictRow], organization_id: UUID) -> None:
        self._conn = conn
        self.organization_id = organization_id

    def _params(self, sql: str, params: Mapping[str, Any] | None) -> dict[str, Any]:
        if ORG_PLACEHOLDER not in sql:
            raise TenantScopeError("Toda consulta del worker debe filtrar por %(organization_id)s")
        merged = dict(params or {})
        if "organization_id" in merged and str(merged["organization_id"]) != str(
            self.organization_id
        ):
            raise TenantScopeError("organization_id distinto al del trabajo")
        merged["organization_id"] = self.organization_id
        return merged

    async def execute(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> AsyncCursor[DictRow]:
        return await self._conn.execute(sql, self._params(sql, params))

    async def fetchone(self, sql: str, params: Mapping[str, Any] | None = None) -> DictRow | None:
        cur = await self.execute(sql, params)
        return await cur.fetchone()

    async def fetchall(self, sql: str, params: Mapping[str, Any] | None = None) -> list[DictRow]:
        cur = await self.execute(sql, params)
        return await cur.fetchall()


class TenantDB:
    def __init__(self, pool: AsyncConnectionPool[AsyncConnection[DictRow]]) -> None:
        self._pool = pool

    @classmethod
    def create_pool(
        cls, database_url: str, max_size: int = 5
    ) -> AsyncConnectionPool[AsyncConnection[DictRow]]:
        return AsyncConnectionPool(
            database_url,
            min_size=1,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    @asynccontextmanager
    async def scoped(self, organization_id: UUID) -> AsyncIterator[TenantConnection]:
        """Conexión en una transacción, limitada a una organización."""
        async with self._pool.connection() as conn, conn.transaction():
            yield TenantConnection(conn, organization_id)
