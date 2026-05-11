"""
LLM-backed instructional helpers.

Uses OPENAI_API_KEY from the environment when set; otherwise returns
deterministic preview content suitable for local development.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Literal, Tuple

import httpx

from app.settings import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

SourceKind = Literal["openai", "mock"]


def observation_record_text(row: Dict[str, Any]) -> str:
    header: List[str] = []
    if row.get("lesson_title"):
        header.append(f"Lesson context: {row.get('lesson_title')}")
    if row.get("focus_area"):
        header.append(f"Focus: {row.get('focus_area')}")
    parts = header + [
        row.get("notes"),
        row.get("strengths"),
        row.get("growth_areas"),
    ]
    return "\n\n".join(str(p).strip() for p in parts if p)


def _chat_completion(user_prompt: str, system_prompt: str) -> str:
    if not OPENAI_API_KEY:
        return ""
    url = f"{OPENAI_BASE_URL}/chat/completions"
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.35,
    }
    with httpx.Client(timeout=90.0) as client:
        r = client.post(
            url,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    return str(data["choices"][0]["message"]["content"] or "").strip()


def _parse_json_string_list(raw: str) -> List[str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "bullets" in data:
            data = data["bullets"]
        if isinstance(data, dict) and "suggestions" in data:
            data = data["suggestions"]
        if isinstance(data, list):
            out = [str(x).strip() for x in data if str(x).strip()]
            return out
    except json.JSONDecodeError:
        pass
    lines = [re.sub(r"^[-*•]\s*", "", ln).strip() for ln in text.splitlines() if ln.strip()]
    return [ln for ln in lines if ln]


def _mock_observation_bullets(full_text: str) -> List[str]:
    snippet = full_text.strip().replace("\n", " ")
    if len(snippet) > 220:
        snippet = snippet[:217] + "…"
    return [
        "Anchor next steps in one concrete instructional shift drawn from your evidence above.",
        "Schedule a brief follow-up peer conversation to rehearse the strategy you named in context.",
        "Capture one student-voice artifact in the next lesson to validate engagement trends you observed.",
    ]


def summarize_observation_for_teacher(full_text: str) -> Tuple[List[str], SourceKind]:
    """Return exactly three high-impact bullets for the educator."""
    text = full_text.strip()
    if len(text) < 12:
        return [], "mock"

    system = (
        "You are an expert instructional coach in K-12 and higher education. "
        "You write concise, respectful, actionable feedback for educators."
    )
    user = (
        "Read the classroom observation notes below. Produce exactly THREE bullet points "
        "that highlight the highest-impact insights for the teacher's professional growth. "
        "Each bullet must be one sentence, no numbering in the string itself. "
        "Respond with ONLY valid JSON: {\"bullets\": [\"...\", \"...\", \"...\"]}\n\n"
        f"NOTES:\n{text}"
    )

    if not OPENAI_API_KEY:
        return _mock_observation_bullets(text), "mock"

    try:
        raw = _chat_completion(user, system)
        bullets = _parse_json_string_list(raw)
        if len(bullets) >= 3:
            return bullets[:3], "openai"
        if bullets:
            while len(bullets) < 3:
                bullets.append(
                    "Identify one measurable student outcome to monitor in your next instructional cycle."
                )
            return bullets[:3], "openai"
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        pass
    return _mock_observation_bullets(text), "mock"


def _observations_score_context(observations: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for o in observations:
        rub = o.get("rubric") or {}
        lines.append(
            f"- {o.get('observed_at', '')}: holistic={o.get('overall_score')}, "
            f"rubric={json.dumps(rub, default=str)[:400]}"
        )
    return "\n".join(lines) if lines else "(no scored observations on file)"


def _mock_goal_suggestions(observations: List[Dict[str, Any]]) -> List[str]:
    scores: List[float] = []
    for o in observations:
        s = o.get("overall_score")
        if s is not None:
            try:
                scores.append(float(s))
            except (TypeError, ValueError):
                continue
    avg = sum(scores) / len(scores) if scores else None
    if avg is not None and avg < 3.2:
        return [
            "Design two low-inference formative checks for engagement during the next unit launch.",
            "Pilot a concise classroom routine map to strengthen transitions without reducing rigor.",
        ]
    return [
        "Lead a peer learning lab focused on cognitively demanding tasks aligned to your standards.",
        "Document student discourse patterns across three lessons to refine questioning sequences.",
    ]


def suggest_professional_development_goals(
    observations: List[Dict[str, Any]],
) -> Tuple[List[str], SourceKind]:
    """Return two professional development goal statements informed by observation history."""
    ctx = _observations_score_context(observations)
    system = (
        "You are a director of professional learning. Suggest measurable, respectful "
        "professional development goals for an educator."
    )
    user = (
        "Given the following observation score history for ONE educator, propose exactly TWO "
        "professional development goals they might add to their growth plan. "
        "Each goal must be a single sentence, specific and actionable. "
        "Respond with ONLY valid JSON: {\"suggestions\": [\"...\", \"...\"]}\n\n"
        f"HISTORY:\n{ctx}"
    )

    if not OPENAI_API_KEY:
        return _mock_goal_suggestions(observations), "mock"

    try:
        raw = _chat_completion(user, system)
        items = _parse_json_string_list(raw)
        if len(items) >= 2:
            return items[:2], "openai"
        if len(items) == 1:
            items.append(
                "Partner with a colleague to co-plan one lesson that elevates student academic discourse."
            )
            return items[:2], "openai"
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        pass
    return _mock_goal_suggestions(observations), "mock"
