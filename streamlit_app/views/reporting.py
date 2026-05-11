"""CSV reporting and data extracts for leadership workflows."""

from __future__ import annotations

import streamlit as st

from http_api import api_request


def _download(label: str, path: str, filename: str, key: str) -> None:
    r = api_request("GET", path)
    if r.is_success:
        st.download_button(
            label,
            data=r.text,
            file_name=filename,
            mime="text/csv; charset=utf-8",
            key=key,
            use_container_width=True,
        )
    else:
        st.caption(f"{label}: _unavailable ({r.status_code})_")


def render() -> None:
    st.header("Reports & exports")
    st.caption(
        "Each file reflects **your current visibility** in Supabase (observers export their walkthroughs; "
        "educators export goals tied to their profile, etc.)."
    )

    st.subheader("Structured data extracts (CSV)")
    c1, c2 = st.columns(2)
    with c1:
        _download(
            "Download observation records",
            "/reports/observations.csv",
            "observation_records.csv",
            "dl_obs",
        )
        _download(
            "Download instructional summary",
            "/reports/instructional-summary.csv",
            "instructional_observation_summary.csv",
            "dl_sum",
        )
    with c2:
        _download(
            "Download educator roster",
            "/reports/teachers.csv",
            "educators_roster.csv",
            "dl_teach",
        )
        _download(
            "Download performance review packets",
            "/reports/performance-reviews.csv",
            "performance_reviews.csv",
            "dl_pr",
        )

    st.subheader("Professional growth goals export")
    _download(
        "Download my professional growth goals",
        "/reports/goals.csv",
        "professional_growth_goals.csv",
        "dl_goals",
    )

    st.divider()
    st.subheader("Workflow automation (lightweight)")
    st.caption(
        "These CSVs can be scheduled through your district’s automation layer (e.g., nightly SFTP jobs) "
        "by calling the same authenticated API endpoints from a secure worker using a service account."
    )
