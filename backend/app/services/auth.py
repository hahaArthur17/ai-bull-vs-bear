from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status


AUTHENTICATION_ERROR = "Invalid or expired access token"


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    access_token: str | None


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


class SupabaseAuthVerifier:
    """Validate a Supabase session against the project's Auth server."""

    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.user_url = f"{supabase_url.rstrip('/')}/auth/v1/user"
        self.anon_key = anon_key
        self.client = client

    def verify(self, access_token: str) -> AuthContext:
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {access_token}",
        }
        try:
            if self.client is not None:
                response = self.client.get(self.user_url, headers=headers)
            else:
                response = httpx.get(self.user_url, headers=headers, timeout=8.0)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc
        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTHENTICATION_ERROR,
                headers={"WWW-Authenticate": "Bearer"},
            )
        payload = response.json()
        user_id = payload.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTHENTICATION_ERROR,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthContext(user_id=user_id, access_token=access_token)
