"""Run History tab: summary metadata for recent local runs."""

import streamlit as st

from src.services.run_history import list_recent_runs

COLUMNS = [
    ("Time", "created_at"),
    ("Role", "job_title"),
    ("Score", "match_score"),
    ("Matched", "matched_skills_count"),
    ("Missing", "missing_skills_count"),
    ("Bullets", "optimized_bullets_count"),
    ("Answers", "application_answer_count"),
    ("Interview Qs", "interview_question_count"),
    ("Warnings", "warnings_count"),
    ("Errors", "errors_count"),
]


def to_rows(runs: list[dict]) -> list[dict]:
    return [{label: run[key] for label, key in COLUMNS} for run in runs]


def render(limit: int = 10) -> None:
    st.markdown("#### Recent Local Runs")
    try:
        runs = list_recent_runs(limit=limit)
    except Exception as exc:
        runs = []
        st.warning(f"Run history could not be loaded: {exc}")

    if not runs:
        st.info("Run an analysis to create local history.")
        return

    st.caption("History stores summary metadata only. Raw resumes and job descriptions are not persisted.")
    st.dataframe(to_rows(runs), use_container_width=True, hide_index=True)
