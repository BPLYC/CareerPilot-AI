"""Evaluation metric helpers."""

from src.services.scoring import keyword_coverage, skill_match_rate, star_coverage_rate


def evaluate_state(state: dict) -> dict:
    jd = state.get("jd_analysis") or {}
    resume = state.get("resume_profile") or {}
    report = state.get("match_report") or {}
    bullets = [item.get("optimized_bullet", "") for item in state.get("optimized_bullets", [])]
    optimized_text = " ".join(bullets)
    revised = [item for item in state.get("optimized_bullets", []) if item.get("is_revised_by_reflection")]
    bullet_count = len(bullets)
    application_answers = [value for value in (state.get("application_answers") or {}).values() if value]
    interview_questions = state.get("interview_questions", [])
    return {
        "keyword_coverage_before": keyword_coverage(state.get("raw_resume_text", ""), jd.get("keywords", [])),
        "keyword_coverage_after": keyword_coverage(optimized_text, jd.get("keywords", [])),
        "required_skills_match_rate": skill_match_rate(resume.get("skills", []), jd.get("required_skills", [])),
        "missing_skills_count": len(report.get("missing_skills", [])),
        "bullet_count_generated": bullet_count,
        "reflection_revision_rate": (len(revised) / bullet_count) if bullet_count else 0.0,
        "star_coverage_rate": star_coverage_rate(bullets),
        "application_answer_count": len(application_answers),
        "interview_question_count": len(interview_questions),
    }
