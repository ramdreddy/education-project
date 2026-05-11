"""Helpers for resolving the current Supabase user from a JWT-backed client."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException
from supabase import Client


def get_user_id_or_401(supabase: Client, access_token: str) -> str:
    user_resp = supabase.auth.get_user(jwt=access_token)
    if not user_resp or not user_resp.user:
        raise HTTPException(status_code=401, detail="Invalid session.")
    return user_resp.user.id


def fetch_my_teacher_row(supabase: Client, user_id: str) -> Optional[Dict[str, Any]]:
    res = supabase.table("teachers").select("*").eq("user_id", user_id).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def require_my_teacher(supabase: Client, user_id: str) -> Dict[str, Any]:
    row = fetch_my_teacher_row(supabase, user_id)
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No educator profile found. Complete onboarding under Overview first.",
        )
    return row


def assert_teacher_belongs_to_user(supabase: Client, teacher_id: str, user_id: str) -> None:
    res = supabase.table("teachers").select("id").eq("id", teacher_id).eq("user_id", user_id).limit(1).execute()
    if not (res.data or []):
        raise HTTPException(status_code=403, detail="Not permitted for this educator profile.")
