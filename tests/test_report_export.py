"""Markdown export: content, safety notices, and filename shaping."""

from datetime import datetime

import pytest

from src.services.report_export import (
    REVIEW_NOTICE,
    SENSITIVE_NOTICE,
    build_markdown_report,
    suggested_filename,
)

NOW = datetime(2026, 7, 23, 5, 30)

FULL_STATE = {
    "jd_analysis": {"job_title": "AI Intern"},
    "match_report": {
        "overall_score": 65,
        "matched_skills": ["Python", "SQL"],
        "missing_skills": ["PyTorch"],
        "relevant_projects": ["Movie Recommendation System"],
        "weak_sections": ["Limited internship experience"],
        "explanation": "Solid overlap on core tooling.",
    },
    "optimized_bullets": [
        {
            "context": "Movie Recommendation System",
            "original_bullet": "Built a recommender",
            "optimized_bullet": "Built a collaborative-filtering recommender in Python",
            "rationale": "Names the technique already described in the resume.",
        }
    ],
    "application_answers": {
        "why_this_role": "It matches my Python work.",
        "key_strengths": "Hands-on data projects.",
        "project_example": "The recommender project.",
        "custom_answers": [
            {"question": "Why us?", "answer": "Because of the data team.", "review_notice": "Draft only."}
        ],
        "review_notice": "Draft only.",
    },
    "interview_questions": [
        {"question": "Walk me through your recommender.", "focus_area": "Projects", "prep_notes": "Use STAR."}
    ],
    "warnings": ["Resume text was truncated to fit analysis limits."],
}


def test_empty_state_produces_no_report():
    assert build_markdown_report({}) == ""


def test_report_leads_with_the_role_and_review_notice():
    report = build_markdown_report(FULL_STATE, now=NOW)

    assert report.startswith("# CareerPilot AI Report: AI Intern")
    assert "_Generated 2026-07-23 05:30_" in report
    assert REVIEW_NOTICE in report


def test_report_always_carries_the_sensitive_notice():
    # This is the boundary telling the applicant to answer visa and
    # compensation questions themselves. It must survive export.
    assert SENSITIVE_NOTICE in build_markdown_report(FULL_STATE, now=NOW)


def test_report_includes_every_section():
    report = build_markdown_report(FULL_STATE, now=NOW)

    for heading in [
        "## Warnings",
        "## Match Report",
        "## Resume Bullet Suggestions",
        "## Application Answer Starters",
        "## Interview Practice",
    ]:
        assert heading in report


def test_report_carries_the_actual_content():
    report = build_markdown_report(FULL_STATE, now=NOW)

    assert "**Score:** 65/100" in report
    assert "- Python" in report
    assert "- PyTorch" in report
    assert "Built a collaborative-filtering recommender in Python" in report
    assert "Because of the data team." in report
    assert "Walk me through your recommender." in report
    assert "Resume text was truncated" in report


def test_low_match_state_omits_sections_with_no_content():
    low_match = {
        "jd_analysis": {"job_title": "ML Intern"},
        "match_report": {
            "overall_score": 30,
            "matched_skills": [],
            "missing_skills": ["Python"],
            "relevant_projects": [],
            "weak_sections": [],
            "explanation": "Little overlap.",
        },
        "optimized_bullets": [],
        "application_answers": {},
        "interview_questions": [],
        "warnings": ["Low match score (30/100)."],
    }

    report = build_markdown_report(low_match, now=NOW)

    assert "## Match Report" in report
    assert "## Resume Bullet Suggestions" not in report
    assert "## Application Answer Starters" not in report
    assert "## Interview Practice" not in report
    assert "_None identified._" in report
    assert SENSITIVE_NOTICE in report


@pytest.mark.parametrize(
    ("job_title", "expected"),
    [
        ("AI Intern", "careerpilot-ai-intern-20260723.md"),
        ("Data Analyst / BI", "careerpilot-data-analyst-bi-20260723.md"),
        ("", "careerpilot-role-20260723.md"),
        ("!!!", "careerpilot-role-20260723.md"),
    ],
)
def test_suggested_filename(job_title, expected):
    state = {"jd_analysis": {"job_title": job_title}}

    assert suggested_filename(state, now=NOW) == expected


def test_long_context_is_trimmed_in_the_heading():
    # Observed with the real model: it returned the whole rewritten bullet as
    # `context`, so every heading became a paragraph.
    long_context = (
        "Built a movie recommendation system using Python, pandas, NumPy, and scikit-learn. "
        "Compared collaborative filtering and content-based recommendations."
    )
    state = {
        "jd_analysis": {"job_title": "AI Intern"},
        "match_report": {"overall_score": 60, "matched_skills": [], "missing_skills": [], "explanation": ""},
        "optimized_bullets": [{"context": long_context, "optimized_bullet": "x", "rationale": "y"}],
    }

    report = build_markdown_report(state, now=NOW)
    heading = next(line for line in report.splitlines() if line.startswith("### 1."))

    assert len(heading) < 75
    assert heading.endswith("...")
    # The full text is still available in the body, just not as the heading.
    assert "x" in report


def test_missing_context_falls_back_to_a_label():
    state = {
        "jd_analysis": {"job_title": "AI Intern"},
        "match_report": {"overall_score": 60, "matched_skills": [], "missing_skills": [], "explanation": ""},
        "optimized_bullets": [{"context": "   ", "optimized_bullet": "x", "rationale": "y"}],
    }

    assert "### 1. Resume experience" in build_markdown_report(state, now=NOW)


def test_report_ends_with_a_single_newline():
    report = build_markdown_report(FULL_STATE, now=NOW)

    assert report.endswith("\n")
    assert not report.endswith("\n\n")
