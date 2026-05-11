"""Formal instructional performance review workflow (reviewer-authored packets)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.authz import get_user_id_or_401
from app.deps import AuthedSupabase, get_authed_supabase

router = APIRouter(prefix="/performance-reviews", tags=["Performance reviews"])

_STATUSES = frozenset({"draft", "in_progress", "completed"})


class PerformanceReviewCreate(BaseModel):
    teacher_id: UUID
    review_period: str = Field(..., min_length=2, max_length=240)
    status: str = "draft"
    summary_notes: Optional[str] = None
    strengths_summary: Optional[str] = None
    growth_priorities: Optional[str] = None
    overall_performance_level: Optional[str] = None


class PerformanceReviewUpdate(BaseModel):
    review_period: Optional[str] = None
    status: Optional[str] = None
    summary_notes: Optional[str] = None
    strengths_summary: Optional[str] = None
    growth_priorities: Optional[str] = None
    overall_performance_level: Optional[str] = None
    submitted_at: Optional[str] = None


@router.get("", response_model=List[Dict[str, Any]])
def list_performance_reviews(
    teacher_id: Optional[UUID] = Query(default=None),
    ctx: AuthedSupabase = Depends(get_authed_supabase),
) -> List[Dict[str, Any]]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    q = supabase.table("performance_reviews").select("*").order("created_at", desc=True)
    if teacher_id is not None:
        q = q.eq("teacher_id", str(teacher_id))
    res = q.execute()
    return res.data or []


@router.get("/{review_id}", response_model=Dict[str, Any])
def get_performance_review(
    review_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = (
        supabase.table("performance_reviews")
        .select("*")
        .eq("id", str(review_id))
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Performance review not found.")
    return rows[0]


@router.post("", status_code=201, response_model=Dict[str, Any])
def create_performance_review(
    body: PerformanceReviewCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    if body.status not in _STATUSES:
        raise HTTPException(status_code=400, detail="Invalid review status.")
    row: Dict[str, Any] = {
        "teacher_id": str(body.teacher_id),
        "reviewer_user_id": uid,
        "review_period": body.review_period,
        "status": body.status,
        "summary_notes": body.summary_notes,
        "strengths_summary": body.strengths_summary,
        "growth_priorities": body.growth_priorities,
        "overall_performance_level": body.overall_performance_level,
    }
    row = {k: v for k, v in row.items() if v is not None}
    res = supabase.table("performance_reviews").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@router.patch("/{review_id}", response_model=Dict[str, Any])
def update_performance_review(
    review_id: UUID, body: PerformanceReviewUpdate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "status" in patch and patch["status"] not in _STATUSES:
        raise HTTPException(status_code=400, detail="Invalid review status.")
    if patch.get("status") == "completed" and "submitted_at" not in patch:
        patch["submitted_at"] = datetime.now(timezone.utc).isoformat()
    res = (
        supabase.table("performance_reviews")
        .update(patch)
        .eq("id", str(review_id))
        .execute()
    )
    data = res.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Performance review not found or not permitted.")
    return data[0]


@router.delete("/{review_id}", status_code=204)
def delete_performance_review(
    review_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> None:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("performance_reviews").delete().eq("id", str(review_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Performance review not found or not permitted.")
