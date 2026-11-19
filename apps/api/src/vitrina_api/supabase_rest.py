"""Cliente mínimo de PostgREST que actúa COMO EL USUARIO (su JWT).

La API lee datos de negocio con el token del usuario para que la RLS de la base
aplique también aquí (defensa en profundidad). El service role queda reservado
para el worker y operaciones del sistema.
"""

from __future__ import annotations

from typing import Any

import httpx


class SupabaseRest:
    def __init__(self, supabase_url: str, anon_key: str, client: httpx.AsyncClient) -> None:
        self._base = f"{supabase_url.rstrip('/')}/rest/v1"
        self._anon_key = anon_key
        self._client = client

    async def select(
        self, user_token: str, table: str, params: dict[str, str]
    ) -> list[dict[str, Any]]:
        r = await self._client.get(
            f"{self._base}/{table}",
            params=params,
            headers={"apikey": self._anon_key, "Authorization": f"Bearer {user_token}"},
        )
        r.raise_for_status()
        data: list[dict[str, Any]] = r.json()
        return data
