"""Streamlit entrypoint for CareerPilot AI."""

import os

import streamlit as st

from src.parsers.file_parser import parse_resume_file
from src.services.cache import get_cache_key, load_from_cache, save_to_cache
from src.services.provider_config import get_provider_config
from src.workflow.careerpilot_graph import stream_workflow
from src.workflow.state import create_initial_state


SAMPLE_JDS = {
    "AI Intern": "data/sample_jd_ai_intern.txt",
    "Data Analyst": "data/sample_jd_data_analyst.txt",
    "SWE Intern": "data/sample_jd_swe_intern.txt",
}


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def load_sample_data(selected_jd: str) -> None:
    st.session_state["sample_resume"] = read_text("data/sample_resume.txt")
    st.session_state["sample_jd"] = read_text(SAMPLE_JDS[selected_jd])


def run_analysis(resume_text: str, jd_text: str, application_questions: list[str] | None = None) -> dict:
    application_questions = application_questions or []
    key = get_cache_key(resume_text, jd_text, application_questions)
    cached = load_from_cache(key)
    if cached:
        st.info("Loaded cached analysis for the same resume and JD.")
        return cached

    state = create_initial_state(resume_text, jd_text, application_questions)
    final_state = state
    with st.status("Running CareerPilot Analysis...", expanded=True) as status:
        for event in stream_workflow(state):
            node_name, final_state = next(iter(event.items()))
            traces = final_state.get("workflow_trace", [])
            st.write(f"{node_name}: {traces[-1] if traces else 'completed'}")
        status.update(label="Analysis complete", state="complete")
    save_to_cache(key, final_state)
    return final_state


def main() -> None:
    st.set_page_config(page_title="CareerPilot AI", layout="wide")

    with st.sidebar:
        st.title("CareerPilot AI")
        st.divider()
        config = get_provider_config()
        if config.api_key:
            st.success("DeepSeek API key configured")
        else:
            st.warning("DeepSeek API key missing; deterministic fallback will be used.")

        model_input = st.text_input("Model", value=config.model, placeholder="Enter your DeepSeek model")
        if model_input:
            os.environ["DEEPSEEK_MODEL"] = model_input

        thinking_options = ["disabled", "enabled"]
        thinking_index = thinking_options.index(config.thinking) if config.thinking in thinking_options else 0
        thinking_mode = st.selectbox("Thinking Mode", thinking_options, index=thinking_index)
        os.environ["DEEPSEEK_THINKING"] = thinking_mode

        effort_options = ["low", "medium", "high"]
        effort_index = effort_options.index(config.reasoning_effort) if config.reasoning_effort in effort_options else 0
        reasoning_effort = st.selectbox(
            "Reasoning Effort",
            effort_options,
            index=effort_index,
            disabled=thinking_mode == "disabled",
        )
        os.environ["DEEPSEEK_REASONING_EFFORT"] = reasoning_effort

        st.caption(f"Base URL: {config.base_url}")
        st.divider()
        selected_jd = st.selectbox("Select Sample JD", list(SAMPLE_JDS))
        if st.button("Load Sample Data", use_container_width=True):
            load_sample_data(selected_jd)
            st.success("Sample data loaded")

    st.title("CareerPilot AI")
    st.caption("LangGraph-based Multi-Agent RAG System for Resume-JD Matching")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Input", "Match Report", "Resume Tips", "Application & Interview", "Workflow Trace"]
    )

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Your Resume")
            resume_file = st.file_uploader("Upload Resume (TXT, PDF, or DOCX)", type=["txt", "pdf", "docx"])
            pasted_resume = st.text_area("Or paste resume text here", height=330, value=st.session_state.get("sample_resume", ""))
        with col2:
            st.subheader("Job Description")
            jd_text = st.text_area("Paste JD here", height=390, value=st.session_state.get("sample_jd", ""))
        application_question_text = st.text_area(
            "Optional application questions",
            height=120,
            placeholder="One question per line, such as: Why are you interested in this internship?",
        )

        if st.button("Run CareerPilot Analysis", type="primary", use_container_width=True):
            try:
                file_text = parse_resume_file(resume_file) if resume_file else ""
                resume_text = file_text or pasted_resume
                application_questions = [
                    line.strip() for line in application_question_text.splitlines() if line.strip()
                ]
                if not resume_text.strip() or not jd_text.strip():
                    st.error("Please provide both a resume and a job description.")
                else:
                    st.session_state["last_result"] = run_analysis(resume_text, jd_text, application_questions)
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")

    state = st.session_state.get("last_result")

    with tab2:
        if not state or not state.get("match_report"):
            st.info("Run the analysis first.")
        else:
            report = state["match_report"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Match Score", f"{report['overall_score']}/100")
            col2.metric("Matched Skills", len(report["matched_skills"]))
            col3.metric("Missing Skills", len(report["missing_skills"]))
            st.progress(report["overall_score"] / 100)

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

    with tab3:
        if not state or not state.get("optimized_bullets"):
            st.info("Run the analysis first, or check Match Report for low-match warnings.")
        else:
            st.warning("AI-generated draft. Please review and personalize before submitting.")
            if state.get("reflection_iteration", 0) > 0:
                st.info(f"Reflection reviewed suggestions: {state.get('reflection_feedback', '')}")
            for index, bullet in enumerate(state["optimized_bullets"], start=1):
                with st.expander(f"{bullet['context']} - Suggestion {index}", expanded=True):
                    if bullet.get("original_bullet"):
                        st.markdown("**Before:**")
                        st.text(bullet["original_bullet"])
                    st.markdown("**After:**")
                    st.markdown(f"> {bullet['optimized_bullet']}")
                    st.caption(bullet["rationale"])

    with tab4:
        if not state:
            st.info("Run the analysis first.")
        elif not state.get("application_answers") and not state.get("interview_questions"):
            st.info("Application and interview prep is available when the resume is a workable match for the role.")
        else:
            answers = state.get("application_answers", {})
            if answers:
                st.warning(answers.get("review_notice", "Draft only. Review and personalize before submitting."))
                st.markdown("#### Application Answer Starters")
                labels = {
                    "why_this_role": "Why this role",
                    "key_strengths": "Key strengths",
                    "project_example": "Project example",
                }
                for key, label in labels.items():
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

            questions = state.get("interview_questions", [])
            if questions:
                st.markdown("#### Interview Practice")
                for index, question in enumerate(questions, start=1):
                    with st.expander(f"Question {index}: {question.get('focus_area', 'Practice')}"):
                        st.write(question.get("question", ""))
                        if question.get("prep_notes"):
                            st.caption(question["prep_notes"])
        st.warning("Please fill visa, authorization, and compensation questions yourself.")

    with tab5:
        if not state:
            st.info("Run the analysis first.")
        else:
            st.markdown("#### Agent Workflow Trace")
            for index, trace in enumerate(state.get("workflow_trace", []), start=1):
                st.text(f"Step {index}: {trace}")
            if state.get("errors"):
                st.markdown("#### Errors")
                for error in state["errors"]:
                    st.error(error)
            with st.expander("View Full State JSON"):
                st.json(state)


if __name__ == "__main__":
    main()
