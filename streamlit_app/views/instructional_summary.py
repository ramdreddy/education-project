"""Instructional effectiveness summary for leadership review."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from http_api import api_request


def render() -> None:
    st.header("Instructional effectiveness summary")
    st.caption(
        "Aggregated observation scores respect each user’s visibility in the system "
        "(observers see their walkthroughs; educators see visits about their practice)."
    )

    if st.button("Refresh analytics", key="sum_refresh"):
        r = api_request("GET", "/analytics/instructional-observation-summary")
        if r.is_success:
            st.session_state["_summary_cache"] = r.json()
        else:
            st.error(r.text)

    rows: List[Dict[str, Any]] = st.session_state.get("_summary_cache") or []
    if not rows:
        st.info("Load analytics to view average holistic scores by educator.")
        return

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("No summary rows returned.")
        return

    rename_map = {
        "full_name": "Educator",
        "avg_overall_score": "Average holistic score",
        "observation_count": "Observation count",
    }
    display = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    plot_df = df.copy()
    if "avg_overall_score" in plot_df.columns and "full_name" in plot_df.columns:
        plot_df = plot_df.dropna(subset=["avg_overall_score"])
        if not plot_df.empty:
            st.subheader("Average holistic score by educator")
            chart = plot_df.set_index("full_name")[["avg_overall_score"]].sort_values(
                "avg_overall_score", ascending=True
            )
            st.bar_chart(chart, use_container_width=True)
        else:
            st.info("No scored observations yet to chart. Submit a classroom observation with the rubric.")
