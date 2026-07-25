"""Resume optimizer node."""

from src.agents.common import invoke_structured_list, run_node
from src.models.schemas import BulletSuggestion
from src.services.prompts import RESUME_OPTIMIZER_SYSTEM, context_block
from src.services.structured_output import model_to_dict, validate_dict


def _source_items(resume_profile: dict, match_report: dict) -> list[dict]:
    relevant = set(match_report.get("relevant_projects", []))
    items = []
    for project in resume_profile.get("projects", []):
        if not relevant or project.get("name") in relevant:
            items.append({"type": "project", **project})
    for work in resume_profile.get("work_experience", []):
        items.append({"type": "work", "name": work.get("role", "Work Experience"), **work})
    return items[:4]


def fallback_optimize(resume_profile: dict, jd_analysis: dict, match_report: dict, reflection_feedback: str = "") -> list[dict]:
    keywords = jd_analysis.get("keywords", [])[:3]
    suggestions = []
    for item in _source_items(resume_profile, match_report):
        context = item.get("name") or item.get("role") or item.get("company") or "简历经历"
        techs = item.get("technologies", []) or resume_profile.get("skills", [])[:3]
        tech_text = ", ".join(techs[:3]) if techs else "相关工具"
        keyword_text = ", ".join(keywords) if keywords else "目标职位"
        bullet = (
            f"使用 {tech_text} 开发并记录“{context}”，突出与“{keyword_text}”相关的已有经历。"
        )
        if reflection_feedback:
            bullet = (
                f"使用 {tech_text} 参与“{context}”，描述严格限定在简历已确认的事实范围内。"
            )
        suggestion = BulletSuggestion(
            context=context,
            original_bullet=item.get("description", ""),
            optimized_bullet=bullet,
            rationale="将简历中的已有证据与职位关键词关联，不添加未经支持的指标。",
        )
        suggestions.append(model_to_dict(suggestion))
    return suggestions


def resume_optimizer_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    match_report = state.get("match_report") or {}
    feedback = state.get("reflection_feedback", "")
    iteration = state.get("reflection_iteration", 0)

    def from_llm() -> list[dict]:
        user_prompt = (
            "Return a JSON array of BulletSuggestion objects. "
            "Use only facts from the resume profile. Do not add unsupported numbers.\n"
            + context_block(
                resume_profile=resume_profile,
                jd_analysis=jd_analysis,
                match_report=match_report,
                rag_context=state.get("retrieved_context", {}),
                reflection_feedback=feedback,
            )
        )
        raw = invoke_structured_list(RESUME_OPTIMIZER_SYSTEM, user_prompt, "bullet suggestions")
        return [model_to_dict(validate_dict(BulletSuggestion, item)) for item in raw]

    return run_node(
        node_name=f"ResumeOptimizerNode (Iteration {iteration})",
        output_key="optimized_bullets",
        llm_branch=from_llm,
        fallback_branch=lambda: fallback_optimize(resume_profile, jd_analysis, match_report, feedback),
        describe=lambda bullets: f"已生成 {len(bullets)} 条简历要点建议。",
    )
