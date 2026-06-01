"""LangGraph state and initialization helpers."""

from operator import add
from typing import Annotated, Dict, List, Optional, TypedDict


class CareerPilotState(TypedDict):
    raw_resume_text: str
    raw_jd_text: str
    resume_profile: Optional[dict]
    jd_analysis: Optional[dict]
    retrieved_context: dict
    match_report: Optional[dict]
    optimized_bullets: List[dict]
    has_exaggeration: bool
    reflection_feedback: str
    reflection_iteration: int
    application_answers: Dict[str, str]
    interview_questions: List[dict]
    workflow_trace: Annotated[List[str], add]
    errors: Annotated[List[str], add]
    warnings: Annotated[List[str], add]


def create_initial_state(resume_text: str, jd_text: str) -> CareerPilotState:
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
        "application_answers": {},
        "interview_questions": [],
        "workflow_trace": [],
        "errors": [],
        "warnings": [],
    }
