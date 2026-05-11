"""Roster and educator onboarding."""

from __future__ import annotations

import streamlit as st

from http_api import api_request


def render() -> None:
    st.header("Overview & educator roster")
    st.caption(
        "Maintain your organization directory. Each educator completes a one-time profile "
        "linking their account to instructional records."
    )

    if st.button("Refresh roster", key="refresh_teachers"):
        r = api_request("GET", "/teachers")
        if r.is_success:
            st.session_state["_teachers_cache"] = r.json()
        else:
            st.error(r.text)
    if "_teachers_cache" in st.session_state:
        st.dataframe(st.session_state["_teachers_cache"], use_container_width=True)

    with st.expander("Register my educator profile"):
        fn = st.text_input("Full name", key="onboard_name")
        em = st.text_input("School email (optional)", key="onboard_email")
        dept = st.text_input("Department or grade team (optional)", key="onboard_dept")
        if st.button("Save profile", key="onboard_save"):
            r = api_request(
                "POST",
                "/teachers",
                json={"full_name": fn, "email": em or None, "department": dept or None},
            )
            if r.is_success:
                st.success("Profile saved.")
                st.session_state["_teachers_cache"] = None
            else:
                st.error(r.text)
