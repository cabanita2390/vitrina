"""TTSProvider que llama al servicio propio apps/tts (Kokoro-82M)."""

from __future__ import annotations

import httpx

from vitrina_core.providers.base import ProviderError, TTSRequest, TTSResult


class KokoroTTSProvider:
    name = "kokoro"

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self._url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=600)

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        try:
            r = await self._client.post(
                f"{self._url}/synthesize",
                json={"text": request.text, "voice": request.voice, "speed": request.speed},
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"servicio TTS: {exc}") from exc
        return TTSResult(
            audio=r.content,
            media_type=r.headers.get("content-type", "audio/wav"),
            duration_seconds=float(r.headers["X-Audio-Duration"]),
            characters=len(request.text),
        )
