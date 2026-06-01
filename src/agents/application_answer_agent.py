"""Application answer drafting node."""

from src.agents.common import can_use_llm, invoke_structured
from src.models.schemas import ApplicationAnswerSet
from src.services.prompts import APPLICATION_ANSWER_SYSTEM, schema_instruction
from src.services.structured_output import model_to_dict


SENSITIVE_NOTICE = (
    "Visa, work authorization, sponsorship, salary, and legal eligibility answers "
    "must be filled by the applicant directly."
)


def _join(items: list[str], fallback: str) -> str:
    return ", ".join(items[:4]) if items else fallback


def fallback_application_answers(resume_profile: dict, jd_analysis: dict, match_report: dict) -> dict:
    role = jd_analysis.get("job_title") or "this internship role"
    matched = _join(match_report.get("matched_skills", []), "the skills already shown in the resume")
    projects = resume_profile.get("projects", [])
    project_name = projects[0].get("name", "a relevant resume project") if projects else "a relevant resume project"
    project_description = projects[0].get("description", "") if projects else ""
    missing = match_report.get("missing_skills", [])
    growth_note = f" I am also actively strengthening {', '.join(missing[:2])}." if missing else ""

    answers = ApplicationAnswerSet(
        why_this_role=(
            f"I am interested in {role} because it connects directly with my existing experience in {matched}."
            f"{growth_note}"
        ),
        key_strengths=(
            f"My strongest fit is the hands-on evidence in my resume around {matched}, "
            "with examples I can discuss from coursework, projects, or internship work already listed."
        ),
        project_example=(
            f"One example I would highlight is {project_name}. {project_description}".strip()
        ),
        review_notice=f"Draft only. Personalize tone and examples before submitting. {SENSITIVE_NOTICE}",
    )
    return model_to_dict(answers)


def application_answer_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    match_report = state.get("match_report") or {}
    try:
        if can_use_llm():
            user_prompt = (
                schema_instruction(
                    "ApplicationAnswerSet",
                    "why_this_role,key_strengths,project_example,review_notice",
                )
                + "\nUse only verified evidence. Do not answer sensitive eligibility questions.\n"
                f"Resume profile: {resume_profile}\nJD analysis: {jd_analysis}\n"
                f"Match report: {match_report}\nRAG context: {state.get('retrieved_context', {})}"
            )
            answers = invoke_structured(ApplicationAnswerSet, APPLICATION_ANSWER_SYSTEM, user_prompt)
        else:
            answers = fallback_application_answers(resume_profile, jd_analysis, match_report)
        return {
            "application_answers": answers,
            "workflow_trace": ["ApplicationAnswerNode: Drafted conservative application answer starters."],
        }
    except Exception as exc:
        answers = fallback_application_answers(resume_profile, jd_analysis, match_report)
        return {
            "application_answers": answers,
            "errors": [f"ApplicationAnswerNode failed and used fallback answers: {exc}"],
            "workflow_trace": ["ApplicationAnswerNode: Fallback application answers completed."],
        }
