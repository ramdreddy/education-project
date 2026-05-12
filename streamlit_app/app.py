from __future__ import annotations

from typing import Any, Dict

import streamlit as st
from supabase import create_client

from config_env import SUPABASE_KEY, SUPABASE_URL
from http_api import api_request
from views import (
    classroom_observation,
    instructional_summary,
    observation_detail,
    overview,
    performance_review,
    professional_goals,
    reporting,
    staff_leave,
)


def _require_supabase() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Set SUPABASE_URL and SUPABASE_KEY in your `.env` at the project root.")
        st.stop()


def _fetch_dashboard_stats() -> Dict[str, Any]:
    """Aggregate counts visible to the signed-in user (RLS-scoped via API)."""
    stats = {
        "roster": 0,
        "observations": 0,
        "goals": 0,
        "reviews": 0,
        "leave_pending": 0,
        "substitute_open": 0,
    }
    r = api_request("GET", "/directory/educators")
    if r.is_success and isinstance(r.json(), list):
        stats["roster"] = len(r.json())
    r = api_request("GET", "/observations")
    if r.is_success and isinstance(r.json(), list):
        stats["observations"] = len(r.json())
    r = api_request("GET", "/goals")
    if r.is_success and isinstance(r.json(), list):
        stats["goals"] = len(r.json())
    r = api_request("GET", "/performance-reviews")
    if r.is_success and isinstance(r.json(), list):
        stats["reviews"] = len(r.json())
    r = api_request("GET", "/staff/leave-requests?status=pending")
    if r.is_success and isinstance(r.json(), list):
        stats["leave_pending"] = len(r.json())
    r = api_request("GET", "/staff/substitute-plans")
    if r.is_success and isinstance(r.json(), list):
        stats["substitute_open"] = sum(
            1 for x in r.json() if str(x.get("status", "")).lower() != "completed"
        )
    return stats


def _ensure_auth_context() -> None:
    """Load platform admin flag once per session (backend mirrors RLS)."""
    if "is_platform_admin" in st.session_state:
        return
    r = api_request("GET", "/auth/context")
    if r.is_success and isinstance(r.json(), dict):
        st.session_state["is_platform_admin"] = bool(r.json().get("is_platform_admin"))
    else:
        st.session_state["is_platform_admin"] = False


