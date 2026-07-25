"""Reflection node for factual consistency checks."""

import re

from src.services.scoring import matched_and_missing_skills
from src.utils.text_utils import contains_keyword


def _unsupported_metric(bullet: str, resume_text: str) -> bool:
    metrics = re.findall(r"\b\d+(?:\.\d+)?%|\b\d+x\b|\$\d+", bullet or "", flags=re.IGNORECASE)
    return any(metric not in (resume_text or "") for metric in metrics)


def _unsupported_skills(bullet: str, resume_profile: dict, jd_analysis: dict) -> list[str]:
    candidates = (jd_analysis.get("required_skills", []) or []) + (jd_analysis.get("preferred_skills", []) or [])
    mentioned = [skill for skill in candidates if contains_keyword(bullet, skill)]
    _, unsupported = matched_and_missing_skills(resume_profile.get("skills", []), mentioned)
    return unsupported


def _unsupported_context(context: str, resume_profile: dict) -> bool:
    if not context:
        return False
    supported = {
        str(value).strip().lower()
        for item in (resume_profile.get("projects", []) or []) + (resume_profile.get("work_experience", []) or [])
        for value in (item.get("name"), item.get("role"), item.get("company"))
        if value and str(value).strip().lower() != "unknown"
    }
    return context.strip().lower() not in supported


def reflection_node(state) -> dict:
    bullets = state.get("optimized_bullets", [])
    resume_text = state.get("raw_resume_text", "")
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    iteration = state.get("reflection_iteration", 0)
    issues = []
    for index, bullet in enumerate(bullets, start=1):
        text = bullet.get("optimized_bullet", "")
        if _unsupported_metric(text, resume_text):
            issues.append(f"建议 {index} 包含简历中不存在的指标。")
        unsupported_skills = _unsupported_skills(text, resume_profile, jd_analysis)
        if unsupported_skills:
            issues.append(f"建议 {index} 包含简历中不存在的技能：{', '.join(unsupported_skills)}。")
        if _unsupported_context(bullet.get("context", ""), resume_profile):
            issues.append(f"建议 {index} 引用了简历中不存在的项目或经历。")

    if issues and iteration < 2:
        next_iteration = iteration + 1
        return {
            "has_exaggeration": True,
            "reflection_feedback": " ".join(issues) + " 请去除未经支持的数字或表述后重新生成。",
            "reflection_iteration": next_iteration,
            "workflow_trace": [f"ReflectionNode（第 {next_iteration} 轮）：发现 {len(issues)} 个问题，正在修订。"],
        }

    finalized = []
    for bullet in bullets:
        updated = dict(bullet)
        if iteration > 0:
            updated["is_revised_by_reflection"] = True
        finalized.append(updated)
    feedback = "已达到最大修订轮数。" if issues else "已通过事实审查。"
    return {
        "has_exaggeration": False,
        "reflection_feedback": feedback,
        "optimized_bullets": finalized,
        "workflow_trace": [f"ReflectionNode（第 {iteration} 轮）：发现 {len(issues)} 个问题，正在完成输出。"],
    }
