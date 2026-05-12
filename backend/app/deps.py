from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from app.settings import SUPABASE_KEY, SUPABASE_URL


def require_supabase_config() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(
            status_code=500,
            detail="Missing SUPABASE_URL or SUPABASE_KEY in environment.",
        )


@dataclass(frozen=True)
class AuthedSupabase:
    client: Client
    access_token: str


# Registers Bearer auth in OpenAPI so /docs shows **Authorize** for protected routes.
_http_bearer = HTTPBearer(auto_error=False)


def get_authed_supabase(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_http_bearer),
) -> AuthedSupabase:
    require_supabase_config()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token.")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.postgrest.auth(token)
    return AuthedSupabase(client=client, access_token=token)


def get_supabase(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Client:
    return ctx.client
