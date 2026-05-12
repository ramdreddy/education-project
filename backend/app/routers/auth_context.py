"""Signed-in user context for UI (roles, not a substitute for RLS)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.authz import get_user_id_or_401, is_platform_admin
from app.deps import AuthedSupabase, get_authed_supabase

router = APIRouter(tags=["Auth context"])


@router.get("/auth/context")
def auth_context(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    return {
        "user_id": uid,
        "is_platform_admin": is_platform_admin(supabase, uid),
    }
