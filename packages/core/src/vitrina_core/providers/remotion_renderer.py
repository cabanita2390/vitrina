"""Renderer que llama al servicio apps/renderer (Remotion).

Si cambian las condiciones de licencia de Remotion, se reemplaza por otra
implementación de `Renderer` (p. ej., FFmpeg) sin tocar el resto del código.
"""

from __future__ import annotations

import httpx

from vitrina_core.providers.base import ProviderError, RenderRequest, RenderResult


class RemotionRenderer:
    name = "remotion"

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self._url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=900)

    async def render(self, request: RenderRequest) -> RenderResult:
        try:
            r = await self._client.post(
                f"{self._url}/render",
                json={
                    "composition": request.composition,
                    "props": request.props,
                    "outputName": request.output_key,
                },
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"renderer: {exc}") from exc
        data = r.json()
        return RenderResult(
            location=f"{self._url}{data['location']}",
            duration_seconds=float(data["durationSeconds"]),
            render_seconds=float(data["renderSeconds"]),
            size_bytes=int(data["sizeBytes"]),
        )
