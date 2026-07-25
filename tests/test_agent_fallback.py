"""The fallback path must produce the same derived state as the success path.

Before the shared run_node() skeleton existed, each node hand-rolled its own
try/except. Post-processing and derived state lived only in the success branch,
so when the LLM failed the node silently returned less than it should have.
These tests pin the unified behaviour.
"""

import pytest

from src.agents import application_answer_agent, common, match_scoring_agent
from src.workflow.state import create_initial_state

LOW_MATCH_RESUME = "Alex Chen\nalex@example.com\nHobbies: hiking.\n"
SKILL_HEAVY_JD = (
    "Machine Learning Intern\n"
    "Required: Python, PyTorch, TensorFlow, SQL, Docker, Spark, AWS.\n"
    "Responsibilities: train and evaluate models.\n"
)


@pytest.fixture
def llm_configured_but_failing(monkeypatch):
    """Make nodes take the LLM branch, and make that branch raise."""

    monkeypatch.setattr(common, "can_use_llm", lambda *args, **kwargs: True)

    def explode(*args, **kwargs):
        raise RuntimeError("simulated DeepSeek failure")

    monkeypatch.setattr(match_scoring_agent, "invoke_structured", explode)
    monkeypatch.setattr(application_answer_agent, "invoke_structured", explode)


def _scoring_state() -> dict:
    from src.agents.jd_analyzer_agent import fallback_analyze_jd
    from src.agents.resume_parser_agent import fallback_parse_resume

    state = create_initial_state(LOW_MATCH_RESUME, SKILL_HEAVY_JD)
    state["resume_profile"] = fallback_parse_resume(LOW_MATCH_RESUME)
    state["jd_analysis"] = fallback_analyze_jd(SKILL_HEAVY_JD)
    return state


def test_low_match_warning_survives_an_llm_failure(llm_configured_but_failing):
    update = match_scoring_agent.match_scoring_node(_scoring_state())

    assert update["match_report"]["overall_score"] < match_scoring_agent.LOW_MATCH_THRESHOLD
    assert update["errors"], "the failure should be recorded"
    # The warning is what the UI renders to tell the applicant this JD is a poor
    # fit. Losing it because the model happened to fail would hide that.
    assert any("匹配评分较低" in warning for warning in update["warnings"])


def test_sensitive_question_boundaries_survive_an_llm_failure(llm_configured_but_failing):
    state = _scoring_state()
    state["match_report"] = {"matched_skills": ["Python"], "missing_skills": ["Docker"], "overall_score": 30}
    state["application_questions"] = [
        "Do you require visa sponsorship now or in the future?",
        "Why are you interested in this internship?",
    ]

    update = application_answer_agent.application_answer_node(state)
    answers = {item["question"]: item["answer"] for item in update["application_answers"]["custom_answers"]}

    assert update["errors"], "the failure should be recorded"
    assert answers["Do you require visa sponsorship now or in the future?"] == (
        application_answer_agent.SENSITIVE_NOTICE
    )
    assert answers["Why are you interested in this internship?"] != application_answer_agent.SENSITIVE_NOTICE


def test_run_node_reports_the_failure_and_still_returns_output(monkeypatch):
    # Without this the credentials are absent, run_node never enters the LLM
    # branch, and the test would pass without exercising failure handling.
    monkeypatch.setattr(common, "can_use_llm", lambda *args, **kwargs: True)

    update = common.run_node(
        node_name="ExampleNode",
        output_key="value",
        llm_branch=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        fallback_branch=lambda: "deterministic",
        describe=lambda value: f"Produced {value}.",
    )

    assert update["value"] == "deterministic"
    assert "boom" in update["errors"][0]
    assert update["fallback_nodes"] == ["ExampleNode"]
    assert "已采用离线规则" in update["workflow_trace"][0]


def test_run_node_marks_unconfigured_llm_as_offline(monkeypatch):
    monkeypatch.setattr(common, "can_use_llm", lambda *args, **kwargs: False)

    update = common.run_node(
        node_name="ExampleNode",
        output_key="value",
        llm_branch=lambda: "model",
        fallback_branch=lambda: "deterministic",
        describe=lambda value: f"Produced {value}.",
    )

    assert update["value"] == "deterministic"
    assert update["fallback_nodes"] == ["ExampleNode"]
    assert "离线规则" in update["workflow_trace"][0]
