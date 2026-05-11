"""HTTP calls to the FastAPI backend (all data access goes through the API)."""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from config_env import BACKEND_URL


def _auth_headers() -> dict[str, str]:
    sess = st.session_state.get("supabase_session")
    if not sess or not getattr(sess, "access_token", None):
        return {}
    return {"Authorization": f"Bearer {sess.access_token}"}


def api_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = f"{BACKEND_URL}{path}"
    headers = {**kwargs.pop("headers", {}), **_auth_headers()}
    with httpx.Client(timeout=60.0) as client:
        return client.request(method, url, headers=headers, **kwargs)
