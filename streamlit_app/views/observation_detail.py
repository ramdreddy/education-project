"""Observation record detail with AI-generated coaching summary."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from http_api import api_request
from ui_ai import render_ai_bullets
from ui_rubric import render_instructional_rubric


def _load_observations() -> List[Dict[str, Any]]:
    r = api_request("GET", "/observations")
    if not r.is_success:
        st.error(r.text)
        return []
    return r.json() or []


def render() -> None:
    st.header("Observation detail")
    st.caption(
        "Review a single observation record and generate a concise AI coaching digest "
        "for the educator—ideal after a formal walkthrough."
    )

    if st.button("Refresh observation list", key="od_refresh_list"):
        st.session_state["_od_obs_list"] = _load_observations()
        st.session_state.pop("_od_selected_detail", None)

    obs_list: List[Dict[str, Any]] = st.session_state.get("_od_obs_list")
    if obs_list is None:
        obs_list = _load_observations()
        st.session_state["_od_obs_list"] = obs_list

    if not obs_list:
        st.info("No observation records available to you yet. Submit one under **Classroom observation**.")
        return

    def _label(o: Dict[str, Any]) -> str:
        oid = str(o.get("id", ""))
        short = oid[:8] + "…" if len(oid) > 8 else oid
        title = o.get("lesson_title") or "Observation"
        when = str(o.get("observed_at", ""))[:10]
        return f"{when} · {title} · {short}"

    by_id = {str(o["id"]): o for o in obs_list if o.get("id")}
    choice = st.selectbox(
        "Select observation record",
        options=list(by_id.keys()),
        format_func=lambda x: _label(by_id[x]),
        key="od_pick",
    )

    if st.button("Load full record", key="od_load_detail"):
        dr = api_request("GET", f"/observations/{choice}")
        if dr.is_success:
            st.session_state["_od_selected_detail"] = dr.json()
        else:
            st.error(dr.text)

    detail = st.session_state.get("_od_selected_detail")
    if not detail or str(detail.get("id")) != choice:
        st.caption("Choose a record and click **Load full record**.")
        return

    st.subheader("Record contents")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Observed at:**", detail.get("observed_at", "—"))
        st.write("**Lesson / segment:**", detail.get("lesson_title") or "—")
        st.write("**Focus:**", detail.get("focus_area") or "—")

    overall = detail.get("overall_score")
    render_instructional_rubric(
        detail.get("rubric"),
        overall_score=float(overall) if overall is not None else None,
        key_prefix=f"od_{choice}",
    )

    st.markdown("**Narrative notes**")
    st.text_area("Notes", value=detail.get("notes") or "", height=120, disabled=True, key="od_notes_ro")
    st.text_area("Strengths", value=detail.get("strengths") or "", height=80, disabled=True, key="od_str_ro")
    st.text_area("Growth areas", value=detail.get("growth_areas") or "", height=80, disabled=True, key="od_gr_ro")

    st.divider()
    st.markdown("##### ✨ AI coaching digest")
    st.caption("Turns lengthy narrative into three high-impact bullets for the teacher.")

    if st.button("Generate AI summary", type="primary", key="od_ai_btn"):
        with st.spinner("Preparing summary…"):
            ar = api_request("POST", f"/observations/{choice}/ai-summary")
        if ar.is_success:
            payload = ar.json()
            st.session_state["_od_ai_last"] = payload
        else:
            st.error(ar.text)
            st.session_state.pop("_od_ai_last", None)

    last = st.session_state.get("_od_ai_last")
    if last and isinstance(last, dict) and last.get("bullets"):
        render_ai_bullets(
            "High-impact takeaways for the educator",
            last["bullets"],
            str(last.get("source", "mock")),
        )
