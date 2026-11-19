"""Precios de modelos de Claude (USD por millón de tokens).

Fuente: lista de precios de Anthropic (consultada 2026-11-19). Revisar al cambiar
de modelo. Cache: escritura 1,25x y lectura 0,1x del precio de entrada.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class ModelPrice:
    input_per_m: Decimal
    output_per_m: Decimal
    # Algunos modelos cobran más cuando el prompt supera un umbral.
    long_context_threshold: int | None = None
    long_input_per_m: Decimal | None = None
    long_output_per_m: Decimal | None = None


PRICES: dict[str, ModelPrice] = {
    "claude-haiku-5-5": ModelPrice(
        Decimal("0.10"),
        Decimal("0.50"),
        long_context_threshold=100_000,
        long_input_per_m=Decimal("0.50"),
        long_output_per_m=Decimal("2.50"),
    ),
    "claude-sonnet-5-5": ModelPrice(Decimal("2.00"), Decimal("10.00")),
    "claude-opus-5-5": ModelPrice(Decimal("4.00"), Decimal("20.00")),
}


class UnknownModelPriceError(KeyError):
    pass


def price_for(model: str) -> ModelPrice:
    try:
        return PRICES[model]
    except KeyError as exc:
        raise UnknownModelPriceError(f"sin precio registrado para {model}") from exc


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> Decimal:
    p = price_for(model)
    prompt_tokens = input_tokens + cache_write_tokens + cache_read_tokens
    in_price, out_price = p.input_per_m, p.output_per_m
    if p.long_context_threshold is not None and prompt_tokens > p.long_context_threshold:
        in_price = p.long_input_per_m or in_price
        out_price = p.long_output_per_m or out_price
    total = (
        Decimal(input_tokens) * in_price
        + Decimal(cache_write_tokens) * in_price * Decimal("1.25")
        + Decimal(cache_read_tokens) * in_price * Decimal("0.1")
        + Decimal(output_tokens) * out_price
    ) / MILLION
    return total.quantize(Decimal("0.000001"))
