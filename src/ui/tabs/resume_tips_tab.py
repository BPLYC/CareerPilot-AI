"""Resume Tips tab: before/after bullet suggestions."""

import streamlit as st


def render(state: dict | None) -> None:
    if not state or not state.get("optimized_bullets"):
        st.info("Run the analysis first, or check Match Report for low-match warnings.")
        return

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
