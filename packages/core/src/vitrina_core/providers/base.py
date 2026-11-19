"""Interfaces de proveedores. Cambiar de proveedor = configuración.

Los proveedores son "puros": hablan con el servicio externo y reportan el costo.
El presupuesto y el registro en usage_costs los aplica `metered.MeteredLLM`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol


class ProviderError(Exception):
    """Error genérico de un proveedor externo."""


class ProviderNotConfiguredError(ProviderError):
    """Falta configuración (p. ej., la clave de API)."""


class ProviderRefusalError(ProviderError):
    """El modelo declinó la solicitud (stop_reason = refusal)."""


# ----------------------------------------------------------------------------- LLM


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMRequest:
    messages: list[LLMMessage]
    system: str = ""
    model: str | None = None  # None -> modelo por defecto (barato)
    max_tokens: int = 4000
    effort: Literal["low", "medium", "high"] | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    usd_cost: Decimal
    stop_reason: str | None
    raw_usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str

    def resolve_model(self, request: LLMRequest) -> str: ...

    def estimate_cost(self, request: LLMRequest) -> Decimal:
        """Costo máximo esperado (USD) antes de llamar: se reserva en el presupuesto."""
        ...

    async def complete(self, request: LLMRequest) -> LLMResponse: ...


# ----------------------------------------------------------------------------- TTS


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str = "ef_dora"
    speed: float = 1.0


@dataclass(frozen=True)
class TTSResult:
    audio: bytes
    media_type: str  # audio/wav
    duration_seconds: float
    characters: int
    usd_cost: Decimal = Decimal(0)  # autoalojado -> 0 directo


class TTSProvider(Protocol):
    name: str

    async def synthesize(self, request: TTSRequest) -> TTSResult: ...


# ----------------------------------------------------------------------------- Video IA


@dataclass(frozen=True)
class VideoRequest:
    prompt: str
    duration_seconds: int = 5
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    first_frame_url: str | None = None
    last_frame_url: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class VideoResult:
    url: str
    duration_seconds: float
    usd_cost: Decimal


class VideoProvider(Protocol):
    name: str

    def estimate_cost(self, request: VideoRequest) -> Decimal: ...

    async def generate(self, request: VideoRequest) -> VideoResult: ...


# ----------------------------------------------------------------------------- Render plantilla


@dataclass(frozen=True)
class RenderRequest:
    composition: str
    props: dict[str, Any]
    output_key: str  # nombre/clave de salida (R2 más adelante)


@dataclass(frozen=True)
class RenderResult:
    location: str  # ruta o URL del archivo generado
    duration_seconds: float
    render_seconds: float
    size_bytes: int


class Renderer(Protocol):
    name: str

    async def render(self, request: RenderRequest) -> RenderResult: ...
