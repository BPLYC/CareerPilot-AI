"""Resume Tips tab: before/after bullet suggestions."""

import streamlit as st


def render(state: dict | None) -> None:
    if not state or not state.get("optimized_bullets"):
        st.info("请先运行分析；如果匹配度较低，请查看“匹配报告”中的提示。")
        return

    st.warning("以下内容由 AI 生成，请在提交前仔细检查并结合个人情况修改。")
    if state.get("reflection_iteration", 0) > 0:
        st.info(f"反思节点审查结果：{state.get('reflection_feedback', '')}")

    for index, bullet in enumerate(state["optimized_bullets"], start=1):
        with st.expander(f"{bullet['context']} - 建议 {index}", expanded=True):
            if bullet.get("original_bullet"):
                st.markdown("**修改前：**")
                st.text(bullet["original_bullet"])
            st.markdown("**修改后：**")
            st.markdown(f"> {bullet['optimized_bullet']}")
            st.caption(bullet["rationale"])
