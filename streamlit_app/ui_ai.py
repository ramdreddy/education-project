"""Shared styling for AI-generated instructional content."""

from __future__ import annotations

import html
from typing import Iterable, List

import streamlit as st

_AI_ACCENT = "#5b21b6"
_AI_BG = "#f5f3ff"
_AI_BORDER = "#7c3aed"


def _inject_ai_styles_once() -> None:
    if st.session_state.get("_ai_styles_injected"):
        return
    st.markdown(
        f"""
        <style>
        .ai-panel {{
            border-left: 4px solid {_AI_BORDER};
            background: {_AI_BG};
            padding: 14px 16px;
            border-radius: 0 10px 10px 0;
            margin: 10px 0 14px 0;
        }}
        .ai-panel .ai-badge {{
            display: inline-block;
            font-size: 0.78rem;
            font-weight: 600;
            color: {_AI_ACCENT};
            margin-bottom: 8px;
        }}
        .ai-panel ul {{ margin: 0.35em 0 0 1.1em; }}
        .ai-panel li {{ margin-bottom: 0.35em; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_ai_styles_injected"] = True


def render_ai_bullets(
    title: str,
    bullets: Iterable[str],
    source: str,
) -> None:
    """Sparkle-styled block for observation summaries."""
    _inject_ai_styles_once()
    badge = "Live model" if source == "openai" else "Preview mode (no API key configured)"
    items: List[str] = [html.escape(b) for b in bullets if str(b).strip()]
    lis = "".join(f"<li>{b}</li>" for b in items)
    st.markdown(
        f"""
        <div class="ai-panel">
            <div class="ai-badge">✨ {html.escape(title)} · {html.escape(badge)}</div>
            <ul>{lis}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_suggestions(
    title: str,
    suggestions: Iterable[str],
    source: str,
) -> None:
    """Sparkle-styled block for goal recommendations."""
    _inject_ai_styles_once()
    badge = "Live model" if source == "openai" else "Preview mode (no API key configured)"
    items = [html.escape(s) for s in suggestions if str(s).strip()]
    blocks = "".join(
        f'<p style="margin:10px 0 0 0;line-height:1.45;"><span aria-hidden="true">✨</span> {s}</p>'
        for s in items
    )
    st.markdown(
        f"""
        <div class="ai-panel">
            <div class="ai-badge">{html.escape(title)} · {html.escape(badge)}</div>
            {blocks}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_markdown_briefing(title: str, markdown_body: str, source: str) -> None:
    """Sparkle header + rendered Markdown body for leadership AI briefings."""
    _inject_ai_styles_once()
    badge = "Live model" if source == "openai" else "Preview mode (no API key configured)"
    st.markdown(
        f"""
        <div class="ai-panel">
            <div class="ai-badge">✨ {html.escape(title)} · {html.escape(badge)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(markdown_body)
