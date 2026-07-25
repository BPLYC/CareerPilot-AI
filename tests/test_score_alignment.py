"""The model's match score is shown against a deterministic baseline.

The model scores well below the rule-based scorer on the sample data, and the
user reads the model number as the headline. Rather than silently rewrite it --
which would hide the model's behaviour -- the baseline is carried through, shown
beside it, and a warning fires when the two disagree sharply.
"""

from src.agents import common, match_scoring_agent
from src.agents.match_scoring_agent import (
    LOW_MATCH_THRESHOLD,
    SCORE_GAP_THRESHOLD,
    _score_warnings,
    match_scoring_node,
)
from src.services.report_export import build_markdown_report
from src.workflow.state import create_initial_state


def _report(score):
    return {"overall_score": score, "matched_skills": [], "missing_skills": []}


# --- the warning logic, in isolation ---------------------------------------


def test_a_wide_gap_warns():
    warnings = _score_warnings(_report(70), reference=70 - SCORE_GAP_THRESHOLD)
    assert any("相差" in w for w in warnings)


def test_a_narrow_gap_does_not_warn():
    warnings = _score_warnings(_report(70), reference=70 - (SCORE_GAP_THRESHOLD - 1))
    assert not any("相差" in w for w in warnings)


def test_the_gap_warning_is_symmetric():
    # The model can land either side of the baseline.
    above = _score_warnings(_report(90), reference=90 - SCORE_GAP_THRESHOLD)
    below = _score_warnings(_report(30), reference=30 + SCORE_GAP_THRESHOLD)
    assert any("相差" in w for w in above)
    assert any("相差" in w for w in below)


def test_a_low_score_still_warns_independently():
    warnings = _score_warnings(_report(LOW_MATCH_THRESHOLD - 1), reference=LOW_MATCH_THRESHOLD - 1)
    assert any("匹配评分较低" in w for w in warnings)
    # Equal scores, so no gap warning rides along.
    assert not any("相差" in w for w in warnings)


# --- the node, deterministic path ------------------------------------------


def _scoring_state():
    state = create_initial_state("resume", "jd")
    # Scores ~48 deterministically: one matched skill (40), no projects,
    # no education (8), no work experience.
    state["resume_profile"] = {"skills": ["Python"], "projects": [], "work_experience": []}
    state["jd_analysis"] = {"required_skills": ["Python"], "keywords": [], "responsibilities": []}
    return state


def test_reference_score_is_recorded_and_agrees_on_the_fallback_path():
    update = match_scoring_node(_scoring_state())

    assert update["reference_score"] == update["match_report"]["overall_score"]
    # The model IS the reference scorer here, so nothing disagrees.
    assert not any("disagree by" in w for w in update["warnings"])


def test_the_model_score_is_kept_not_overwritten_by_the_reference(monkeypatch):
    monkeypatch.setattr(common, "can_use_llm", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        match_scoring_agent,
        "invoke_structured",
        lambda *args, **kwargs: {
            "overall_score": 15,
            "matched_skills": ["Python"],
            "missing_skills": [],
            "relevant_projects": [],
            "weak_sections": [],
            "explanation": "model says 15",
        },
    )

    update = match_scoring_node(_scoring_state())

    # The whole point: the model's number survives, it is not clamped to the
    # baseline. The baseline sits beside it and the disagreement is surfaced.
    assert update["match_report"]["overall_score"] == 15
    assert update["reference_score"] >= 40
    assert any("相差" in w for w in update["warnings"])


# --- export ----------------------------------------------------------------


def test_export_shows_both_scores_when_they_differ():
    state = {
        "match_report": {
            "overall_score": 50,
            "matched_skills": ["Python"],
            "missing_skills": [],
            "explanation": "x",
        },
        "reference_score": 72,
        "jd_analysis": {"job_title": "AI Intern"},
    }

    report = build_markdown_report(state)

    assert "50/100 (AI)" in report
    assert "72/100 (rule-based baseline)" in report


def test_export_shows_one_score_when_they_agree():
    state = {
        "match_report": {"overall_score": 68, "matched_skills": [], "missing_skills": [], "explanation": "x"},
        "reference_score": 68,
        "jd_analysis": {"job_title": "AI Intern"},
    }

    report = build_markdown_report(state)

    assert "**Score:** 68/100" in report
    assert "rule-based baseline" not in report
