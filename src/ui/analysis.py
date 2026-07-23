"""Running an analysis from the UI, with caching and run history."""

import streamlit as st

from src.services.cache import get_cache_key, load_from_cache, save_to_cache
from src.services.provider_config import provider_overrides
from src.services.run_history import record_run
from src.workflow.careerpilot_graph import stream_workflow
from src.workflow.state import create_initial_state


def save_run_history(cache_key: str, state: dict) -> None:
    try:
        record_run(cache_key, state)
    except Exception as exc:
        st.warning(f"Run history could not be saved: {exc}")


def run_analysis(
    resume_text: str,
    jd_text: str,
    application_questions: list[str] | None = None,
    settings=None,
) -> dict:
    application_questions = application_questions or []
    key = get_cache_key(resume_text, jd_text, application_questions)
    cached = load_from_cache(key)
    if cached:
        st.info("Loaded cached analysis for the same resume and JD.")
        save_run_history(key, cached)
        return cached

    state = create_initial_state(resume_text, jd_text, application_questions)
    final_state = state
    overrides = settings.as_overrides() if settings else {}
    with st.status("Running CareerPilot Analysis...", expanded=True) as status:
        # Provider settings are applied only while the workflow runs, so
        # rendering the sidebar does not leave them set process-wide.
        with provider_overrides(**overrides):
            for event in stream_workflow(state):
                node_name, final_state = next(iter(event.items()))
                traces = final_state.get("workflow_trace", [])
                st.write(f"{node_name}: {traces[-1] if traces else 'completed'}")
        status.update(label="Analysis complete", state="complete")

    save_to_cache(key, final_state)
    save_run_history(key, final_state)
    return final_state
