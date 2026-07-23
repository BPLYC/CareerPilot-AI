"""LangGraph state and initialization helpers."""

from operator import add
from typing import Annotated, Any, TypedDict


class CareerPilotState(TypedDict):
    raw_resume_text: str
    raw_jd_text: str
    resume_profile: dict | None
    jd_analysis: dict | None
    retrieved_context: dict
    match_report: dict | None
    optimized_bullets: list[dict]
    has_exaggeration: bool
    reflection_feedback: str
    reflection_iteration: int
    application_questions: list[str]
    application_answers: dict[str, Any]
    interview_questions: list[dict]
    workflow_trace: Annotated[list[str], add]
    errors: Annotated[list[str], add]
    warnings: Annotated[list[str], add]


def create_initial_state(
    resume_text: str,
    jd_text: str,
    application_questions: list[str] | None = None,
) -> CareerPilotState:
    return {
        "raw_resume_text": resume_text or "",
        "raw_jd_text": jd_text or "",
        "resume_profile": None,
        "jd_analysis": None,
        "retrieved_context": {},
        "match_report": None,
        "optimized_bullets": [],
        "has_exaggeration": False,
        "reflection_feedback": "",
        "reflection_iteration": 0,
        "application_questions": application_questions or [],
        "application_answers": {},
        "interview_questions": [],
        "workflow_trace": [],
        "errors": [],
        "warnings": [],
    }
