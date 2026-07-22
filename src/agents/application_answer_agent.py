"""Application answer drafting node."""

from src.agents.common import can_use_llm, invoke_structured
from src.models.schemas import ApplicationAnswerSet, ApplicationQuestionAnswer
from src.services.prompts import APPLICATION_ANSWER_SYSTEM, schema_instruction
from src.services.structured_output import model_to_dict

SENSITIVE_NOTICE = (
    "Visa, work authorization, sponsorship, salary, and legal eligibility answers "
    "must be filled by the applicant directly."
)
SENSITIVE_TERMS = (
    "visa",
    "work authorization",
    "authorization",
    "authorized",
    "sponsorship",
    "sponsor",
    "salary",
    "compensation",
    "eligible",
    "eligibility",
    "legal",
)


def _join(items: list[str], fallback: str) -> str:
    return ", ".join(items[:4]) if items else fallback


def is_sensitive_question(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in SENSITIVE_TERMS)


def _custom_answer(
    question: str,
    role: str,
    matched: str,
    project_name: str,
    project_description: str,
) -> dict:
    if is_sensitive_question(question):
        answer = SENSITIVE_NOTICE
        notice = SENSITIVE_NOTICE
    else:
        project_note = f" For a concrete example, I would discuss {project_name}."
        if project_description:
            project_note += f" {project_description}"
        answer = (
            f"Draft starter: I would answer by connecting {role} to verified resume evidence in {matched}."
            f"{project_note}"
        )
        notice = f"Draft only. Personalize tone and exact wording before submitting. {SENSITIVE_NOTICE}"

    return model_to_dict(
        ApplicationQuestionAnswer(
            question=question,
            answer=answer,
            review_notice=notice,
        )
    )


def fallback_application_answers(
    resume_profile: dict,
    jd_analysis: dict,
    match_report: dict,
    application_questions: list[str] | None = None,
) -> dict:
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
        custom_answers=[
            _custom_answer(question, role, matched, project_name, project_description)
            for question in (application_questions or [])
        ],
        review_notice=f"Draft only. Personalize tone and examples before submitting. {SENSITIVE_NOTICE}",
    )
    return model_to_dict(answers)


def enforce_sensitive_question_boundaries(answers: dict, application_questions: list[str]) -> dict:
    if not application_questions:
        return answers

    custom_answers = {item.get("question", ""): dict(item) for item in answers.get("custom_answers", [])}
    sanitized = []
    for question in application_questions:
        item = custom_answers.get(question, {"question": question, "answer": "", "review_notice": ""})
        if is_sensitive_question(question):
            item["answer"] = SENSITIVE_NOTICE
            item["review_notice"] = SENSITIVE_NOTICE
        sanitized.append(
            model_to_dict(
                ApplicationQuestionAnswer(
                    question=question,
                    answer=item.get("answer") or "Draft starter unavailable. Answer this manually with verified facts.",
                    review_notice=item.get("review_notice") or "Review and personalize before submitting.",
                )
            )
        )

    updated = dict(answers)
    updated["custom_answers"] = sanitized
    return updated


def application_answer_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    match_report = state.get("match_report") or {}
    application_questions = state.get("application_questions") or []
    try:
        if can_use_llm():
            user_prompt = (
                schema_instruction(
                    "ApplicationAnswerSet",
                    "why_this_role,key_strengths,project_example,custom_answers,review_notice",
                )
                + "\nUse only verified evidence. Do not answer sensitive eligibility questions.\n"
                + "For each requested application question, add one custom_answers item with question, answer, and review_notice.\n"
                f"Resume profile: {resume_profile}\nJD analysis: {jd_analysis}\n"
                f"Match report: {match_report}\nApplication questions: {application_questions}\n"
                f"RAG context: {state.get('retrieved_context', {})}"
            )
            answers = invoke_structured(ApplicationAnswerSet, APPLICATION_ANSWER_SYSTEM, user_prompt)
        else:
            answers = fallback_application_answers(resume_profile, jd_analysis, match_report, application_questions)
        answers = enforce_sensitive_question_boundaries(answers, application_questions)
        return {
            "application_answers": answers,
            "workflow_trace": ["ApplicationAnswerNode: Drafted conservative application answer starters."],
        }
    except Exception as exc:
        answers = fallback_application_answers(resume_profile, jd_analysis, match_report, application_questions)
        return {
            "application_answers": answers,
            "errors": [f"ApplicationAnswerNode failed and used fallback answers: {exc}"],
            "workflow_trace": ["ApplicationAnswerNode: Fallback application answers completed."],
        }
