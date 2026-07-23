"""Match Report tab: score, matched and missing skills, explanation."""

import streamlit as st

from src.services.report_export import build_markdown_report, suggested_filename


def render(state: dict | None) -> None:
    if not state or not state.get("match_report"):
        st.info("Run the analysis first.")
        return

    report = state["match_report"]

    st.download_button(
        "Download full report (Markdown)",
        data=build_markdown_report(state),
        file_name=suggested_filename(state),
        mime="text/markdown",
        use_container_width=True,
        help="Match report, bullet suggestions, application answers, and interview questions.",
    )
    reference = state.get("reference_score")
    score = report["overall_score"]
    show_reference = reference is not None and reference != score

    if show_reference:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("AI Score", f"{score}/100")
        col2.metric("Rule-based Score", f"{reference}/100")
        col3.metric("Matched Skills", len(report["matched_skills"]))
        col4.metric("Missing Skills", len(report["missing_skills"]))
        st.caption(
            "Two scores: the AI's assessment and a deterministic rule-based baseline. "
            "They usually differ; when they diverge sharply, the skills below are the more reliable read."
        )
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Match Score", f"{score}/100")
        col2.metric("Matched Skills", len(report["matched_skills"]))
        col3.metric("Missing Skills", len(report["missing_skills"]))
    st.progress(score / 100)

    for warning in state.get("warnings", []):
        st.warning(warning)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Matched Skills")
        for skill in report["matched_skills"]:
            st.success(skill)
    with col2:
        st.markdown("#### Missing Skills")
        for skill in report["missing_skills"]:
            st.error(skill)

    st.markdown("#### Analysis")
    st.write(report["explanation"])
