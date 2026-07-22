"""Input tab: resume upload or paste, job description, optional questions."""

import streamlit as st

from src.parsers.file_parser import parse_resume_file
from src.ui.analysis import run_analysis


def split_questions(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def render(settings) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Your Resume")
        resume_file = st.file_uploader("Upload Resume (TXT, PDF, or DOCX)", type=["txt", "pdf", "docx"])
        pasted_resume = st.text_area(
            "Or paste resume text here",
            height=330,
            value=st.session_state.get("sample_resume", ""),
        )
    with col2:
        st.subheader("Job Description")
        jd_text = st.text_area("Paste JD here", height=390, value=st.session_state.get("sample_jd", ""))

    application_question_text = st.text_area(
        "Optional application questions",
        height=120,
        placeholder="One question per line, such as: Why are you interested in this internship?",
    )

    if not st.button("Run CareerPilot Analysis", type="primary", use_container_width=True):
        return

    try:
        file_text = parse_resume_file(resume_file) if resume_file else ""
        resume_text = file_text or pasted_resume
        if not resume_text.strip() or not jd_text.strip():
            st.error("Please provide both a resume and a job description.")
            return
        st.session_state["last_result"] = run_analysis(
            resume_text,
            jd_text,
            split_questions(application_question_text),
            settings=settings,
        )
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
