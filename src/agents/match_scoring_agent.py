"""Match scoring node."""

import re

from src.agents.common import invoke_structured, run_node
from src.models.schemas import MatchReport
from src.services.prompts import MATCH_SCORING_SYSTEM, context_block, schema_instruction
from src.services.scoring import keyword_coverage, matched_and_missing_skills, skill_match_rate
from src.services.skill_taxonomy import find_known_skills, transferable_skills
from src.services.structured_output import model_to_dict, validate_dict
from src.utils.text_utils import unique_preserve_order

BREAKDOWN_LIMITS = {
    "required_skills": 40,
    "preferred_skills": 10,
    "project_evidence": 25,
    "experience_evidence": 15,
    "education": 10,
}


def _evidence_text(item: dict) -> str:
    values = [
        item.get("name", ""),
        item.get("role", ""),
        item.get("description", ""),
        item.get("outcome", ""),
        " ".join(item.get("technologies", []) or []),
    ]
    return " ".join(value for value in values if value)


def _has_role_evidence(text: str, jd_analysis: dict) -> bool:
    target_skills = unique_preserve_order(
        (jd_analysis.get("required_skills", []) or [])
        + (jd_analysis.get("preferred_skills", []) or [])
        + (jd_analysis.get("tools_and_technologies", []) or [])
    )
    evidence_skills = find_known_skills(text)
    matched, _ = matched_and_missing_skills(evidence_skills, target_skills)
    if matched:
        return True
    useful_keywords = [
        term
        for term in jd_analysis.get("keywords", []) or []
        if term.lower() not in {"intern", "internship", "candidate", "team"}
    ]
    return keyword_coverage(text, useful_keywords) > 0


def _education_score(resume_profile: dict, jd_analysis: dict) -> int:
    requirement = (jd_analysis.get("education_requirements") or "").strip()
    level = jd_analysis.get("education_level")
    major = jd_analysis.get("education_major")
    graduation = jd_analysis.get("graduation_requirement")
    gpa = jd_analysis.get("gpa_requirement")
    is_required = jd_analysis.get("education_is_required")
    has_structured_requirement = any(value is not None for value in (level, major, graduation, gpa))
    if not requirement and not has_structured_requirement:
        return BREAKDOWN_LIMITS["education"]
    education = resume_profile.get("education") or []
    if not education:
        return 0 if is_required is not False else 5

    # Education evidence exists, but unknown fields are not treated as a match.
    if not has_structured_requirement:
        return 7

    def known(value) -> bool:
        return bool(value and str(value).strip().lower() not in {"unknown", "n/a", "none"})

    level_rank = {"associate": 1, "bachelor": 2, "master": 3, "doctorate": 4}

    def resume_level(degree: str) -> str | None:
        lowered = degree.lower()
        if re.search(r"\b(?:phd|doctorate|doctoral)\b|博士", lowered):
            return "doctorate"
        if re.search(r"\b(?:master|msc|ma|meng)\b|硕士|研究生", lowered):
            return "master"
        if re.search(r"\b(?:bachelor|bsc|bs|ba|beng)\b|本科|学士", lowered):
            return "bachelor"
        if re.search(r"\bassociate\b|专科|大专", lowered):
            return "associate"
        return None

    checks: list[bool | None] = []
    if level:
        observed = [resume_level(str(item.get("degree", ""))) for item in education]
        known_levels = [candidate for candidate in observed if candidate]
        checks.append(
            max((level_rank[candidate] for candidate in known_levels), default=0)
            >= level_rank.get(str(level).lower(), 99)
            if known_levels
            else None
        )
    if major:
        required_terms = {
            term
            for term in re.findall(r"[\w\u4e00-\u9fff]+", str(major).lower())
            if len(term) > 2 and term not in {"related", "field", "degree", "专业", "相关"}
        }
        observed_majors = [
            str(item.get("major", "")).lower() for item in education if known(item.get("major"))
        ]
        checks.append(
            any(any(term in observed for term in required_terms) for observed in observed_majors)
            if observed_majors and required_terms
            else None
        )
    if graduation:
        observed_dates = [
            str(item.get("graduation_date", "")) for item in education if known(item.get("graduation_date"))
        ]
        required_years = {int(year) for year in re.findall(r"20\d{2}", str(graduation))}
        observed_years = {int(year) for text in observed_dates for year in re.findall(r"20\d{2}", text)}
        if observed_years and required_years:
            low, high = min(required_years), max(required_years)
            checks.append(any(low <= year <= high for year in observed_years))
        else:
            checks.append(None)
    if gpa is not None:
        # Resume schema intentionally has no GPA field. Do not infer it from school or degree.
        checks.append(None)

    known_checks = [check for check in checks if check is not None]
    if False in known_checks:
        return 2 if is_required is not False else 5
    if known_checks and len(known_checks) == len(checks):
        return BREAKDOWN_LIMITS["education"]
    return 7


