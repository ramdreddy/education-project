"""Formal instructional performance review workflow for administrators and leads."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from http_api import api_request


def _teachers() -> List[Dict[str, Any]]:
    r = api_request("GET", "/teachers")
    if not r.is_success:
        st.error(r.text)
        return []
    return r.json() or []


def _refresh_reviews() -> None:
    r = api_request("GET", "/performance-reviews")
    if r.is_success:
        st.session_state["_pr_list"] = r.json()
    else:
        st.error(r.text)


def render() -> None:
    st.header("Instructional performance review")
    st.caption(
        "Author formal review packets for educators you support. Educators can read reviews "
        "written about them; only the assigned reviewer may edit or remove a packet."
    )

    teachers = _teachers()
    t_lookup: Dict[str, str] = {str(t["id"]): str(t.get("full_name", "—")) for t in teachers}

    if st.button("Refresh review list", key="pr_refresh"):
        _refresh_reviews()

    if "_pr_list" not in st.session_state:
        _refresh_reviews()

    reviews: List[Dict[str, Any]] = list(st.session_state.get("_pr_list") or [])

    st.subheader("Start a new review")
    if not teachers:
        st.warning("No educators in the roster yet.")
    else:
        tmap = {str(t["id"]): f'{t.get("full_name", "—")}' for t in teachers}
        tid = st.selectbox(
            "Educator receiving this review",
            options=list(tmap.keys()),
            format_func=lambda x: tmap[x],
            key="pr_new_teacher",
        )
        period = st.text_input(
            "Review period label",
            placeholder="e.g., Fall 2026 · Mid-cycle",
            key="pr_new_period",
        )
        status_new = st.selectbox("Starting status", ["draft", "in_progress"], index=0, key="pr_new_status")
        if st.button("Create review packet", key="pr_create"):
            if not period or len(period.strip()) < 2:
                st.warning("Enter a meaningful review period label.")
            else:
                r = api_request(
                    "POST",
                    "/performance-reviews",
                    json={
                        "teacher_id": tid,
                        "review_period": period.strip(),
                        "status": status_new,
                    },
                )
                if r.is_success:
                    st.success("Review packet created.")
                    _refresh_reviews()
                    st.rerun()
                else:
                    st.error(r.text)

    st.divider()
    st.subheader("Review packets in your workspace")
    if not reviews:
        st.info("No performance reviews yet. Create one above or adjust roster access.")
        return

    for rev in reviews:
        rid = rev.get("id")
        teacher_name = t_lookup.get(str(rev.get("teacher_id", "")), "Educator")
        title = f"{rev.get('review_period', 'Review')} · {teacher_name} · {str(rid)[:8]}…"
        with st.expander(title):
            st.caption(
                f"Status: **{rev.get('status', '')}** · Submitted: **{rev.get('submitted_at') or '—'}**"
            )
            summary = st.text_area(
                "Executive summary",
                value=rev.get("summary_notes") or "",
                height=100,
                key=f"pr_sum_{rid}",
            )
            strengths = st.text_area(
                "Strengths observed",
                value=rev.get("strengths_summary") or "",
                height=80,
                key=f"pr_str_{rid}",
            )
            growth = st.text_area(
                "Growth priorities",
                value=rev.get("growth_priorities") or "",
                height=80,
                key=f"pr_gr_{rid}",
            )
            level = st.text_input(
                "Overall performance narrative",
                value=rev.get("overall_performance_level") or "",
                key=f"pr_lvl_{rid}",
            )
            st_sel = st.selectbox(
                "Workflow status",
                ["draft", "in_progress", "completed"],
                index=["draft", "in_progress", "completed"].index(rev.get("status", "draft"))
                if rev.get("status") in ("draft", "in_progress", "completed")
                else 0,
                key=f"pr_st_{rid}",
            )
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Save updates", key=f"pr_sv_{rid}"):
                    pr = api_request(
                        "PATCH",
                        f"/performance-reviews/{rid}",
                        json={
                            "summary_notes": summary or None,
                            "strengths_summary": strengths or None,
                            "growth_priorities": growth or None,
                            "overall_performance_level": level or None,
                            "status": st_sel,
                        },
                    )
                    if pr.is_success:
                        st.success("Saved.")
                        _refresh_reviews()
                        st.rerun()
                    else:
                        st.error(pr.text)
            with c2:
                if st.button("Mark completed", key=f"pr_done_{rid}"):
                    pr = api_request(
                        "PATCH",
                        f"/performance-reviews/{rid}",
                        json={"status": "completed"},
                    )
                    if pr.is_success:
                        st.success("Marked completed (timestamp recorded).")
                        _refresh_reviews()
                        st.rerun()
                    else:
                        st.error(pr.text)
            with c3:
                if st.button("Delete packet", key=f"pr_del_{rid}"):
                    dr = api_request("DELETE", f"/performance-reviews/{rid}")
                    if dr.is_success:
                        st.success("Deleted.")
                        _refresh_reviews()
                        st.rerun()
                    else:
                        st.error(dr.text)
