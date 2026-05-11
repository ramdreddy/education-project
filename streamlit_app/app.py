from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")


def _normalize_supabase_url(url: str) -> str:
    """`supabase-py` expects `https://<ref>.supabase.co`, not the REST base URL."""
    u = (url or "").strip().rstrip("/")
    if u.endswith("/rest/v1"):
        u = u[: -len("/rest/v1")].rstrip("/")
    return u


SUPABASE_URL = _normalize_supabase_url(os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or ""
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def _api_headers() -> dict[str, str]:
    sess = st.session_state.get("supabase_session")
    if not sess or not getattr(sess, "access_token", None):
        return {}
    return {"Authorization": f"Bearer {sess.access_token}"}


def _api_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = f"{BACKEND_URL}{path}"
    headers = {**kwargs.pop("headers", {}), **_api_headers()}
    with httpx.Client(timeout=30.0) as client:
        return client.request(method, url, headers=headers, **kwargs)


def _require_supabase() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Set SUPABASE_URL and SUPABASE_KEY in your `.env` file (loaded via `settings`).")
        st.stop()


def main() -> None:
    _require_supabase()
    st.set_page_config(page_title="School Evaluation", layout="wide")
    st.title("School Evaluation")

    if "supabase" not in st.session_state:
        st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    sb = st.session_state.supabase

    with st.sidebar:
        st.subheader("Sign in")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Log in"):
            res = sb.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.supabase_session = res.session
            st.success("Signed in.")
        if st.button("Log out"):
            sb.auth.sign_out()
            st.session_state.pop("supabase_session", None)
            st.session_state.pop("supabase", None)
            st.rerun()

    sess = st.session_state.get("supabase_session")
    if not sess:
        st.info("Sign in with Supabase Auth to use the API.")
        return

    st.session_state.supabase_session = sess

    tab_t, tab_o = st.tabs(["Teachers", "Observations"])
    with tab_t:
        st.subheader("Teachers (via API)")
        if st.button("Refresh teachers"):
            r = _api_request("GET", "/teachers")
            if r.is_success:
                st.dataframe(r.json())
            else:
                st.error(r.text)
        if st.expander("Create my teacher profile"):
            fn = st.text_input("Full name")
            em = st.text_input("Profile email (optional)")
            dept = st.text_input("Department (optional)")
            if st.button("Create teacher"):
                r = _api_request(
                    "POST",
                    "/teachers",
                    json={"full_name": fn, "email": em or None, "department": dept or None},
                )
                if r.is_success:
                    st.success("Created.")
                    st.json(r.json())
                else:
                    st.error(r.text)

    with tab_o:
        st.subheader("Observations (via API)")
        tid = st.text_input("Filter by teacher_id (optional UUID)")
        if st.button("Refresh observations"):
            path = "/observations" + (f"?teacher_id={tid}" if tid.strip() else "")
            r = _api_request("GET", path)
            if r.is_success:
                st.dataframe(r.json())
            else:
                st.error(r.text)
        if st.expander("New observation"):
            teacher_id = st.text_input("Teacher UUID")
            lesson = st.text_input("Lesson title")
            focus = st.text_input("Focus area")
            strengths = st.text_area("Strengths")
            growth = st.text_area("Growth areas")
            if st.button("Submit observation"):
                r = _api_request(
                    "POST",
                    "/observations",
                    json={
                        "teacher_id": teacher_id,
                        "lesson_title": lesson or None,
                        "focus_area": focus or None,
                        "strengths": strengths or None,
                        "growth_areas": growth or None,
                        "rubric": {},
                    },
                )
                if r.is_success:
                    st.success("Created.")
                    st.json(r.json())
                else:
                    st.error(r.text)


if __name__ == "__main__":
    main()
