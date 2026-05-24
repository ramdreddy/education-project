"""Structured classroom observation workflow."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from http_api import api_request
from ui_rubric import render_instructional_rubric, rubric_summary_line


def _load_teachers() -> List[Dict[str, Any]]:
    r = api_request("GET", "/directory/educators")
    if not r.is_success:
        st.error(r.text)
        return []
    return r.json() or []


def render() -> None:
    st.header("Classroom observation")
    st.caption(
        "Document an evidence-based walkthrough using the instructional practice rubric. "
        "Scores use a 1–5 scale aligned to your professional growth framework."
    )

    teachers = _load_teachers()
    if not teachers:
        st.warning("No educators in the roster yet, or you may not have access to view them.")
        return

    labels = {str(t["id"]): f'{t.get("full_name", "—")} ({str(t["id"])[:8]}…)' for t in teachers}
    choice = st.selectbox(
        "Educator observed",
        options=list(labels.keys()),
        format_func=lambda x: labels[x],
    )

    col1, col2 = st.columns(2)
    with col1:
        lesson = st.text_input("Lesson or learning segment", key="obs_lesson")
        focus = st.text_input("Observation focus", key="obs_focus")
    with col2:
        pass

    st.subheader("Instructional practice rubric (1 = emerging, 5 = exemplary)")
    c1, c2, c3 = st.columns(3)
    with c1:
        se = st.slider("Student engagement", 1, 5, 3, key="rubric_se")
    with c2:
        ck = st.slider("Content knowledge & pedagogy", 1, 5, 3, key="rubric_ck")
    with c3:
        cm = st.slider("Classroom management & culture", 1, 5, 3, key="rubric_cm")

    notes = st.text_area(
        "Observation notes",
        height=160,
        placeholder="Evidence, dialogue highlights, and next steps for professional learning…",
        key="obs_notes",
    )

    if st.button("Submit observation record", type="primary", key="obs_submit"):
        payload = {
            "teacher_id": choice,
            "lesson_title": lesson or None,
            "focus_area": focus or None,
            "student_engagement": int(se),
            "content_knowledge": int(ck),
            "classroom_management": int(cm),
            "notes": notes or None,
        }
        r = api_request("POST", "/observations/classroom", json=payload)
        if r.is_success:
            saved = r.json()
            st.success("Observation recorded.")
            render_instructional_rubric(
                saved.get("rubric"),
                overall_score=(
                    float(saved["overall_score"])
                    if saved.get("overall_score") is not None
                    else None
                ),
                key_prefix="obs_saved",
            )
            st.session_state.pop("_obs_cache", None)
        else:
            st.error(r.text)

    st.divider()
    st.subheader("Recent observation records")
    tid_filter = st.text_input("Filter by educator ID (optional)", key="obs_list_tid")
    if st.button("Refresh list", key="obs_refresh"):
        path = "/observations" + (f"?teacher_id={tid_filter.strip()}" if tid_filter.strip() else "")
        lr = api_request("GET", path)
        if lr.is_success:
            st.session_state["_obs_cache"] = lr.json()
        else:
            st.error(lr.text)
    cached = st.session_state.get("_obs_cache")
    if cached is not None:
        if not cached:
            st.info("No observation records in this view yet.")
        else:
            for o in cached:
                oid = str(o.get("id", ""))
                when = str(o.get("observed_at", ""))[:16] or "—"
                lesson = o.get("lesson_title") or "Observation"
                overall = o.get("overall_score")
                rubric_line = rubric_summary_line(o.get("rubric"), overall)
                title = f"{when} · {lesson} · {rubric_line}"
                with st.expander(title, expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**Educator ID:**", str(o.get("teacher_id", "—"))[:8] + "…")
                        st.write("**Focus:**", o.get("focus_area") or "—")
                    render_instructional_rubric(
                        o.get("rubric"),
                        overall_score=float(overall) if overall is not None else None,
                        key_prefix=f"obs_list_{oid}",
                    )
                    if o.get("notes"):
                        st.markdown("**Observation notes**")
                        st.write(o.get("notes"))
                    if o.get("strengths"):
                        st.markdown("**Strengths**")
                        st.write(o.get("strengths"))
                    if o.get("growth_areas"):
                        st.markdown("**Growth areas**")
                        st.write(o.get("growth_areas"))
