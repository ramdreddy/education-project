"""Structured classroom observation workflow."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from http_api import api_request


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
            st.success("Observation recorded.")
            st.json(r.json())
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
    if "_obs_cache" in st.session_state and st.session_state["_obs_cache"] is not None:
        st.dataframe(st.session_state["_obs_cache"], use_container_width=True)
