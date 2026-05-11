"""Instructional effectiveness summary for leadership review."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from http_api import api_request
from ui_ai import render_ai_markdown_briefing


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

    rows_raw = st.session_state.get("_summary_cache")
    rows: Optional[List[Dict[str, Any]]] = rows_raw if isinstance(rows_raw, list) else None
    if rows is None:
        st.info("Click **Refresh analytics** to load the summary table.")
        rows = []
    elif not rows:
        st.info("No summary rows returned for your account yet.")
    else:
        df = pd.DataFrame(rows)
        if df.empty:
            st.warning("No summary rows returned.")
        else:
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
                    st.info(
                        "No scored observations yet to chart. Submit a classroom observation with the rubric."
                    )

    st.divider()
    st.subheader("Automated leadership briefing (AI)")
    st.caption(
        "Generates a narrative executive digest from the same summary metrics—useful before "
        "principal meetings or board study sessions."
    )
    if st.button("Generate AI leadership briefing", type="primary", key="briefing_btn"):
        with st.spinner("Composing briefing…"):
            br = api_request("POST", "/reports/ai-leadership-briefing")
        if br.is_success:
            st.session_state["_briefing_last"] = br.json()
        else:
            st.error(br.text)
            st.session_state.pop("_briefing_last", None)

    briefing = st.session_state.get("_briefing_last")
    if briefing and isinstance(briefing, dict) and briefing.get("briefing_markdown"):
        render_ai_markdown_briefing(
            "Executive briefing",
            str(briefing["briefing_markdown"]),
            str(briefing.get("source", "mock")),
        )
