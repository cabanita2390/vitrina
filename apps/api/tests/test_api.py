"""Tests unitarios de la API (sin Supabase)."""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from vitrina_api.deps import get_supabase
from vitrina_api.main import create_app
from vitrina_core.config import Settings

SECRET = "test-secret-with-at-least-32-characters!!"


def make_token(**overrides: Any) -> str:
    claims = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "a@vitrina.test",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 300,
        **overrides,
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


class StubSupabase:
    """Doble de prueba de SupabaseRest: devuelve filas fijas y registra llamadas."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    async def select(self, user_token: str, table: str, params: dict[str, str]) -> list[Any]:
        self.calls.append((user_token, table, params))
        if table == "memberships":
            return [
                {
                    "role": "owner",
                    "organizations": {
                        "id": "22222222-2222-2222-2222-222222222222",
                        "name": "Panadería",
                        "kind": "business",
                    },
                }
            ]
        return [{"organization_id": "22222222-2222-2222-2222-222222222222", "balance": 40}]


@pytest.fixture
def stub() -> StubSupabase:
    return StubSupabase()


@pytest.fixture
def client(stub: StubSupabase) -> TestClient:
    app = create_app(Settings(supabase_jwt_secret=SECRET, app_env="test"))
    app.dependency_overrides[get_supabase] = lambda: stub
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_requires_token(client: TestClient) -> None:
    assert client.get("/me/organization").status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "no-es-un-jwt",
        make_token(exp=int(time.time()) - 10),
        make_token(role="anon"),
        make_token(aud="otra"),
        jwt.encode(
            {
                "sub": "x",
                "role": "authenticated",
                "aud": "authenticated",
                "exp": int(time.time()) + 60,
            },
            "otro-secreto-de-32-caracteres-minimo!!",
            algorithm="HS256",
        ),
    ],
    ids=["basura", "expirado", "anon", "audiencia", "firma"],
)
def test_rejects_invalid_tokens(client: TestClient, token: str) -> None:
    r = client.get("/me/organization", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_my_organization_uses_user_token(client: TestClient, stub: StubSupabase) -> None:
    token = make_token()
    r = client.get("/me/organization", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "Panadería",
        "kind": "business",
        "role": "owner",
        "credit_balance": 40,
    }
    # Toda lectura se hace con el JWT del usuario (RLS activa), nunca con service role.
    assert all(call[0] == token for call in stub.calls)
