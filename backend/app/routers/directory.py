"""Staff-wide educator directory for scheduling (minimal fields)."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.authz import get_user_id_or_401
from app.deps import AuthedSupabase, get_authed_supabase

router = APIRouter(prefix="/directory", tags=["Directory"])


@router.get("/educators", response_model=List[Dict[str, Any]])
def staff_educator_directory(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> List[Dict[str, Any]]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.rpc("staff_educator_directory", {}).execute()
    return res.data or []
