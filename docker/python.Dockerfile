# Imagen común para api y worker (uv workspace). Se construye desde la raíz del repo.
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/
RUN mkdir -p packages/core/src/vitrina_core apps/api/src/vitrina_api apps/worker/src/vitrina_worker \
    && uv sync --frozen --no-dev --no-install-workspace

COPY packages/core packages/core
COPY apps/api apps/api
COPY apps/worker apps/worker
RUN uv sync --frozen --no-dev && useradd --create-home --uid 1000 app
USER app

FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "vitrina_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker
CMD ["arq", "vitrina_worker.main.WorkerSettings"]
