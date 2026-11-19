"""LLM con presupuesto y registro de costos.

Todo el código de negocio llama a MeteredLLM, nunca al proveedor directamente.
"""

from __future__ import annotations

from uuid import UUID

from vitrina_core.budget import DailyBudget, UsageCost
from vitrina_core.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderRefusalError,
)


class MeteredLLM:
    def __init__(self, provider: LLMProvider, budget: DailyBudget) -> None:
        self._provider = provider
        self._budget = budget

    async def complete(
        self,
        request: LLMRequest,
        *,
        organization_id: UUID,
        job_id: str | None = None,
        operation: str = "llm_call",
    ) -> LLMResponse:
        reservation = await self._budget.reserve(self._provider.estimate_cost(request))
        try:
            response = await self._provider.complete(request)
        except BaseException:
            await self._budget.release(reservation)
            raise

        await self._budget.settle(
            reservation,
            UsageCost(
                organization_id=organization_id,
                provider=self._provider.name,
                operation=operation,
                usd_cost=response.usd_cost,
                model=response.model,
                job_id=job_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                metadata={"stop_reason": response.stop_reason, **response.raw_usage},
            ),
        )
        if response.stop_reason == "refusal":
            raise ProviderRefusalError("el modelo declinó la solicitud")
        return response
