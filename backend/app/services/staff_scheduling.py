"""School-day leave caps and PTO day calculations."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional, Set

from fastapi import HTTPException

MAX_CONCURRENT_ABSENCES_PER_SCHOOL_PER_DAY = 3

# Leave types that consume PTO balance when approved (sick/professional/other do not by default)
PTO_DEBITING_LEAVE_TYPES = frozenset({"vacation", "personal", "family"})


def iter_dates_inclusive(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d = d + timedelta(days=1)


def pto_days_for_leave(start: date, end: date, is_half_day: bool, request_type: str) -> float:
    if request_type not in PTO_DEBITING_LEAVE_TYPES:
        return 0.0
    if is_half_day and start == end:
        return 0.5
    return float((end - start).days + 1)


def _leave_overlaps_day(row: Dict[str, Any], day: date) -> bool:
    sd = date.fromisoformat(str(row["start_date"])[:10])
    ed = date.fromisoformat(str(row["end_date"])[:10])
    return sd <= day <= ed


def _teacher_school_map(supabase: Any) -> Dict[str, Optional[str]]:
    res = supabase.table("teachers").select("id, school_id").execute()
    out: Dict[str, Optional[str]] = {}
    for t in res.data or []:
        out[str(t["id"])] = str(t["school_id"]) if t.get("school_id") else None
    return out


def _all_active_leave_rows(supabase: Any) -> Any:
    return (
        supabase.table("leave_requests")
        .select("id, teacher_id, start_date, end_date, status")
        .in_("status", ["pending", "approved"])
        .execute()
    )


def assert_leave_cap_for_school(
    supabase: Any,
    school_id: Optional[str],
    teacher_id: str,
    start: date,
    end: date,
    exclude_leave_id: Optional[str],
) -> None:
    """At most N distinct educators may be out per campus per calendar day (pending + approved)."""
    if not school_id:
        raise HTTPException(
            status_code=400,
            detail="Educator must be assigned to a campus (school) before requesting leave.",
        )
    school_map = _teacher_school_map(supabase)
    rows = (_all_active_leave_rows(supabase).data) or []
    for day in iter_dates_inclusive(start, end):
        occupied: Set[str] = set()
        for row in rows:
            if exclude_leave_id and str(row.get("id")) == exclude_leave_id:
                continue
            tid = str(row.get("teacher_id", ""))
            if school_map.get(tid) != school_id:
                continue
            if not _leave_overlaps_day(row, day):
                continue
            occupied.add(tid)
        if teacher_id not in occupied and len(occupied) >= MAX_CONCURRENT_ABSENCES_PER_SCHOOL_PER_DAY:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Campus absence cap reached on {day.isoformat()}: at most "
                    f"{MAX_CONCURRENT_ABSENCES_PER_SCHOOL_PER_DAY} educators may be out per day. "
                    "Adjust dates or resolve other pending/approved absences first."
                ),
            )
        if teacher_id in occupied and len(occupied) > MAX_CONCURRENT_ABSENCES_PER_SCHOOL_PER_DAY:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Campus absence cap exceeded on {day.isoformat()} (too many overlapping records). "
                    "Resolve duplicate or overlapping leave entries."
                ),
            )


def build_schedule_matrix(
    supabase: Any,
    school_id: str,
    start: date,
    end: date,
    exclude_leave_id: Optional[str],
) -> Dict[str, Any]:
    """Per-day occupancy for schedule builder UI."""
    school_map = _teacher_school_map(supabase)
    rows = (_all_active_leave_rows(supabase).data) or []
    days_out: Dict[str, Dict[str, Any]] = {}
    for day in iter_dates_inclusive(start, end):
        occupied: Set[str] = set()
        for row in rows:
            if exclude_leave_id and str(row.get("id")) == exclude_leave_id:
                continue
            tid = str(row.get("teacher_id", ""))
            if school_map.get(tid) != school_id:
                continue
            if not _leave_overlaps_day(row, day):
                continue
            occupied.add(tid)
        key = day.isoformat()
        days_out[key] = {
            "date": key,
            "absent_educator_count": len(occupied),
            "at_daily_cap": len(occupied) >= MAX_CONCURRENT_ABSENCES_PER_SCHOOL_PER_DAY,
        }
    return {
        "school_id": school_id,
        "max_concurrent_absences_per_day": MAX_CONCURRENT_ABSENCES_PER_SCHOOL_PER_DAY,
        "days": list(days_out.values()),
    }
