from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import Client

from app.deps import AuthedSupabase, get_authed_supabase, get_supabase

app = FastAPI(title="School Evaluation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TeacherCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    department: Optional[str] = None


class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None


class ObservationCreate(BaseModel):
    teacher_id: UUID
    observed_at: Optional[str] = None
    lesson_title: Optional[str] = None
    focus_area: Optional[str] = None
    rubric: Dict[str, Any] = Field(default_factory=dict)
    strengths: Optional[str] = None
    growth_areas: Optional[str] = None
    overall_score: Optional[float] = None


class ObservationUpdate(BaseModel):
    observed_at: Optional[str] = None
    lesson_title: Optional[str] = None
    focus_area: Optional[str] = None
    rubric: Optional[Dict[str, Any]] = None
    strengths: Optional[str] = None
    growth_areas: Optional[str] = None
    overall_score: Optional[float] = None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# --- Teachers ---


@app.get("/teachers")
def list_teachers(supabase: Client = Depends(get_supabase)) -> List[Dict[str, Any]]:
    res = supabase.table("teachers").select("*").order("created_at", desc=True).execute()
    return res.data or []


@app.get("/teachers/{teacher_id}")
def get_teacher(teacher_id: UUID, supabase: Client = Depends(get_supabase)) -> Dict[str, Any]:
    res = supabase.table("teachers").select("*").eq("id", str(teacher_id)).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return rows[0]


@app.post("/teachers", status_code=201)
def create_teacher(
    body: TeacherCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    user = supabase.auth.get_user(jwt=ctx.access_token)
    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid session.")
    row = {
        "user_id": user.user.id,
        "full_name": body.full_name,
        "email": body.email,
        "department": body.department,
    }
    res = supabase.table("teachers").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@app.patch("/teachers/{teacher_id}")
def update_teacher(
    teacher_id: UUID, body: TeacherUpdate, supabase: Client = Depends(get_supabase)
) -> Dict[str, Any]:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    res = supabase.table("teachers").update(patch).eq("id", str(teacher_id)).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Teacher not found or not permitted.")
    return data[0]


@app.delete("/teachers/{teacher_id}", status_code=204)
def delete_teacher(teacher_id: UUID, supabase: Client = Depends(get_supabase)) -> None:
    res = supabase.table("teachers").delete().eq("id", str(teacher_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Teacher not found or not permitted.")


# --- Observations ---


@app.get("/observations")
def list_observations(
    teacher_id: Optional[UUID] = Query(default=None),
    supabase: Client = Depends(get_supabase),
) -> List[Dict[str, Any]]:
    q = supabase.table("observations").select("*").order("observed_at", desc=True)
    if teacher_id is not None:
        q = q.eq("teacher_id", str(teacher_id))
    res = q.execute()
    return res.data or []


@app.get("/observations/{observation_id}")
def get_observation(observation_id: UUID, supabase: Client = Depends(get_supabase)) -> Dict[str, Any]:
    res = supabase.table("observations").select("*").eq("id", str(observation_id)).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Observation not found.")
    return rows[0]


@app.post("/observations", status_code=201)
def create_observation(
    body: ObservationCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    user = supabase.auth.get_user(jwt=ctx.access_token)
    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid session.")
    row = {
        "teacher_id": str(body.teacher_id),
        "observer_user_id": user.user.id,
        "observed_at": body.observed_at,
        "lesson_title": body.lesson_title,
        "focus_area": body.focus_area,
        "rubric": body.rubric,
        "strengths": body.strengths,
        "growth_areas": body.growth_areas,
        "overall_score": body.overall_score,
    }
    row = {k: v for k, v in row.items() if v is not None}
    res = supabase.table("observations").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@app.patch("/observations/{observation_id}")
def update_observation(
    observation_id: UUID, body: ObservationUpdate, supabase: Client = Depends(get_supabase)
) -> Dict[str, Any]:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    res = (
        supabase.table("observations")
        .update(patch)
        .eq("id", str(observation_id))
        .execute()
    )
    data = res.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Observation not found or not permitted.")
    return data[0]


@app.delete("/observations/{observation_id}", status_code=204)
def delete_observation(observation_id: UUID, supabase: Client = Depends(get_supabase)) -> None:
    res = supabase.table("observations").delete().eq("id", str(observation_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Observation not found or not permitted.")
