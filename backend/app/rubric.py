"""Classroom observation rubric keys and overall score calculation."""

from __future__ import annotations

from typing import Any, Dict, Tuple

KEY_STUDENT_ENGAGEMENT = "student_engagement"
KEY_CONTENT_KNOWLEDGE = "content_knowledge"
KEY_CLASSROOM_MANAGEMENT = "classroom_management"


def build_classroom_rubric(
    student_engagement: int,
    content_knowledge: int,
    classroom_management: int,
) -> Tuple[Dict[str, Any], float]:
    rubric: Dict[str, Any] = {
        KEY_STUDENT_ENGAGEMENT: student_engagement,
        KEY_CONTENT_KNOWLEDGE: content_knowledge,
        KEY_CLASSROOM_MANAGEMENT: classroom_management,
        "rubric_version": "instructional_practice_v1",
    }
    overall = round(
        (student_engagement + content_knowledge + classroom_management) / 3.0,
        2,
    )
    return rubric, overall
