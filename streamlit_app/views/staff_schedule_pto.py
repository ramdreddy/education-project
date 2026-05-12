"""Campus schedule occupancy (daily absence cap) and PTO balances."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import streamlit as st

from http_api import api_request


def _schools() -> List[Dict[str, Any]]:
    r = api_request("GET", "/staff/schools")
    if not r.is_success:
        st.error(r.text)
        return []
    data = r.json()
    return data if isinstance(data, list) else []


def _educators() -> List[Dict[str, Any]]:
    r = api_request("GET", "/directory/educators")
    if not r.is_success or not isinstance(r.json(), list):
        return []
    return r.json()


def _pto_summary(teacher_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = "/staff/pto-summary"
    if teacher_id:
        path = f"/staff/pto-summary?teacher_id={teacher_id}"
    r = api_request("GET", path)
    if not r.is_success:
        st.error(r.text)
        return None
    return r.json()


def _schedule_matrix(school_id: str, start: date, end: date) -> Optional[Dict[str, Any]]:
    qs = f"?school_id={school_id}&start_date={start.isoformat()}&end_date={end.isoformat()}"
    r = api_request("GET", f"/staff/schedule-builder{qs}")
    if not r.is_success:
        st.error(r.text)
        return None
    return r.json()


def render() -> None:
    st.header("Schedule builder & PTO")
    st.caption(
        "See how many educators are already out per day at a campus (pending and approved leave). "
        "At most **three** distinct educators per campus per calendar day may be absent. "
        "PTO balances reflect vacation, personal, and family leave charges when requests are approved."
    )

    schools = _schools()
    if not schools:
        st.warning("No campuses found. Add rows to `schools` and assign educators via `school_id`.")
    else:
        st.subheader("Campus occupancy")
        sid_labels = {str(s["id"]): str(s.get("name", s["id"])) for s in schools}
        default_sid = next(iter(sid_labels))
        pick = st.selectbox(
            "Campus",
            options=list(sid_labels.keys()),
            format_func=lambda k: sid_labels[k],
            key="sched_pto_school",
        )
        today = date.today()
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Range start", value=today, key="sched_pto_sd")
        with c2:
            end = st.date_input(
                "Range end",
                value=min(today + timedelta(days=20), today + timedelta(days=120)),
                key="sched_pto_ed",
            )
        if end < start:
            st.warning("End date must be on or after start date.")
        else:
            if (end - start).days > 120:
                st.warning("Narrow the range to 120 days or fewer.")
            else:
                mat = _schedule_matrix(pick, start, end)
                if mat and isinstance(mat.get("days"), list):
                    max_n = int(mat.get("max_concurrent_absences_per_day", 3))
                    rows = []
                    for d in mat["days"]:
                        rows.append(
                            {
                                "Date": d.get("date"),
                                "Out (count)": d.get("absent_educator_count"),
                                "At daily cap": "Yes" if d.get("at_daily_cap") else "No",
                            }
                        )
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                    at_cap_days = [r["Date"] for r in rows if r["At daily cap"] == "Yes"]
                    if at_cap_days:
                        st.warning(
                            f"**{len(at_cap_days)}** day(s) in this window already have {max_n} educators "
                            "out—additional overlapping absences will be blocked until something changes."
                        )
                    else:
                        st.success(f"No day in this window reaches the {max_n}-person campus cap yet.")

    st.divider()
    st.subheader("PTO balance")
    admin = bool(st.session_state.get("is_platform_admin"))
    teacher_id: Optional[str] = None
    if admin:
        people = _educators()
        if people:
            id_to_label = {
                str(p["id"]): f"{p.get('full_name', '—')} ({p.get('school_name', 'campus')})"
                for p in people
            }
            opts = [""] + list(id_to_label.keys())
            choice = st.selectbox(
                "Educator (leave blank for your own profile)",
                options=opts,
                format_func=lambda x: "— My profile —" if x == "" else id_to_label.get(x, x),
                key="sched_pto_which",
            )
            if choice:
                teacher_id = choice
    summ = _pto_summary(teacher_id)
    if summ:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Allowance (days)", f"{float(summ.get('pto_allowance_days', 0)):.2f}")
        with c2:
            st.metric("Used (days)", f"{float(summ.get('pto_used_days', 0)):.2f}")
        with c3:
            st.metric("Remaining (days)", f"{float(summ.get('pto_remaining_days', 0)):.2f}")
        st.caption(
            f"Profile: **{summ.get('full_name', '—')}** · Campus id: `{summ.get('school_id')}`"
        )
