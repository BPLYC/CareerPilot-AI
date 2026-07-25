"""Low-match conditional node."""


def low_match_warning_node(state) -> dict:
    report = state.get("match_report") or {}
    missing = report.get("missing_skills", [])[:5]
    advice = "关键缺失技能：" + (", ".join(missing) if missing else "未发现足够明确的职位重合信息")
    warning = (
        f"{advice}。可以围绕这些要求完成一个小型作品集项目，"
        "也可以优先考虑与当前背景更接近的职位。"
    )
    return {
        "warnings": [warning],
        "optimized_bullets": [],
        "workflow_trace": ["LowMatchWarningNode：评分低于阈值（45），已跳过简历优化，请查看警告中的后续建议。"],
    }
