"""Fixtures compartidas para tests contra Supabase local (marcador `db`).

Requieren `npx supabase start` y las claves en .env. Se saltan si Supabase no responde.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
import pytest

from vitrina_core.config import Settings


def pytest_asyncio_loop_factories(config: Any, item: Any) -> dict[str, Any]:
    # psycopg async no funciona con el ProactorEventLoop por defecto de Windows.
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}


@dataclass(frozen=True)
class TenantUser:
    user_id: str
    email: str
    token: str
    organization_id: str


@pytest.fixture(scope="session")
def settings() -> Settings:
    s = Settings()
    try:
        httpx.get(f"{s.supabase_url}/auth/v1/health", timeout=3).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Supabase local no está corriendo (npx supabase start)")
    if not s.supabase_service_role_key.get_secret_value():
        pytest.skip("Falta SUPABASE_SERVICE_ROLE_KEY en .env")
    return s


@pytest.fixture(scope="session")
def service_headers(settings: Settings) -> dict[str, str]:
    key = settings.supabase_service_role_key.get_secret_value()
    return {"apikey": key, "Authorization": f"Bearer {key}"}


@pytest.fixture(scope="session")
def anon_key(settings: Settings) -> str:
    return settings.supabase_anon_key.get_secret_value()


@pytest.fixture
def db(settings: Settings) -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        yield conn


def _create_user(settings: Settings, service_headers: dict[str, str], business: str) -> TenantUser:
    email = f"test-{uuid.uuid4().hex[:12]}@vitrina.test"
    password = uuid.uuid4().hex
    base = settings.supabase_url
    r = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers=service_headers,
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"business_name": business},
        },
        timeout=10,
    )
    r.raise_for_status()
    user_id = r.json()["id"]

    r = httpx.post(
        f"{base}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key.get_secret_value()},
        json={"email": email, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json()["access_token"]

    r = httpx.get(
        f"{base}/rest/v1/memberships",
        headers=service_headers,
        params={"user_id": f"eq.{user_id}", "select": "organization_id"},
        timeout=10,
    )
    r.raise_for_status()
    org_id = r.json()[0]["organization_id"]
    return TenantUser(user_id=user_id, email=email, token=token, organization_id=org_id)


@pytest.fixture
def make_user(settings: Settings, service_headers: dict[str, str]) -> Iterator[Any]:
    created: list[TenantUser] = []

    def _make(business: str) -> TenantUser:
        u = _create_user(settings, service_headers, business)
        created.append(u)
        return u

    yield _make

    for u in created:
        httpx.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{u.user_id}",
            headers=service_headers,
            timeout=10,
        )


@pytest.fixture
def rest(settings: Settings, anon_key: str) -> Any:
    """Cliente PostgREST autenticado como un usuario (o anónimo si token=None)."""

    def _client(token: str | None) -> httpx.Client:
        headers = {"apikey": anon_key, "Authorization": f"Bearer {token or anon_key}"}
        return httpx.Client(
            base_url=f"{settings.supabase_url}/rest/v1", headers=headers, timeout=10
        )

    return _client
