from src.models.schemas import ResumeProfile
from src.workflow.state import create_initial_state


def test_resume_profile_defaults_are_independent():
    first = ResumeProfile()
    second = ResumeProfile()
    first.skills.append("Python")
    assert second.skills == []


def test_create_initial_state_has_required_fields():
    state = create_initial_state("resume", "jd")
    assert state["raw_resume_text"] == "resume"
    assert state["raw_jd_text"] == "jd"
    assert state["workflow_trace"] == []
    assert state["errors"] == []
    assert state["warnings"] == []
