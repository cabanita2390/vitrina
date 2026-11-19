"""Aislamiento multi-tenant vía API contra Supabase local real (marcador `db`)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vitrina_api.main import create_app

# Las fixtures settings y make_user vienen del conftest.py de la raíz.
pytestmark = pytest.mark.db


@pytest.fixture
def api(settings: Any) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


def test_user_sees_only_own_org_via_api(api: TestClient, make_user: Any) -> None:
    a = make_user("Panadería A")
    b = make_user("Ferretería B")
    auth_a = {"Authorization": f"Bearer {a.token}"}

    me = api.get("/me/organization", headers=auth_a)
    assert me.status_code == 200
    assert me.json()["id"] == a.organization_id
    assert me.json()["role"] == "owner"

    assert api.get(f"/organizations/{a.organization_id}", headers=auth_a).status_code == 200
    assert api.get(f"/organizations/{b.organization_id}", headers=auth_a).status_code == 404
