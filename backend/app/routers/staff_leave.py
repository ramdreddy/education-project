"""Leave requests, approvals, and substitute coverage (RLS-scoped)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from app.authz import assert_teacher_belongs_to_user, get_user_id_or_401, is_platform_admin
from app.deps import AuthedSupabase, get_authed_supabase

router = APIRouter(prefix="/staff", tags=["Leave & substitutes"])

_REQUEST_TYPES = frozenset(
    {"vacation", "sick", "personal", "professional", "family", "other"}
)
_LEAVE_STATUSES = frozenset({"pending", "approved", "denied", "cancelled"})
_SUB_STATUSES = frozenset({"draft", "confirmed", "in_place", "completed"})


def _is_leave_approver(supabase: Any, uid: str) -> bool:
    if is_platform_admin(supabase, uid):
        return True
    res = supabase.table("leave_approvers").select("user_id").eq("user_id", uid).limit(1).execute()
    return bool(res.data)


class LeaveRequestCreate(BaseModel):
    teacher_id: UUID
    request_type: str
    start_date: str
    end_date: str
    is_half_day: bool = False
    reason: Optional[str] = None

    @model_validator(mode="after")
    def _dates(self) -> "LeaveRequestCreate":
        if self.request_type not in _REQUEST_TYPES:
            raise ValueError("Invalid request_type.")
        d0 = date.fromisoformat(self.start_date)
        d1 = date.fromisoformat(self.end_date)
        if d1 < d0:
            raise ValueError("end_date must be on or after start_date.")
        return self


class LeaveRequestUpdate(BaseModel):
    request_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_half_day: Optional[bool] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    review_notes: Optional[str] = None


class SubstitutePlanCreate(BaseModel):
    leave_request_id: UUID
    coverage_date: str
    period_label: Optional[str] = None
    substitute_name: str = Field(..., min_length=1, max_length=200)
    substitute_contact: Optional[str] = None
    handoff_notes: Optional[str] = None
    status: str = "draft"


class SubstitutePlanUpdate(BaseModel):
    coverage_date: Optional[str] = None
    period_label: Optional[str] = None
    substitute_name: Optional[str] = None
    substitute_contact: Optional[str] = None
    handoff_notes: Optional[str] = None
    status: Optional[str] = None


@router.get("/leave-approvers/me")
def am_i_leave_approver(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    return {"is_leave_approver": _is_leave_approver(supabase, uid)}


@router.get("/leave-requests", response_model=List[Dict[str, Any]])
def list_leave_requests(
    status: Optional[str] = Query(default=None),
    teacher_id: Optional[UUID] = Query(default=None),
    ctx: AuthedSupabase = Depends(get_authed_supabase),
) -> List[Dict[str, Any]]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    q = supabase.table("leave_requests").select("*").order("start_date", desc=True)
    if status is not None:
        if status not in _LEAVE_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter.")
        q = q.eq("status", status)
    if teacher_id is not None:
        if not _is_leave_approver(supabase, uid) and not is_platform_admin(supabase, uid):
            assert_teacher_belongs_to_user(supabase, str(teacher_id), uid)
        q = q.eq("teacher_id", str(teacher_id))
    res = q.execute()
    return res.data or []


@router.get("/leave-requests/{request_id}", response_model=Dict[str, Any])
def get_leave_request(
    request_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = (
        supabase.table("leave_requests")
        .select("*")
        .eq("id", str(request_id))
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    return rows[0]


@router.post("/leave-requests", status_code=201, response_model=Dict[str, Any])
def create_leave_request(
    body: LeaveRequestCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    if not is_platform_admin(supabase, uid):
        assert_teacher_belongs_to_user(supabase, str(body.teacher_id), uid)
    row: Dict[str, Any] = {
        "teacher_id": str(body.teacher_id),
        "request_type": body.request_type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "is_half_day": body.is_half_day,
        "reason": body.reason,
        "status": "pending",
    }
    row = {k: v for k, v in row.items() if v is not None}
    res = supabase.table("leave_requests").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@router.patch("/leave-requests/{request_id}", response_model=Dict[str, Any])
def update_leave_request(
    request_id: UUID, body: LeaveRequestUpdate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "request_type" in patch and patch["request_type"] not in _REQUEST_TYPES:
        raise HTTPException(status_code=400, detail="Invalid request_type.")
    if "status" in patch and patch["status"] not in _LEAVE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status.")
    is_approver = _is_leave_approver(supabase, uid)
    if is_approver and "status" in patch and patch["status"] in ("approved", "denied"):
        patch["reviewed_by_user_id"] = uid
        patch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    elif "reviewed_at" in patch:
        patch.pop("reviewed_at", None)

    # Non-approvers cannot set approval fields
    if not is_approver:
        patch.pop("review_notes", None)
        for k in ("reviewed_by_user_id", "reviewed_at"):
            patch.pop(k, None)
        if "status" in patch and patch["status"] not in ("pending", "cancelled"):
            raise HTTPException(
                status_code=403, detail="Only leave approvers may approve or deny requests."
            )

    res = (
        supabase.table("leave_requests")
        .update(patch)
        .eq("id", str(request_id))
        .execute()
    )
    data = res.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Leave request not found or not permitted.")
    return data[0]


@router.delete("/leave-requests/{request_id}", status_code=204)
def delete_leave_request(
    request_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> None:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("leave_requests").delete().eq("id", str(request_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Leave request not found or not permitted.")


@router.get("/substitute-plans", response_model=List[Dict[str, Any]])
def list_substitute_plans(
    leave_request_id: Optional[UUID] = Query(default=None),
    ctx: AuthedSupabase = Depends(get_authed_supabase),
) -> List[Dict[str, Any]]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    q = supabase.table("substitute_plans").select("*").order("coverage_date", desc=False)
    if leave_request_id is not None:
        q = q.eq("leave_request_id", str(leave_request_id))
    res = q.execute()
    return res.data or []


@router.post("/substitute-plans", status_code=201, response_model=Dict[str, Any])
def create_substitute_plan(
    body: SubstitutePlanCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    if body.status not in _SUB_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid substitute plan status.")
    row: Dict[str, Any] = {
        "leave_request_id": str(body.leave_request_id),
        "coverage_date": body.coverage_date,
        "period_label": body.period_label,
        "substitute_name": body.substitute_name,
        "substitute_contact": body.substitute_contact,
        "handoff_notes": body.handoff_notes,
        "status": body.status,
    }
    row = {k: v for k, v in row.items() if v is not None}
    res = supabase.table("substitute_plans").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@router.patch("/substitute-plans/{plan_id}", response_model=Dict[str, Any])
def update_substitute_plan(
    plan_id: UUID, body: SubstitutePlanUpdate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "status" in patch and patch["status"] not in _SUB_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status.")
    res = (
        supabase.table("substitute_plans")
        .update(patch)
        .eq("id", str(plan_id))
        .execute()
    )
    data = res.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Substitute plan not found or not permitted.")
    return data[0]


@router.delete("/substitute-plans/{plan_id}", status_code=204)
def delete_substitute_plan(
    plan_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> None:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("substitute_plans").delete().eq("id", str(plan_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Substitute plan not found or not permitted.")
