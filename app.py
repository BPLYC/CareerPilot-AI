"""Streamlit entrypoint for CareerPilot AI.

Assembly only. Each tab lives in src/ui/tabs/.
"""

import streamlit as st

from src.ui.sidebar import render_sidebar
from src.ui.tabs import (
    application_tab,
    compare_tab,
    input_tab,
    match_report_tab,
    resume_tips_tab,
    run_history_tab,
    workflow_trace_tab,
)

TAB_LABELS = [
    "信息输入",
    "匹配报告",
    "简历优化",
    "申请与面试",
    "职位对比",
    "工作流记录",
    "运行历史",
]


def main() -> None:
    st.set_page_config(page_title="CareerPilot AI", layout="wide")

    settings = render_sidebar()

    st.title("CareerPilot AI")
    st.caption("基于 LangGraph 的多智能体 RAG 简历与职位匹配系统")

    tabs = st.tabs(TAB_LABELS)

    with tabs[0]:
        input_tab.render(settings)

    # Read after the input tab runs, so a fresh analysis shows up in the same
    # pass rather than only after the next interaction.
    state = st.session_state.get("last_result")

    with tabs[1]:
        match_report_tab.render(state)
    with tabs[2]:
        resume_tips_tab.render(state)
    with tabs[3]:
        application_tab.render(state)
    with tabs[4]:
        compare_tab.render(settings)
    with tabs[5]:
        workflow_trace_tab.render(state)
    with tabs[6]:
        run_history_tab.render()


if __name__ == "__main__":
    main()
