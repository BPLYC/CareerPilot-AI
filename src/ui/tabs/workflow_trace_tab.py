"""Workflow Trace tab: per-node trace, errors, and the raw state."""

import streamlit as st


def render(state: dict | None) -> None:
    if not state:
        st.info("Run the analysis first.")
        return

    st.markdown("#### Agent Workflow Trace")
    for index, trace in enumerate(state.get("workflow_trace", []), start=1):
        st.text(f"Step {index}: {trace}")

    if state.get("errors"):
        st.markdown("#### Errors")
        for error in state["errors"]:
            st.error(error)

    with st.expander("View Full State JSON"):
        st.json(state)
