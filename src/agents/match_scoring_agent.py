"""Match scoring node."""

from src.agents.common import invoke_structured, run_node
from src.models.schemas import MatchReport
from src.services.prompts import MATCH_SCORING_SYSTEM, context_block, schema_instruction
from src.services.scoring import keyword_coverage, matched_and_missing_skills, skill_match_rate
from src.services.structured_output import model_to_dict, validate_dict


def fallback_score_match(resume_profile: dict, jd_analysis: dict) -> dict:
    skills = resume_profile.get("skills", [])
    required = jd_analysis.get("required_skills", [])
    matched, missing = matched_and_missing_skills(skills, required)
    skill_score = skill_match_rate(skills, required) * 40

    projects = resume_profile.get("projects", [])
    responsibilities_text = " ".join(jd_analysis.get("responsibilities", []) + jd_analysis.get("keywords", []))
    relevant_projects = []
    for project in projects:
        project_text = " ".join([project.get("name", ""), project.get("description", "")] + project.get("technologies", []))
        if keyword_coverage(project_text + " " + responsibilities_text, jd_analysis.get("keywords", [])) > 0:
            relevant_projects.append(project.get("name", "unknown project"))
    project_score = min(30, len(relevant_projects) * 10)
    education_score = 15 if resume_profile.get("education") else 8
    experience_score = min(15, len(resume_profile.get("work_experience", [])) * 8 + len(projects) * 2)
    total = max(0, min(100, round(skill_score + project_score + education_score + experience_score)))

    weak_sections = []
    if missing:
        weak_sections.append("必需技术存在技能缺口")
    if not resume_profile.get("work_experience"):
        weak_sections.append("实习或工作经历较少")
    if not relevant_projects:
        weak_sections.append("与职位直接相关的项目较少")

    return model_to_dict(
        MatchReport(
            overall_score=total,
            matched_skills=matched,
            missing_skills=missing,
            relevant_projects=relevant_projects,
            weak_sections=weak_sections,
            explanation=(
                f"简历匹配 {len(matched)} 项必需技能，缺失 {len(missing)} 项。"
                "评分综合考虑技能重合度、项目相关性、教育背景和经历证据。"
            ),
        )
    )


LOW_MATCH_THRESHOLD = 45

# How far the model score may sit from the deterministic baseline before the UI
# warns. Measured on the sample data, the model runs 13-28 points below the
# baseline, so 20 flags the wide cases (SWE 22, AI up to 28) while leaving the
# routine offset (Data Analyst 14-19) to the quieter side-by-side display.
SCORE_GAP_THRESHOLD = 20


def _describe(report: dict) -> str:
    return (
        f"评分 {report['overall_score']}/100，"
        f"匹配 {len(report['matched_skills'])} 项技能，缺失 {len(report['missing_skills'])} 项技能。"
    )


def _score_warnings(report: dict, reference: int) -> list[str]:
    warnings = []
    if report["overall_score"] < LOW_MATCH_THRESHOLD:
        warnings.append(
            f"匹配评分较低（{report['overall_score']}/100）。该职位可能不是当前最合适的选择，"
            "请结合报告中的技能缺口和建议综合判断。"
        )
    gap = abs(report["overall_score"] - reference)
    if gap >= SCORE_GAP_THRESHOLD:
        warnings.append(
            f"AI 评分（{report['overall_score']}/100）与规则基准评分（{reference}/100）"
            f"相差 {gap} 分。请将分数视为近似参考，并优先关注更稳定的匹配与缺失技能。"
        )
    return warnings


def match_scoring_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}

    # Always computed, even on the LLM path, so the model's number can be shown
    # against a stable baseline. On the fallback path the model IS this scorer,
    # so the two agree and nothing extra surfaces.
    reference = fallback_score_match(resume_profile, jd_analysis)["overall_score"]

    def from_llm() -> dict:
        user_prompt = (
            schema_instruction(
                "MatchReport",
                "overall_score,matched_skills,missing_skills,relevant_projects,weak_sections,explanation",
            )
            + "\n"
            + context_block(
                resume_profile=resume_profile,
                jd_analysis=jd_analysis,
                retrieved_context=state.get("retrieved_context", {}),
            )
        )
        return invoke_structured(MatchReport, MATCH_SCORING_SYSTEM, user_prompt)

    return run_node(
        node_name="MatchScoringNode",
        output_key="match_report",
        llm_branch=from_llm,
        fallback_branch=lambda: fallback_score_match(resume_profile, jd_analysis),
        describe=_describe,
        refine=lambda report: model_to_dict(validate_dict(MatchReport, report)),
        extra_state=lambda report: {
            "reference_score": reference,
            "warnings": _score_warnings(report, reference),
        },
    )
