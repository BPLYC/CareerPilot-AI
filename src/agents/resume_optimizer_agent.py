"""Resume optimizer node."""

from src.agents.common import can_use_llm, invoke_structured
from src.models.schemas import BulletSuggestion
from src.services.prompts import RESUME_OPTIMIZER_SYSTEM
from src.services.structured_output import loads_json, model_to_dict, validate_dict


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
        context = item.get("name") or item.get("role") or item.get("company") or "Resume experience"
        techs = item.get("technologies", []) or resume_profile.get("skills", [])[:3]
        tech_text = ", ".join(techs[:3]) if techs else "relevant tools"
        keyword_text = ", ".join(keywords) if keywords else "the target role"
        bullet = (
            f"Developed and documented {context} using {tech_text}, highlighting experience aligned with {keyword_text}."
        )
        if reflection_feedback:
            bullet = (
                f"Contributed to {context} using {tech_text}, keeping the description limited to confirmed resume evidence."
            )
        suggestion = BulletSuggestion(
            context=context,
            original_bullet=item.get("description", ""),
            optimized_bullet=bullet,
            rationale="Connects existing resume evidence to JD keywords without adding unsupported metrics.",
        )
        suggestions.append(model_to_dict(suggestion))
    return suggestions


def resume_optimizer_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    match_report = state.get("match_report") or {}
    feedback = state.get("reflection_feedback", "")
    iteration = state.get("reflection_iteration", 0)
    try:
        if can_use_llm():
            user_prompt = (
                "Return a JSON array of BulletSuggestion objects. "
                "Use only facts from the resume profile. Do not add unsupported numbers.\n"
                f"Resume profile: {resume_profile}\nJD analysis: {jd_analysis}\nMatch report: {match_report}\n"
                f"RAG context: {state.get('retrieved_context', {})}\nReflection feedback: {feedback}"
            )
            raw = invoke_structured_array(user_prompt)
            suggestions = [model_to_dict(validate_dict(BulletSuggestion, item)) for item in raw]
        else:
            suggestions = fallback_optimize(resume_profile, jd_analysis, match_report, feedback)
        trace = f"ResumeOptimizerNode (Iteration {iteration}): Generated {len(suggestions)} bullet suggestions."
        return {"optimized_bullets": suggestions, "workflow_trace": [trace]}
    except Exception as exc:
        suggestions = fallback_optimize(resume_profile, jd_analysis, match_report, feedback)
        return {
            "optimized_bullets": suggestions,
            "errors": [f"ResumeOptimizerNode failed and used fallback optimizer: {exc}"],
            "workflow_trace": [f"ResumeOptimizerNode (Iteration {iteration}): Fallback generated {len(suggestions)} suggestions."],
        }


def invoke_structured_array(user_prompt: str) -> list[dict]:
    from src.services.llm_client import get_llm

    llm = get_llm()
    response = llm.invoke([("system", RESUME_OPTIMIZER_SYSTEM), ("human", user_prompt)])
    content = getattr(response, "content", response)
    parsed = loads_json(str(content))
    if isinstance(parsed, dict) and "items" in parsed:
        return parsed["items"]
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array for bullet suggestions.")
    return parsed
