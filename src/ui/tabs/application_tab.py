"""Application & Interview tab: answer starters and practice questions."""

import streamlit as st

ANSWER_LABELS = {
    "why_this_role": "为什么选择这个职位",
    "key_strengths": "核心优势",
    "project_example": "项目示例",
}

SENSITIVE_REMINDER = "签证、工作许可和薪酬等敏感问题请务必由本人填写。"


def render(state: dict | None) -> None:
    if not state:
        st.info("请先运行分析。")
        return

    answers = state.get("application_answers") or {}
    questions = state.get("interview_questions") or []

    if not answers and not questions:
        st.info("当简历与职位达到可申请的匹配程度后，系统会提供申请与面试准备内容。")
        return

    if answers:
        st.warning(answers.get("review_notice", "以下仅为草稿，请在提交前检查并结合个人情况修改。"))
        st.markdown("#### 申请回答思路")
        for key, label in ANSWER_LABELS.items():
            if answers.get(key):
                st.markdown(f"**{label}**")
                st.write(answers[key])

        custom_answers = answers.get("custom_answers", [])
        if custom_answers:
            st.markdown("#### 自定义申请问题")
            for item in custom_answers:
                with st.expander(item.get("question", "申请问题"), expanded=True):
                    st.write(item.get("answer", ""))
                    if item.get("review_notice"):
                        st.caption(item["review_notice"])

    if questions:
        st.markdown("#### 面试练习")
        for index, question in enumerate(questions, start=1):
            with st.expander(f"问题 {index}：{question.get('focus_area', '练习')}"):
                st.write(question.get("question", ""))
                if question.get("prep_notes"):
                    st.caption(question["prep_notes"])

    # Only shown alongside actual drafts. It used to render unconditionally,
    # including before any analysis had run, where it warned about content that
    # was not on screen.
    st.warning(SENSITIVE_REMINDER)
