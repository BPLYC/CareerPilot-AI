"""The parts of the UI that are testable without a Streamlit runtime.

Splitting app.py into modules made these reachable: they were previously inline
in a 263-line render function.
"""

import os

import pytest

from src.services.provider_config import provider_overrides
from src.ui.sample_data import SAMPLE_JDS, load_sample
from src.ui.tabs.input_tab import split_questions
from src.ui.tabs.run_history_tab import to_rows


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Why this role?\nTell us about a project", ["Why this role?", "Tell us about a project"]),
        ("  padded  \n\n\n  another  ", ["padded", "another"]),
        ("", []),
        ("   \n  \n", []),
        (None, []),
    ],
)
def test_split_questions(text, expected):
    assert split_questions(text) == expected


@pytest.mark.parametrize("role", list(SAMPLE_JDS))
def test_every_sample_role_loads(role):
    resume_text, jd_text = load_sample(role)

    assert resume_text.strip()
    assert jd_text.strip()


def test_run_history_rows_use_display_labels():
    runs = [
        {
            "created_at": "2026-07-23T04:00:00",
            "job_title": "AI Intern",
            "match_score": 65,
            "matched_skills_count": 9,
            "missing_skills_count": 4,
            "optimized_bullets_count": 10,
            "application_answer_count": 4,
            "interview_question_count": 6,
            "warnings_count": 0,
            "errors_count": 0,
        }
    ]

    rows = to_rows(runs)

    assert rows[0]["Role"] == "AI Intern"
    assert rows[0]["Score"] == 65
    assert "job_title" not in rows[0]


def test_provider_overrides_restores_previous_values(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "from-dotenv")
    monkeypatch.delenv("DEEPSEEK_THINKING", raising=False)

    with provider_overrides(model="from-sidebar", thinking="enabled"):
        assert os.environ["DEEPSEEK_MODEL"] == "from-sidebar"
        assert os.environ["DEEPSEEK_THINKING"] == "enabled"

    assert os.environ["DEEPSEEK_MODEL"] == "from-dotenv"
    assert "DEEPSEEK_THINKING" not in os.environ


def test_provider_overrides_ignores_empty_values(monkeypatch):
    # An empty model box must not blank the value .env supplied.
    monkeypatch.setenv("DEEPSEEK_MODEL", "from-dotenv")

    with provider_overrides(model="", thinking=""):
        assert os.environ["DEEPSEEK_MODEL"] == "from-dotenv"


def test_provider_overrides_restores_after_an_exception(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "from-dotenv")

    with pytest.raises(RuntimeError):
        with provider_overrides(model="from-sidebar"):
            raise RuntimeError("workflow blew up")

    assert os.environ["DEEPSEEK_MODEL"] == "from-dotenv"
