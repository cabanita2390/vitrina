"""Dependencias de FastAPI."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vitrina_api.auth import AuthenticatedUser, InvalidTokenError, SupabaseJWTVerifier
from vitrina_api.supabase_rest import SupabaseRest

_bearer = HTTPBearer(auto_error=False)


def get_verifier(request: Request) -> SupabaseJWTVerifier:
    verifier: SupabaseJWTVerifier = request.app.state.verifier
    return verifier


def get_supabase(request: Request) -> SupabaseRest:
    rest: SupabaseRest = request.app.state.supabase
    return rest


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[SupabaseJWTVerifier, Depends(get_verifier)],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de acceso",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verifier.verify(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Supabase = Annotated[SupabaseRest, Depends(get_supabase)]
