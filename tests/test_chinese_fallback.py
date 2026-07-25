from src.agents.jd_analyzer_agent import fallback_analyze_jd
from src.agents.match_scoring_agent import fallback_score_match
from src.agents.resume_parser_agent import fallback_parse_resume


def test_chinese_ai_jd_and_resume_share_canonical_skills():
    resume = (
        "技能：Python、RAG、LangChain、Agent 开发\n"
        "项目：基于 LangGraph 构建智能体应用，并完成大模型检索增强。"
    )
    jd = (
        "AI 大模型应用开发实习生\n"
        "参与模型微调、RAG 检索和 Agent 应用开发，使用大数据处理框架 Spark/Hadoop/Hive。"
    )

    profile = fallback_parse_resume(resume)
    analysis = fallback_analyze_jd(jd)
    report = fallback_score_match(profile, analysis)

    assert {"RAG", "Agent"} <= set(profile["skills"])
    assert {"RAG", "Agent", "Spark", "Hadoop", "Hive"} <= set(analysis["required_skills"])
    assert {"RAG", "Agent"} <= set(report["matched_skills"])
    assert report["overall_score"] > 8
