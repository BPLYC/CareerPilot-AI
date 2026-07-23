"""Sidebar: provider status, model settings, and the sample data loader."""

from dataclasses import dataclass

import streamlit as st

from src.services.provider_config import get_provider_config
from src.ui.sample_data import SAMPLE_JDS, load_sample

THINKING_OPTIONS = ["disabled", "enabled"]
EFFORT_OPTIONS = ["low", "medium", "high"]


@dataclass
class ProviderSettings:
    """What the user picked in the sidebar, carried as a value.

    Returning these instead of writing them straight to os.environ is what keeps
    sidebar rendering free of side effects; run_analysis applies them for the
    duration of one run.
    """

    model: str
    thinking: str
    reasoning_effort: str

    def as_overrides(self) -> dict:
        return {
            "model": self.model,
            "thinking": self.thinking,
            "reasoning_effort": self.reasoning_effort,
        }


def _index_of(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def render_sidebar() -> ProviderSettings:
    with st.sidebar:
        st.title("CareerPilot AI")
        st.divider()

        config = get_provider_config()
        if config.api_key:
            st.success("DeepSeek API key configured")
        else:
            st.warning("DeepSeek API key missing; deterministic fallback will be used.")

        model = st.text_input("Model", value=config.model, placeholder="Enter your DeepSeek model")

        thinking = st.selectbox(
            "Thinking Mode",
            THINKING_OPTIONS,
            index=_index_of(THINKING_OPTIONS, config.thinking),
        )
        reasoning_effort = st.selectbox(
            "Reasoning Effort",
            EFFORT_OPTIONS,
            index=_index_of(EFFORT_OPTIONS, config.reasoning_effort),
            disabled=thinking == "disabled",
        )

        st.caption(f"Base URL: {config.base_url}")
        st.divider()

        selected_jd = st.selectbox("Select Sample JD", list(SAMPLE_JDS))
        if st.button("Load Sample Data", use_container_width=True):
            resume_text, jd_text = load_sample(selected_jd)
            st.session_state["sample_resume"] = resume_text
            st.session_state["sample_jd"] = jd_text
            st.success("Sample data loaded")

    return ProviderSettings(model=model, thinking=thinking, reasoning_effort=reasoning_effort)
