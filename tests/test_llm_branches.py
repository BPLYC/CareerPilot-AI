"""Cover the branch every agent takes when credentials are configured.

The whole suite otherwise runs with the key cleared, so every test exercises the
deterministic fallback and the LLM branch is never executed. A fake chat model
stands in for DeepSeek here: it returns canned content, which is enough to check
that responses are parsed, validated, and turned into state.
"""

import json

import pytest

from src.agents import (
    application_answer_agent,
    common,
    interview_coach_agent,
    jd_analyzer_agent,
    match_scoring_agent,
    resume_optimizer_agent,
    resume_parser_agent,
)
from src.workflow.state import create_initial_state


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    """Records the prompts it is given and replays a scripted response."""

    def __init__(self, content):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return FakeResponse(self.content)


@pytest.fixture
def use_llm(monkeypatch):
    """Configure agents to take the LLM branch, with a scripted response."""

    monkeypatch.setattr(common, "can_use_llm", lambda *args, **kwargs: True)

    def install(content) -> FakeLLM:
        fake = FakeLLM(content)
        monkeypatch.setattr(common, "get_llm", lambda *args, **kwargs: fake)
        return fake

    return install


def _state() -> dict:
    state = create_initial_state("Alex Chen\nSkills: Python", "Data Intern needs Python and SQL.")
    state["resume_profile"] = {"name": "Alex Chen", "skills": ["Python"], "projects": []}
    state["jd_analysis"] = {"job_title": "Data Intern", "required_skills": ["Python", "SQL"], "keywords": ["data"]}
    state["match_report"] = {
        "overall_score": 70,
        "matched_skills": ["Python"],
        "missing_skills": ["SQL"],
        "relevant_projects": [],
        "weak_sections": [],
        "explanation": "ok",
    }
    return state


def _succeeded(update: dict) -> bool:
    return "errors" not in update and "Fallback used." not in update["workflow_trace"][0]


def test_resume_parser_uses_the_model_response(use_llm):
    fake = use_llm(json.dumps({
        "name": "Parsed By Model",
        "email": "model@example.com",
        "phone": "000",
        "skills": ["Rust"],
        "projects": [],
        "work_experience": [],
    }))

    update = resume_parser_agent.resume_parser_node(create_initial_state("Alex Chen", "jd"))

    assert _succeeded(update)
    assert update["resume_profile"]["name"] == "Parsed By Model"
    assert update["resume_profile"]["skills"] == ["Rust"]
    # The resume text has to reach the model, not just the schema instruction.
    assert "Alex Chen" in str(fake.calls[0])


def test_jd_analyzer_uses_the_model_response(use_llm):
    use_llm(json.dumps({
        "job_title": "Model Titled Role",
        "company": "Acme",
        "required_skills": ["Go"],
        "preferred_skills": [],
        "responsibilities": [],
        "keywords": ["go"],
        "tools_and_technologies": [],
    }))

    update = jd_analyzer_agent.jd_analyzer_node(create_initial_state("resume", "jd text"))

    assert _succeeded(update)
    assert update["jd_analysis"]["job_title"] == "Model Titled Role"


def test_match_scoring_uses_the_model_response(use_llm):
    use_llm(json.dumps({
        "overall_score": 88,
        "matched_skills": ["Python"],
        "missing_skills": [],
        "relevant_projects": [],
        "weak_sections": [],
        "explanation": "strong",
    }))

    update = match_scoring_agent.match_scoring_node(_state())

    assert _succeeded(update)
    assert update["match_report"]["overall_score"] == 88
    # A high score raises no low-match warning. It may raise a gap warning,
    # since the deterministic baseline for this fixture scores far below 88 --
    # that is the score-alignment behaviour, exercised in test_score_alignment.
    assert not any("Low match score" in w for w in update["warnings"])


def test_match_scoring_warns_on_a_low_model_score(use_llm):
    use_llm(json.dumps({
        "overall_score": 20,
        "matched_skills": [],
        "missing_skills": ["Python"],
        "relevant_projects": [],
        "weak_sections": [],
        "explanation": "weak",
    }))

    update = match_scoring_agent.match_scoring_node(_state())

    assert any("Low match score" in warning for warning in update["warnings"])


def test_resume_optimizer_parses_a_json_array(use_llm):
    use_llm(json.dumps([
        {
            "context": "Task Manager",
            "original_bullet": "Built an app",
            "optimized_bullet": "Built a Flask task manager used in coursework",
            "rationale": "adds the framework already on the resume",
        }
    ]))

    update = resume_optimizer_agent.resume_optimizer_node(_state())

    assert _succeeded(update)
    assert len(update["optimized_bullets"]) == 1
    assert update["optimized_bullets"][0]["context"] == "Task Manager"


def test_interview_coach_accepts_an_items_wrapper(use_llm):
    # Models routinely wrap arrays in an object; invoke_structured_list unwraps
    # a single "items" key rather than falling back over it.
    use_llm(json.dumps({"items": [
        {"question": "Explain your project", "focus_area": "Projects", "prep_notes": "use STAR"},
        {"question": "Why SQL?", "focus_area": "Skills", "prep_notes": "cite coursework"},
    ]}))

    update = interview_coach_agent.interview_coach_node(_state())

    assert _succeeded(update)
    assert len(update["interview_questions"]) == 2


def test_application_answer_uses_the_model_response(use_llm):
    use_llm(json.dumps({
        "why_this_role": "model written reason",
        "key_strengths": "model written strengths",
        "project_example": "model written example",
        "custom_answers": [],
        "review_notice": "Draft only.",
    }))

    state = _state()
    update = application_answer_agent.application_answer_node(state)

    assert _succeeded(update)
    assert update["application_answers"]["why_this_role"] == "model written reason"


def test_sensitive_questions_are_overridden_even_when_the_model_answers_them(use_llm):
    """The model answering a visa question must not reach the user."""

    use_llm(json.dumps({
        "why_this_role": "reason",
        "key_strengths": "strengths",
        "project_example": "example",
        "custom_answers": [
            {
                "question": "Do you need visa sponsorship?",
                "answer": "No, you do not need sponsorship.",
                "review_notice": "",
            }
        ],
        "review_notice": "Draft only.",
    }))

    state = _state()
    state["application_questions"] = ["Do you need visa sponsorship?"]
    update = application_answer_agent.application_answer_node(state)

    answer = update["application_answers"]["custom_answers"][0]["answer"]
    assert answer == application_answer_agent.SENSITIVE_NOTICE


@pytest.mark.parametrize(
    "content",
    ["this is not json at all", "{unclosed", '{"overall_score": "not a number"}', ""],
)
def test_unparseable_responses_fall_back(use_llm, content):
    use_llm(content)

    update = match_scoring_agent.match_scoring_node(_state())

    assert update["errors"], "the parse failure should be recorded"
    assert "Fallback used." in update["workflow_trace"][0]
    assert isinstance(update["match_report"]["overall_score"], int)


def test_a_non_array_response_for_a_list_node_falls_back(use_llm):
    use_llm(json.dumps({"context": "single object, not an array"}))

    update = resume_optimizer_agent.resume_optimizer_node(_state())

    assert update["errors"]
    assert "Fallback used." in update["workflow_trace"][0]


def test_non_string_content_is_handled(use_llm):
    # Some clients return structured content blocks rather than a plain string.
    use_llm({"overall_score": 55, "matched_skills": [], "missing_skills": [],
             "relevant_projects": [], "weak_sections": [], "explanation": "block content"})

    update = match_scoring_agent.match_scoring_node(_state())

    assert _succeeded(update)
    assert update["match_report"]["overall_score"] == 55
