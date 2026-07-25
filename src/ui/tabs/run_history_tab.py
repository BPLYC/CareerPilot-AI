"""Run History tab: summary metadata for recent local runs."""

import streamlit as st

from src.services.run_history import list_recent_runs

COLUMNS = [
    ("时间", "created_at"),
    ("职位", "job_title"),
    ("评分", "match_score"),
    ("匹配技能", "matched_skills_count"),
    ("缺失技能", "missing_skills_count"),
    ("简历建议", "optimized_bullets_count"),
    ("申请回答", "application_answer_count"),
    ("面试问题", "interview_question_count"),
    ("警告", "warnings_count"),
    ("错误", "errors_count"),
]


def to_rows(runs: list[dict]) -> list[dict]:
    return [{label: run[key] for label, key in COLUMNS} for run in runs]


def render(limit: int = 10) -> None:
    st.markdown("#### 最近的本地运行记录")
    try:
        runs = list_recent_runs(limit=limit)
    except Exception as exc:
        runs = []
        st.warning(f"无法加载运行历史：{exc}")

    if not runs:
        st.info("运行一次分析后，这里会显示本地历史记录。")
        return

    st.caption("历史记录仅保存摘要元数据，不会保存原始简历和职位描述。")
    st.dataframe(to_rows(runs), use_container_width=True, hide_index=True)