def _workspace_nav_options() -> list[str]:
    staff = [
        "Overview & roster",
        "Classroom observation",
        "Observation detail",
        "Instructional performance review",
        "Professional growth goals",
        "Leave & substitutes",
    ]
    admin_only = [
        "Instructional effectiveness summary",
        "Reports & exports",
    ]
    if st.session_state.get("is_platform_admin"):
        return staff + admin_only
    return staff
    st.markdown(
        """
        <div style="margin-bottom:1rem;padding-bottom:0.75rem;border-bottom:1px solid rgba(148,163,184,0.35);">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="min-width:44px;height:44px;border-radius:12px;background:linear-gradient(145deg,#0f172a,#1d4ed8);
                        color:#f8fafc;display:flex;align-items:center;justify-content:center;
                        font-weight:700;font-size:0.95rem;letter-spacing:0.02em;">SA</div>
            <div>
              <div style="font-size:1.05rem;font-weight:700;color:#0f172a;line-height:1.2;">School Admin Portal</div>
              <div style="font-size:0.78rem;color:#64748b;margin-top:2px;">Instructional effectiveness suite</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_dashboard_strip() -> None:
    """Top-of-page executive strip: positioning copy + key metrics."""
    if st.button("Refresh overview stats", key="dash_stats_refresh"):
        st.session_state.pop("_dash_stats", None)

    if "_dash_stats" not in st.session_state:
        st.session_state["_dash_stats"] = _fetch_dashboard_stats()
    s = st.session_state["_dash_stats"]

    hero_l, hero_r = st.columns([2.1, 1])
    with hero_l:
        st.markdown("### School Evaluation Platform")
        st.caption(
            "Evidence-based instructional growth, performance review, and leadership reporting · "
            "Powered by your Supabase project"
        )
    with hero_r:
        st.markdown("")
        role = "**Platform administrator**" if st.session_state.get("is_platform_admin") else "**Staff**"
        st.caption(f"**Session** · authenticated · {role}")
        st.caption("Use the workspace menu in the sidebar to move between modules.")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric(
            label="Educators on roster",
            value=int(s.get("roster", 0)),
            help="Profiles visible under your current access scope.",
        )
    with m2:
        st.metric(
            label="Observation records",
            value=int(s.get("observations", 0)),
            help="Walkthroughs and visits you may view per policy.",
        )
    with m3:
        st.metric(
            label="Professional growth goals",
            value=int(s.get("goals", 0)),
            help="Goals tied to your educator profile (or empty if no profile yet).",
        )
    with m4:
        st.metric(
            label="Performance review packets",
            value=int(s.get("reviews", 0)),
            help="Formal review packets you authored or can read as subject.",
        )
    with m5:
        st.metric(
            label="Leave requests pending",
            value=int(s.get("leave_pending", 0)),
            help="Awaiting action—visible to request owners and configured approvers.",
        )
    with m6:
        st.metric(
            label="Substitute coverage rows (open)",
            value=int(s.get("substitute_open", 0)),
            help="Substitute plans not yet marked completed in your visibility scope.",
        )

    st.divider()


def _render_instructional_leadership_notes() -> None:
    st.markdown("---")
    st.subheader("Instructional leadership notes")
    st.caption(
        "Confidential reflections visible only to you. Stored in Supabase via the API—"
        "not shared with educators."
    )
    if st.button("Load my notes", key="notes_load"):
        r = api_request("GET", "/admin/private-notes")
        if r.is_success:
            st.session_state["_admin_notes"] = r.json()
        else:
            st.error(r.text)
    for n in st.session_state.get("_admin_notes") or []:
        st.text_area(
            f"Note ({str(n.get('created_at', ''))[:16]})",
            value=n.get("body", ""),
            height=100,
            key=f"note_body_{n['id']}",
            disabled=True,
        )
        if st.button("Delete", key=f"note_del_{n['id']}"):
            dr = api_request("DELETE", f"/admin/private-notes/{n['id']}")
            if dr.is_success:
                st.session_state["_admin_notes"] = None
                st.rerun()
            else:
                st.error(dr.text)

    new_note = st.text_area("New reflection", height=120, key="admin_new_note")
    if st.button("Save note", key="admin_save_note"):
        if not new_note.strip():
            st.warning("Enter text before saving.")
        else:
            r = api_request("POST", "/admin/private-notes", json={"body": new_note.strip()})
            if r.is_success:
                st.success("Saved.")
                st.session_state["_admin_notes"] = None
                st.rerun()
            else:
                st.error(r.text)


def main() -> None:
    _require_supabase()
    st.set_page_config(
        page_title="School Admin Portal",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        div[data-testid="stSidebarNav"] { font-size: 0.95rem; }
        .block-container { padding-top: 1.1rem; }
        div[data-testid="stMetricValue"] { font-size: 1.65rem; font-weight: 600; }
        div[data-testid="stMetricLabel"] { font-size: 0.82rem; text-transform: none; letter-spacing: 0.01em; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "supabase" not in st.session_state:
        st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sb = st.session_state.supabase

    nav = None
    with st.sidebar:
        _render_sidebar_brand()
        st.subheader("Account")
        email = st.text_input("Email", key="auth_email")
        password = st.text_input("Password", type="password", key="auth_pw")
        if st.button("Sign in"):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.supabase_session = res.session
                st.session_state.pop("is_platform_admin", None)
                st.session_state.pop("_nav_role_key", None)
                st.success("Signed in.")
                st.rerun()
            except Exception as e:  # noqa: BLE001 — surface auth errors to the user
                st.error(str(e))
        if st.button("Sign out"):
            sb.auth.sign_out()
            st.session_state.pop("supabase_session", None)
            st.session_state.pop("supabase", None)
            st.session_state.pop("is_platform_admin", None)
            st.session_state.pop("_nav_role_key", None)
            for k in list(st.session_state.keys()):
                if k.startswith("_"):
                    del st.session_state[k]
            st.rerun()

        sess = st.session_state.get("supabase_session")
        if sess:
            st.session_state.supabase_session = sess
            _ensure_auth_context()
            rk = "admin" if st.session_state.get("is_platform_admin") else "staff"
            if st.session_state.get("_nav_role_key") != rk:
                st.session_state.pop("main_nav", None)
                st.session_state["_nav_role_key"] = rk
            st.markdown("##### Workspace")
            nav = st.radio(
                "Navigate",
                _workspace_nav_options(),
                key="main_nav",
                label_visibility="collapsed",
            )
            _render_instructional_leadership_notes()
            st.caption(
                "AI-generated text supports human judgment; it does not replace required "
                "evaluation or employment decisions."
            )

    if not st.session_state.get("supabase_session"):
        intro_l, intro_r = st.columns([1.4, 1])
        with intro_l:
            st.markdown("## School Evaluation Platform")
            st.caption(
                "Sign in to access the **School Admin Portal** workspace—observations, "
                "performance reviews, goals, reporting, and leadership notes."
            )
        with intro_r:
            st.info("Use the **sidebar** to sign in with your school Supabase credentials.")
        return

    _ensure_auth_context()
    _render_dashboard_strip()

    if nav == "Overview & roster":
        overview.render()
    elif nav == "Classroom observation":
        classroom_observation.render()
    elif nav == "Observation detail":
        observation_detail.render()
    elif nav == "Instructional performance review":
        performance_review.render()
    elif nav == "Professional growth goals":
        professional_goals.render()
    elif nav == "Instructional effectiveness summary":
        instructional_summary.render()
    elif nav == "Leave & substitutes":
        staff_leave.render()
    elif nav == "Reports & exports":
        reporting.render()

    st.divider()
    st.caption(
        "Prototype scope: classroom observations, formal performance review packets, "
        "professional growth goals with progress monitoring, leadership notes, CSV reporting, "
        "leave & substitutes, optional OpenAI-backed digests when `OPENAI_API_KEY` is configured, "
        "and `platform_admins` in Supabase for organization-wide visibility."
    )


if __name__ == "__main__":
    main()
