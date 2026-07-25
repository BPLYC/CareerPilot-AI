"""Match Report tab: score, matched and missing skills, explanation."""

import streamlit as st

from src.services.report_export import build_markdown_report, suggested_filename


def render(state: dict | None) -> None:
    if not state or not state.get("match_report"):
        st.info("请先运行分析。")
        return

    report = state["match_report"]
    fallback_nodes = set(state.get("fallback_nodes", []))
    offline_score = "MatchScoringNode" in fallback_nodes
    if fallback_nodes:
        st.warning(
            "本次分析有部分节点无法调用大模型，已采用离线规则。"
            "离线评分仅供排查参考，请先确认简历解析完整后再判断匹配程度。"
        )

    st.download_button(
        "下载完整报告（Markdown）",
        data=build_markdown_report(state),
        file_name=suggested_filename(state),
        mime="text/markdown",
        use_container_width=True,
        help="包含匹配报告、简历要点建议、申请回答和面试问题。",
    )
    reference = state.get("reference_score")
    score = report["overall_score"]
    show_reference = reference is not None and reference != score

    if show_reference:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("AI 评分", f"{score}/100")
        col2.metric("规则基准评分", f"{reference}/100")
        col3.metric("匹配技能", len(report["matched_skills"]))
        col4.metric("缺失技能", len(report["missing_skills"]))
        st.caption(
            "这里同时展示 AI 评估和确定性规则基准评分。两者通常会有差异；"
            "当分差较大时，下方的匹配与缺失技能更值得参考。"
        )
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("离线规则评分" if offline_score else "匹配评分", f"{score}/100")
        col2.metric("匹配技能", len(report["matched_skills"]))
        col3.metric("缺失技能", len(report["missing_skills"]))
    st.progress(score / 100)

    for warning in state.get("warnings", []):
        st.warning(warning)

    breakdown = report.get("score_breakdown") or {}
    if breakdown:
        labels = {
            "required_skills": "必需技能",
            "preferred_skills": "加分技能",
            "project_evidence": "相关项目",
            "experience_evidence": "相关经历",
            "education": "教育要求",
        }
        st.markdown("#### 评分明细")
        st.dataframe(
            [{"评分项": labels.get(key, key), "得分": value} for key, value in breakdown.items()],
            width="stretch",
            hide_index=True,
        )
    if report.get("score_reliable") is False:
        st.info("职位描述未识别出明确的必需技能，因此本次分数为暂定值，工作流不会据此提前停止。")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 匹配技能")
        for skill in report["matched_skills"]:
            st.success(skill)
    with col2:
        st.markdown("#### 缺失技能")
        for skill in report["missing_skills"]:
            st.error(skill)

    st.markdown("#### 分析说明")
    st.write(report["explanation"])
