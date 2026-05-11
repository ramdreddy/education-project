"""CSV exports and AI-assisted leadership reporting."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.authz import fetch_my_teacher_row, get_user_id_or_401
from app.csv_export import dicts_to_csv
from app.deps import AuthedSupabase, get_authed_supabase
from app.services.ai_service import generate_leadership_briefing

router = APIRouter(prefix="/reports", tags=["Reporting"])


def _csv_response(filename: str, content: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/observations.csv")
def export_observations_csv(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> StreamingResponse:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("observations").select("*").order("observed_at", desc=True).execute()
    rows: List[Dict[str, Any]] = res.data or []
    return _csv_response("observations.csv", dicts_to_csv(rows))


@router.get("/teachers.csv")
def export_teachers_csv(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> StreamingResponse:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("teachers").select("*").order("created_at", desc=True).execute()
    rows = res.data or []
    return _csv_response("educators_roster.csv", dicts_to_csv(rows))


@router.get("/instructional-summary.csv")
def export_instructional_summary_csv(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> StreamingResponse:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.rpc("instructional_observation_summary", {}).execute()
    rows = res.data or []
    return _csv_response("instructional_observation_summary.csv", dicts_to_csv(rows))


@router.get("/goals.csv")
def export_goals_csv(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> StreamingResponse:
    supabase = ctx.client
    uid = get_user_id_or_401(supabase, ctx.access_token)
    me = fetch_my_teacher_row(supabase, uid)
    if not me:
        raise HTTPException(
            status_code=404,
            detail="Create an educator profile before exporting professional growth goals.",
        )
    res = (
        supabase.table("goals")
        .select("*")
        .eq("teacher_id", me["id"])
        .order("target_date", desc=False)
        .execute()
    )
    rows = res.data or []
    return _csv_response("professional_growth_goals.csv", dicts_to_csv(rows))


@router.get("/performance-reviews.csv")
def export_performance_reviews_csv(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> StreamingResponse:
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.table("performance_reviews").select("*").order("created_at", desc=True).execute()
    rows = res.data or []
    return _csv_response("performance_reviews.csv", dicts_to_csv(rows))


@router.post("/ai-leadership-briefing")
def ai_leadership_briefing(ctx: AuthedSupabase = Depends(get_authed_supabase)) -> Dict[str, Any]:
    """Automated narrative briefing from observation summary metrics (LLM or preview)."""
    supabase = ctx.client
    get_user_id_or_401(supabase, ctx.access_token)
    res = supabase.rpc("instructional_observation_summary", {}).execute()
    rows: List[Dict[str, Any]] = res.data or []
    markdown, source = generate_leadership_briefing(rows)
    return {"briefing_markdown": markdown, "source": source}
