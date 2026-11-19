"""Organización del usuario autenticado."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from vitrina_api.deps import CurrentUser, Supabase

router = APIRouter(tags=["organizaciones"])


class Organization(BaseModel):
    id: UUID
    name: str
    kind: Literal["business", "institution"]
    role: Literal["owner", "admin", "member"]
    credit_balance: int


async def _load(
    user: CurrentUser, supabase: Supabase, org_filter: dict[str, str]
) -> list[Organization]:
    # La RLS de Supabase limita las filas a las organizaciones del usuario.
    memberships = await supabase.select(
        user.token,
        "memberships",
        {
            "select": "role,organizations(id,name,kind)",
            "user_id": f"eq.{user.user_id}",
            **org_filter,
        },
    )
    if not memberships:
        return []
    org_ids = ",".join(m["organizations"]["id"] for m in memberships)
    balances = await supabase.select(
        user.token,
        "credit_balances",
        {"select": "organization_id,balance", "organization_id": f"in.({org_ids})"},
    )
    by_org = {b["organization_id"]: int(b["balance"]) for b in balances}
    return [
        Organization(
            id=m["organizations"]["id"],
            name=m["organizations"]["name"],
            kind=m["organizations"]["kind"],
            role=m["role"],
            credit_balance=by_org.get(m["organizations"]["id"], 0),
        )
        for m in memberships
    ]


@router.get("/me/organization", response_model=Organization, summary="Mi organización")
async def my_organization(user: CurrentUser, supabase: Supabase) -> Organization:
    """Organización principal del usuario (en v1 cada usuario tiene una)."""
    orgs = await _load(user, supabase, {"order": "created_at.asc"})
    if not orgs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El usuario no tiene organización")
    return orgs[0]


@router.get(
    "/organizations/{organization_id}", response_model=Organization, summary="Organización por id"
)
async def get_organization(
    organization_id: UUID, user: CurrentUser, supabase: Supabase
) -> Organization:
    orgs = await _load(user, supabase, {"organization_id": f"eq.{organization_id}"})
    if not orgs:
        # 404 y no 403: no revelamos si la organización existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organización no encontrada")
    return orgs[0]
