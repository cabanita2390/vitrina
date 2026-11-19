"""Validación del JWT de Supabase.

Soporta las dos formas en que Supabase firma tokens:
  * Claves asimétricas (ES256/RS256) publicadas en JWKS -> por defecto.
  * Secreto compartido HS256 (legado) -> si SUPABASE_JWT_SECRET está definido.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.types import Options

AUDIENCE = "authenticated"


class InvalidTokenError(Exception):
    """El token no es válido, expiró o no es de un usuario autenticado."""


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    token: str


class SupabaseJWTVerifier:
    def __init__(self, supabase_url: str, jwt_secret: str = "") -> None:
        self._issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self._secret = jwt_secret
        self._jwks = PyJWKClient(f"{self._issuer}/.well-known/jwks.json", cache_keys=True)

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            claims = self._decode(token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        if claims.get("role") != AUDIENCE:
            raise InvalidTokenError("el token no es de un usuario autenticado")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise InvalidTokenError("token sin sub")
        email = claims.get("email")
        return AuthenticatedUser(
            user_id=sub, email=email if isinstance(email, str) else None, token=token
        )

    def _decode(self, token: str) -> dict[str, Any]:
        options: Options = {"require": ["exp", "sub", "aud"]}
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            if not self._secret:
                raise jwt.InvalidTokenError("token HS256 sin SUPABASE_JWT_SECRET configurado")
            return jwt.decode(
                token, self._secret, algorithms=["HS256"], audience=AUDIENCE, options=options
            )
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientError as exc:
            raise jwt.InvalidTokenError(str(exc)) from exc
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=AUDIENCE,
            options=options,
        )
