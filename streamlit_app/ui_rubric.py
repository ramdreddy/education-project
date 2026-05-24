"""Readable instructional practice rubric display for observation records."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

import streamlit as st

RUBRIC_DIMENSIONS: Tuple[Tuple[str, str], ...] = (
    ("student_engagement", "Student engagement"),
    ("content_knowledge", "Content knowledge & pedagogy"),
    ("classroom_management", "Classroom management & culture"),
)

_SCORE_DESCRIPTORS = {
    1: "Emerging",
    2: "Developing",
    3: "Proficient",
    4: "Strong",
    5: "Exemplary",
}


def score_descriptor(score: int) -> str:
    return _SCORE_DESCRIPTORS.get(score, "—")


def normalize_rubric(rubric: Any) -> Dict[str, Any]:
    """Parse rubric payload from API; ignore metadata keys like rubric_version."""
    raw: Mapping[str, Any] = rubric if isinstance(rubric, Mapping) else {}
    dimensions: Dict[str, int] = {}
    for key, label in RUBRIC_DIMENSIONS:
        val = raw.get(key)
        if val is not None:
            try:
                dimensions[key] = int(val)
            except (TypeError, ValueError):
                continue
    version = raw.get("rubric_version")
    return {
        "dimensions": dimensions,
        "labels": {k: lbl for k, lbl in RUBRIC_DIMENSIONS},
        "rubric_version": str(version) if version else None,
    }


def render_instructional_rubric(
    rubric: Any,
    *,
    overall_score: Optional[float] = None,
    key_prefix: str = "rubric",
) -> None:
    """Render rubric scores as metrics and progress bars (1–5 scale)."""
    parsed = normalize_rubric(rubric)
    dimensions = parsed["dimensions"]
    labels: Dict[str, str] = parsed["labels"]

    if not dimensions:
        st.caption("No rubric scores recorded for this visit.")
        return

    st.markdown("**Instructional practice rubric**")
    st.caption("1 = emerging · 5 = exemplary")

    if overall_score is not None:
        st.metric("Holistic score", f"{float(overall_score):.2f} / 5")

    cols = st.columns(len(RUBRIC_DIMENSIONS))
    for col, (key, _label) in zip(cols, RUBRIC_DIMENSIONS):
        score = dimensions.get(key)
        with col:
            if score is None:
                st.metric(labels[key], "—")
            else:
                st.metric(labels[key], f"{score} / 5")
                st.progress(max(0.0, min(1.0, score / 5.0)), text=score_descriptor(score))

    version = parsed.get("rubric_version")
    if version:
        st.caption(f"Rubric version: `{version}`")


def rubric_summary_line(rubric: Any, overall_score: Optional[float] = None) -> str:
    """One-line summary for expander titles and tables."""
    parsed = normalize_rubric(rubric)
    parts: List[str] = []
    for key, label in RUBRIC_DIMENSIONS:
        score = parsed["dimensions"].get(key)
        if score is not None:
            short = label.split(" & ")[0] if " & " in label else label
            parts.append(f"{short}: {score}")
    if overall_score is not None:
        parts.append(f"Holistic: {float(overall_score):.2f}")
    return " · ".join(parts) if parts else "No rubric scores"
