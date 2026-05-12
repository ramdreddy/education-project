from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import Client

from app.authz import (
    assert_teacher_belongs_to_user,
    fetch_my_teacher_row,
    get_user_id_or_401,
)
from app.deps import AuthedSupabase, get_authed_supabase, get_supabase
from app.rubric import build_classroom_rubric
from app.routers import performance_reviews as performance_reviews_routes
from app.routers import reports as reports_routes
from app.routers import staff_leave as staff_leave_routes
from app.services.ai_service import (
    observation_record_text,
    suggest_professional_development_goals,
    summarize_observation_for_teacher,
)

app = FastAPI(
    title="School Evaluation API",
    description=(
        "Instructional observation, performance review, professional growth goals, "
        "staff leave & substitute coverage, leadership reporting, and AI-assisted summaries—"
        "all scoped by Supabase RLS."
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(performance_reviews_routes.router)
app.include_router(reports_routes.router)
app.include_router(staff_leave_routes.router)


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
    notes: Optional[str] = None


class ClassroomObservationCreate(BaseModel):
    """Structured instructional walkthrough aligned to core practice domains."""

    teacher_id: UUID
    lesson_title: Optional[str] = None
    focus_area: Optional[str] = None
    student_engagement: int = Field(ge=1, le=5, description="Student engagement (1–5)")
    content_knowledge: int = Field(ge=1, le=5, description="Content knowledge & pedagogy (1–5)")
    classroom_management: int = Field(ge=1, le=5, description="Classroom management & culture (1–5)")
    notes: Optional[str] = None


class ObservationUpdate(BaseModel):
    observed_at: Optional[str] = None
    lesson_title: Optional[str] = None
    focus_area: Optional[str] = None
    rubric: Optional[Dict[str, Any]] = None
    strengths: Optional[str] = None
    growth_areas: Optional[str] = None
    overall_score: Optional[float] = None
    notes: Optional[str] = None


class GoalCreate(BaseModel):
    teacher_id: UUID
    description: str
    target_date: str
    status: str = "active"
    progress_percent: int = Field(default=0, ge=0, le=100)
    progress_note: Optional[str] = None


class GoalUpdate(BaseModel):
    description: Optional[str] = None
    target_date: Optional[str] = None
    status: Optional[str] = None
    progress_percent: Optional[int] = Field(default=None, ge=0, le=100)
    progress_note: Optional[str] = None


class AdminPrivateNoteCreate(BaseModel):
    body: str


class AdminPrivateNoteUpdate(BaseModel):
    body: str


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
        "notes": body.notes,
    }
    row = {k: v for k, v in row.items() if v is not None}
    res = supabase.table("observations").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@app.post("/observations/classroom", status_code=201)
def create_classroom_observation(
    body: ClassroomObservationCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    user = supabase.auth.get_user(jwt=ctx.access_token)
    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid session.")
    rubric, overall = build_classroom_rubric(
        body.student_engagement,
        body.content_knowledge,
        body.classroom_management,
    )
    row = {
        "teacher_id": str(body.teacher_id),
        "observer_user_id": user.user.id,
        "lesson_title": body.lesson_title,
        "focus_area": body.focus_area,
        "rubric": rubric,
        "overall_score": overall,
        "notes": body.notes,
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


@app.post("/observations/{observation_id}/ai-summary")
def ai_summarize_observation(
    observation_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    """Summarize observation narrative into three high-impact bullets (LLM or preview mode)."""
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = (
        supabase.table("observations")
        .select("*")
        .eq("id", str(observation_id))
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Observation not found or not permitted.")
    row = rows[0]
    full_text = observation_record_text(row)
    if len(full_text.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Add more observation notes (or strengths/growth areas) before generating a summary.",
        )
    bullets, source = summarize_observation_for_teacher(full_text)
    if not bullets:
        raise HTTPException(status_code=400, detail="Could not produce a summary from the provided text.")
    return {"bullets": bullets, "source": source}


@app.post("/goals/ai-recommendations")
def ai_goal_recommendations(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Dict[str, Any]:
    """Suggest two professional development goals from this educator's observation history."""
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    me = fetch_my_teacher_row(supabase, uid)
    if not me:
        raise HTTPException(
            status_code=404,
            detail="Create your educator profile before requesting AI-assisted goal ideas.",
        )
    tid = me["id"]
    res = (
        supabase.table("observations")
        .select("*")
        .eq("teacher_id", tid)
        .order("observed_at", desc=True)
        .limit(25)
        .execute()
    )
    observations = res.data or []
    suggestions, source = suggest_professional_development_goals(observations)
    return {"suggestions": suggestions, "source": source}


# --- Current educator profile ---


@app.get("/me/teacher")
def get_my_teacher(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    row = fetch_my_teacher_row(supabase, uid)
    if not row:
        raise HTTPException(status_code=404, detail="No educator profile found for this account.")
    return row


# --- Professional development goals ---

_GOAL_STATUSES = frozenset({"active", "completed", "paused"})


@app.get("/goals")
def list_goals(
    teacher_id: Optional[UUID] = Query(default=None),
    ctx: AuthedSupabase = Depends(get_authed_supabase),
) -> List[Dict[str, Any]]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    tid: Optional[str]
    if teacher_id is not None:
        assert_teacher_belongs_to_user(supabase, str(teacher_id), uid)
        tid = str(teacher_id)
    else:
        me = fetch_my_teacher_row(supabase, uid)
        if not me:
            return []
        tid = me["id"]
    res = (
        supabase.table("goals")
        .select("*")
        .eq("teacher_id", tid)
        .order("target_date", desc=False)
        .execute()
    )
    return res.data or []


@app.post("/goals", status_code=201)
def create_goal(body: GoalCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    if body.status not in _GOAL_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid goal status.")
    assert_teacher_belongs_to_user(supabase, str(body.teacher_id), uid)
    row = {
        "teacher_id": str(body.teacher_id),
        "description": body.description,
        "target_date": body.target_date,
        "status": body.status,
        "progress_percent": body.progress_percent,
        "progress_note": body.progress_note,
    }
    row = {k: v for k, v in row.items() if v is not None}
    res = supabase.table("goals").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@app.patch("/goals/{goal_id}")
def update_goal(
    goal_id: UUID, body: GoalUpdate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "status" in patch and patch["status"] not in _GOAL_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid goal status.")
    if "progress_percent" in patch and patch["progress_percent"] is not None:
        if not 0 <= int(patch["progress_percent"]) <= 100:
            raise HTTPException(status_code=400, detail="progress_percent must be between 0 and 100.")
    res = supabase.table("goals").update(patch).eq("id", str(goal_id)).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Goal not found or not permitted.")
    return data[0]


@app.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)) -> None:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("goals").delete().eq("id", str(goal_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Goal not found or not permitted.")


# --- Instructional leadership private notes ---


@app.get("/admin/private-notes")
def list_admin_private_notes(
    ctx: AuthedSupabase = Depends(get_authed_supabase),
) -> List[Dict[str, Any]]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    res = (
        supabase.table("admin_private_notes")
        .select("*")
        .eq("admin_user_id", uid)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@app.post("/admin/private-notes", status_code=201)
def create_admin_private_note(
    body: AdminPrivateNoteCreate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    row = {"admin_user_id": uid, "body": body.body}
    res = supabase.table("admin_private_notes").insert(row).execute()
    data = res.data or []
    if not data:
        raise HTTPException(status_code=400, detail="Insert failed.")
    return data[0]


@app.patch("/admin/private-notes/{note_id}")
def update_admin_private_note(
    note_id: UUID, body: AdminPrivateNoteUpdate, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> Dict[str, Any]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = (
        supabase.table("admin_private_notes")
        .update({"body": body.body})
        .eq("id", str(note_id))
        .execute()
    )
    data = res.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Note not found or not permitted.")
    return data[0]


@app.delete("/admin/private-notes/{note_id}", status_code=204)
def delete_admin_private_note(
    note_id: UUID, ctx: AuthedSupabase = Depends(get_authed_supabase)
) -> None:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("admin_private_notes").delete().eq("id", str(note_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Note not found or not permitted.")


# --- Instructional analytics ---


@app.get("/analytics/instructional-observation-summary")
def instructional_observation_summary(
    ctx: AuthedSupabase = Depends(get_authed_supabase),
) -> List[Dict[str, Any]]:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.rpc("instructional_observation_summary", {}).execute()
    return res.data or []
