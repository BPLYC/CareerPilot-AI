"""Match scoring node."""

from src.agents.common import can_use_llm, invoke_structured
from src.models.schemas import MatchReport
from src.services.prompts import MATCH_SCORING_SYSTEM, schema_instruction
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
        weak_sections.append("Skill gaps in required technologies")
    if not resume_profile.get("work_experience"):
        weak_sections.append("Limited internship or work experience")
    if not relevant_projects:
        weak_sections.append("Few clearly relevant projects")

    return model_to_dict(
        MatchReport(
            overall_score=total,
            matched_skills=matched,
            missing_skills=missing,
            relevant_projects=relevant_projects,
            weak_sections=weak_sections,
            explanation=f"The resume matches {len(matched)} required skills and misses {len(missing)}. The score reflects skill overlap, project relevance, education, and experience evidence.",
        )
    )


def match_scoring_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    try:
        if can_use_llm():
            user_prompt = (
                schema_instruction(
                    "MatchReport",
                    "overall_score,matched_skills,missing_skills,relevant_projects,weak_sections,explanation",
                )
                + f"\nResume profile:\n{resume_profile}\nJD analysis:\n{jd_analysis}\nRetrieved context:\n{state.get('retrieved_context', {})}"
            )
            report = invoke_structured(MatchReport, MATCH_SCORING_SYSTEM, user_prompt)
        else:
            report = fallback_score_match(resume_profile, jd_analysis)
        report = model_to_dict(validate_dict(MatchReport, report))
        warnings = []
        if report["overall_score"] < 45:
            warnings.append(
                f"Low match score ({report['overall_score']}/100). This JD may not be the best fit. Consider the suggestions in the report."
            )
        trace = (
            f"MatchScoringNode: Score = {report['overall_score']}/100. "
            f"{len(report['matched_skills'])} matched skills, {len(report['missing_skills'])} missing skills."
        )
        return {"match_report": report, "warnings": warnings, "workflow_trace": [trace]}
    except Exception as exc:
        report = fallback_score_match(resume_profile, jd_analysis)
        return {
            "match_report": report,
            "errors": [f"MatchScoringNode failed and used fallback scoring: {exc}"],
            "workflow_trace": ["MatchScoringNode: Fallback scoring completed."],
        }
