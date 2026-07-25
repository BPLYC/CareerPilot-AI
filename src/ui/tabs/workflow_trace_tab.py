"""Workflow Trace tab: per-node trace, errors, and the raw state."""

import streamlit as st


def render(state: dict | None) -> None:
    if not state:
        st.info("请先运行分析。")
        return

    st.markdown("#### 智能体工作流记录")
    for index, trace in enumerate(state.get("workflow_trace", []), start=1):
        st.text(f"步骤 {index}：{trace}")

    if state.get("errors"):
        st.markdown("#### 错误")
        for error in state["errors"]:
            st.error(error)

    with st.expander("查看完整状态 JSON"):
        st.json(state)
