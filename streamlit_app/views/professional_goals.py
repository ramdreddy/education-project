"""Professional development goal tracking for the signed-in educator."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import streamlit as st

from http_api import api_request


def _my_teacher() -> Optional[Dict[str, Any]]:
    r = api_request("GET", "/me/teacher")
    if r.status_code == 404:
        return None
    if not r.is_success:
        st.error(r.text)
        return None
    return r.json()


def _invalidate_goals_cache() -> None:
    st.session_state.pop("_goals_cache", None)


def render() -> None:
    st.header("Professional growth goals")
    st.caption(
        "Set outcomes aligned to your instructional priorities. Only you can view and edit "
        "goals tied to your educator profile."
    )

    me = _my_teacher()
    if not me:
        st.info("Complete your educator profile under **Overview & roster** before tracking goals.")
        return

    tid = me["id"]
    st.markdown(f"**Educator:** {me.get('full_name', '')}")

    if st.session_state.get("_goals_teacher_id") != tid:
        st.session_state["_goals_teacher_id"] = tid
        _invalidate_goals_cache()

    if "_goals_cache" not in st.session_state or st.session_state["_goals_cache"] is None:
        gr = api_request("GET", "/goals")
        if gr.is_success:
            st.session_state["_goals_cache"] = gr.json() or []
        else:
            st.error(gr.text)
            st.session_state["_goals_cache"] = []

    with st.form("new_goal"):
        desc = st.text_area("Goal description")
        target = st.date_input("Target date", value=date.today())
        status_new = st.selectbox("Status", ["active", "paused"], index=0)
        submitted = st.form_submit_button("Add goal")
        if submitted:
            if not desc.strip():
                st.warning("Enter a goal description.")
            else:
                r = api_request(
                    "POST",
                    "/goals",
                    json={
                        "teacher_id": tid,
                        "description": desc.strip(),
                        "target_date": target.isoformat(),
                        "status": status_new,
                    },
                )
                if r.is_success:
                    st.success("Goal added.")
                    _invalidate_goals_cache()
                    st.rerun()
                else:
                    st.error(r.text)

    if st.button("Refresh goals", key="goals_refresh"):
        _invalidate_goals_cache()
        st.rerun()

    goals: List[Dict[str, Any]] = list(st.session_state.get("_goals_cache") or [])
    if not goals:
        st.info("No goals on file yet. Add your first goal above.")

    status_options = ["active", "paused", "completed"]
    for g in goals:
        with st.expander(f"{g.get('description', '')[:80]}{'…' if len(g.get('description', '')) > 80 else ''}"):
            st.caption(f"Target date: **{g.get('target_date', '')}** · Current status: **{g.get('status', '')}**")
            cur = g.get("status", "active")
            idx = status_options.index(cur) if cur in status_options else 0
            new_status = st.selectbox(
                "Update status",
                status_options,
                index=idx,
                key=f"st_{g['id']}",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save status", key=f"sv_{g['id']}"):
                    pr = api_request("PATCH", f"/goals/{g['id']}", json={"status": new_status})
                    if pr.is_success:
                        st.success("Updated.")
                        _invalidate_goals_cache()
                        st.rerun()
                    else:
                        st.error(pr.text)
            with c2:
                if st.button("Remove goal", key=f"rm_{g['id']}"):
                    dr = api_request("DELETE", f"/goals/{g['id']}")
                    if dr.is_success:
                        st.success("Removed.")
                        _invalidate_goals_cache()
                        st.rerun()
                    else:
                        st.error(dr.text)
