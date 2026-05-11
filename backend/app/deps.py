from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException
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


def get_authed_supabase(authorization: Optional[str] = Header(default=None)) -> AuthedSupabase:
    require_supabase_config()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token.")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.postgrest.auth(token)
    return AuthedSupabase(client=client, access_token=token)


def get_supabase(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Client:
    return ctx.client
