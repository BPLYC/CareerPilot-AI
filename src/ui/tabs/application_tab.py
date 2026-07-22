"""Application & Interview tab: answer starters and practice questions."""

import streamlit as st

ANSWER_LABELS = {
    "why_this_role": "Why this role",
    "key_strengths": "Key strengths",
    "project_example": "Project example",
}

SENSITIVE_REMINDER = "Please fill visa, authorization, and compensation questions yourself."


def render(state: dict | None) -> None:
    if not state:
        st.info("Run the analysis first.")
        return

    answers = state.get("application_answers") or {}
    questions = state.get("interview_questions") or []

    if not answers and not questions:
        st.info("Application and interview prep is available when the resume is a workable match for the role.")
        return

    if answers:
        st.warning(answers.get("review_notice", "Draft only. Review and personalize before submitting."))
        st.markdown("#### Application Answer Starters")
        for key, label in ANSWER_LABELS.items():
            if answers.get(key):
                st.markdown(f"**{label}**")
                st.write(answers[key])

        custom_answers = answers.get("custom_answers", [])
        if custom_answers:
            st.markdown("#### Custom Application Questions")
            for item in custom_answers:
                with st.expander(item.get("question", "Application question"), expanded=True):
                    st.write(item.get("answer", ""))
                    if item.get("review_notice"):
                        st.caption(item["review_notice"])

    if questions:
        st.markdown("#### Interview Practice")
        for index, question in enumerate(questions, start=1):
            with st.expander(f"Question {index}: {question.get('focus_area', 'Practice')}"):
                st.write(question.get("question", ""))
                if question.get("prep_notes"):
                    st.caption(question["prep_notes"])

    # Only shown alongside actual drafts. It used to render unconditionally,
    # including before any analysis had run, where it warned about content that
    # was not on screen.
    st.warning(SENSITIVE_REMINDER)
