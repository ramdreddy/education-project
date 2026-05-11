from __future__ import annotations

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
)


def _require_supabase() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Set SUPABASE_URL and SUPABASE_KEY in your `.env` at the project root.")
        st.stop()


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
        page_title="School Evaluation Platform",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        div[data-testid="stSidebarNav"] { font-size: 0.95rem; }
        .block-container { padding-top: 1.2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "supabase" not in st.session_state:
        st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sb = st.session_state.supabase

    nav = None
    with st.sidebar:
        st.title("Account")
        email = st.text_input("Email", key="auth_email")
        password = st.text_input("Password", type="password", key="auth_pw")
        if st.button("Sign in"):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.supabase_session = res.session
                st.success("Signed in.")
                st.rerun()
            except Exception as e:  # noqa: BLE001 — surface auth errors to the user
                st.error(str(e))
        if st.button("Sign out"):
            sb.auth.sign_out()
            st.session_state.pop("supabase_session", None)
            st.session_state.pop("supabase", None)
            for k in list(st.session_state.keys()):
                if k.startswith("_"):
                    del st.session_state[k]
            st.rerun()

        sess = st.session_state.get("supabase_session")
        if sess:
            st.session_state.supabase_session = sess
            st.markdown("##### Workspace")
            nav = st.radio(
                "Navigate",
                [
                    "Overview & roster",
                    "Classroom observation",
                    "Observation detail",
                    "Instructional performance review",
                    "Professional growth goals",
                    "Instructional effectiveness summary",
                    "Reports & exports",
                ],
                key="main_nav",
                label_visibility="collapsed",
            )
            _render_instructional_leadership_notes()
            st.caption(
                "AI-generated text supports human judgment; it does not replace required "
                "evaluation or employment decisions."
            )

    st.title("School Evaluation Platform")
    st.caption(
        "Evidence-based instructional growth, performance review, and leadership reporting · "
        "Powered by your Supabase project"
    )

    if not st.session_state.get("supabase_session"):
        st.info("Sign in with your school credentials to continue.")
        return

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
    elif nav == "Reports & exports":
        reporting.render()

    st.divider()
    st.caption(
        "Prototype scope: classroom observations, formal performance review packets, "
        "professional growth goals with progress monitoring, leadership notes, CSV reporting, "
        "and optional OpenAI-backed digests when `OPENAI_API_KEY` is configured."
    )


if __name__ == "__main__":
    main()
