"""Aplicación FastAPI de Vitrina."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vitrina_api.auth import SupabaseJWTVerifier
from vitrina_api.routers import organizations
from vitrina_api.supabase_rest import SupabaseRest
from vitrina_core.config import Settings, get_settings
from vitrina_core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=10) as client:
            app.state.supabase = SupabaseRest(
                settings.supabase_url, settings.supabase_anon_key.get_secret_value(), client
            )
            yield

    app = FastAPI(
        title="Vitrina API",
        version="0.1.0",
        description="API de Vitrina: contenido con IA para negocios pequeños.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.verifier = SupabaseJWTVerifier(
        settings.supabase_url, settings.supabase_jwt_secret.get_secret_value()
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["sistema"], summary="Estado del servicio")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(organizations.router)
    return app


app = create_app()