def fallback_score_match(resume_profile: dict, jd_analysis: dict) -> dict:
    skills = resume_profile.get("skills", [])
    required = jd_analysis.get("required_skills", [])
    matched, missing = matched_and_missing_skills(skills, required)
    preferred = jd_analysis.get("preferred_skills", [])
    skill_score = round(skill_match_rate(skills, required) * BREAKDOWN_LIMITS["required_skills"])
    preferred_score = round(skill_match_rate(skills, preferred) * BREAKDOWN_LIMITS["preferred_skills"])

    projects = resume_profile.get("projects", [])
    relevant_projects = [
        project.get("name", "unknown project")
        for project in projects
        if _has_role_evidence(_evidence_text(project), jd_analysis)
    ]
    project_score = min(BREAKDOWN_LIMITS["project_evidence"], len(relevant_projects) * 10)
    relevant_experience = [
        item
        for item in resume_profile.get("work_experience", [])
        if _has_role_evidence(_evidence_text(item), jd_analysis)
    ]
    experience_score = min(BREAKDOWN_LIMITS["experience_evidence"], len(relevant_experience) * 8)
    education_score = _education_score(resume_profile, jd_analysis)
    preferred_matched, _ = matched_and_missing_skills(skills, preferred)
    transfer_evidence = transferable_skills(skills, missing)
    breakdown = {
        "required_skills": skill_score,
        "preferred_skills": preferred_score,
        "project_evidence": project_score,
        "experience_evidence": experience_score,
        "education": education_score,
    }
    total = sum(breakdown.values())
    score_evidence = {
        "required_skills": matched or ["未找到明确匹配的必需技能"],
        "preferred_skills": preferred_matched or ["未找到明确匹配的加分技能"],
        "project_evidence": relevant_projects or ["未找到与职位直接相关的项目证据"],
        "experience_evidence": [
            item.get("role") or item.get("company") or "相关工作经历"
            for item in relevant_experience
        ] or ["未找到与职位直接相关的工作经历"],
        "education": [
            (
                "JD 未设置明确教育门槛"
                if not jd_analysis.get("education_requirements")
                else f"教育要求证据得分 {education_score}/{BREAKDOWN_LIMITS['education']}"
            )
        ],
    }
    score_reliable = bool(required)
    scoring_warnings = []
    if not score_reliable:
        scoring_warnings.append("职位描述未识别出必需技能，当前分数为暂定值，不应用于低匹配淘汰。")

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
                "总分由必需技能、加分技能、相关项目、相关工作经历和教育要求五个分项相加得到。"
            ),
            score_breakdown=breakdown,
            score_evidence=score_evidence,
            transferable_skills=transfer_evidence,
            score_reliable=score_reliable,
            scoring_warnings=scoring_warnings,
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
    warnings = list(report.get("scoring_warnings", []))
    if report.get("score_reliable", True) and report["overall_score"] < LOW_MATCH_THRESHOLD:
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


def _normalize_scored_report(report: dict) -> dict:
    report = model_to_dict(validate_dict(MatchReport, report))
    breakdown = report.get("score_breakdown") or {}
    if set(BREAKDOWN_LIMITS) <= set(breakdown):
        normalized = {
            name: max(0, min(limit, int(breakdown.get(name, 0))))
            for name, limit in BREAKDOWN_LIMITS.items()
        }
        report["score_breakdown"] = normalized
        report["overall_score"] = sum(normalized.values())
    return report


def match_scoring_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}

    # Always computed, even on the LLM path, so the model's number can be shown
    # against a stable baseline. On the fallback path the model IS this scorer,
    # so the two agree and nothing extra surfaces.
    reference_report = fallback_score_match(resume_profile, jd_analysis)
    reference = reference_report["overall_score"]

    def from_llm() -> dict:
        user_prompt = (
            schema_instruction(
                "MatchReport",
                "overall_score,matched_skills,missing_skills,relevant_projects,weak_sections,explanation,"
                "score_breakdown,score_evidence,transferable_skills,score_reliable,scoring_warnings",
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
        refine=_normalize_scored_report,
        extra_state=lambda report: {
            "reference_score": reference,
            "routing_score": reference if reference_report["score_reliable"] else None,
            "warnings": _score_warnings(report, reference),
        },
    )
