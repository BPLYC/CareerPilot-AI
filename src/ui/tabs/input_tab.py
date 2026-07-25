"""Input tab: resume upload or paste, job description, optional questions."""

import streamlit as st

from src.parsers.file_parser import parse_resume_file
from src.ui.analysis import run_analysis


def split_questions(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def render(settings) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("你的简历")
        resume_file = st.file_uploader("上传简历（TXT、PDF 或 DOCX）", type=["txt", "pdf", "docx"])
        pasted_resume = st.text_area(
            "或在此粘贴简历文本",
            height=330,
            value=st.session_state.get("sample_resume", ""),
        )
    with col2:
        st.subheader("职位描述")
        jd_text = st.text_area("在此粘贴职位描述", height=390, value=st.session_state.get("sample_jd", ""))

    application_question_text = st.text_area(
        "可选：申请问题",
        height=120,
        placeholder="每行输入一个问题，例如：你为什么对这个实习职位感兴趣？",
    )

    if not st.button("开始 CareerPilot 分析", type="primary", use_container_width=True):
        return

    try:
        file_text = parse_resume_file(resume_file) if resume_file else ""
        resume_text = file_text or pasted_resume
        if not resume_text.strip() or not jd_text.strip():
            st.error("请同时提供简历和职位描述。")
            return
        st.session_state["last_result"] = run_analysis(
            resume_text,
            jd_text,
            split_questions(application_question_text),
            settings=settings,
        )
    except Exception as exc:
        st.error(f"分析失败：{exc}")
