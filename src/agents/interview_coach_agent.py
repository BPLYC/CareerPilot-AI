"""Interview preparation node."""

from src.agents.common import can_use_llm
from src.models.schemas import InterviewQuestion
from src.services.prompts import INTERVIEW_COACH_SYSTEM
from src.services.structured_output import loads_json, model_to_dict, validate_dict


def _project_questions(projects: list[dict]) -> list[dict]:
    questions = []
    for project in projects[:2]:
        name = project.get("name", "your project")
        technologies = ", ".join(project.get("technologies", [])[:4])
        tech_note = f" Be ready to explain {technologies}." if technologies else ""
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question=f"Walk me through {name}. What problem did it solve, and what tradeoffs did you make?",
                    focus_area="Project deep dive",
                    prep_notes=f"Use only implementation details and outcomes already present in your resume.{tech_note}",
                )
            )
        )
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question=f"What would you improve or measure next in {name}?",
                    focus_area="Project follow-up",
                    prep_notes="Ground the answer in the current project scope; do not add unbuilt features as if they already exist.",
                )
            )
        )
    return questions


def _role_specific_questions(jd_analysis: dict) -> list[dict]:
    title = (jd_analysis.get("job_title") or "").lower()
    evidence = " ".join(
        jd_analysis.get("required_skills", [])
        + jd_analysis.get("tools_and_technologies", [])
        + jd_analysis.get("keywords", [])
    ).lower()
    questions = []

    if any(term in title + " " + evidence for term in ["machine learning", "ml", "ai", "pytorch", "tensorflow"]):
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="How would you evaluate whether a model improvement is real and not just noise?",
                    focus_area="ML evaluation",
                    prep_notes="Use validation data, metrics, error analysis, and examples from projects you actually completed.",
                )
            )
        )

    if any(term in title + " " + evidence for term in ["data analyst", "analytics", "sql", "dashboard", "tableau"]):
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="How would you check whether a dashboard metric is trustworthy?",
                    focus_area="Analytics validation",
                    prep_notes="Discuss source data, joins, filters, edge cases, and sanity checks you have used before.",
                )
            )
        )

    if any(term in title + " " + evidence for term in ["software", "backend", "api", "flask", "docker", "rest"]):
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="How would you debug a failing API endpoint in a deployed internship project?",
                    focus_area="Software engineering",
                    prep_notes="Walk through logs, reproduction steps, request data, dependencies, and a small verified fix.",
                )
            )
        )

    return questions


def fallback_interview_questions(resume_profile: dict, jd_analysis: dict, retrieved_context: dict) -> list[dict]:
    questions = _project_questions(resume_profile.get("projects", []))
    questions.extend(_role_specific_questions(jd_analysis))
    for skill in jd_analysis.get("required_skills", [])[:3]:
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question=f"How have you used {skill} in a project or class assignment?",
                    focus_area="Required skill evidence",
                    prep_notes="Prepare a STAR-style answer grounded in a real resume example.",
                )
            )
        )

    bank = " ".join(retrieved_context.get("interview_bank", []))
    if "unclear requirements" in bank.lower():
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="How do you handle unclear requirements?",
                    focus_area="Behavioral",
                    prep_notes="Describe the clarification steps you actually used in a past project.",
                )
            )
        )

    if not questions:
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question="Tell me about a technical project from your resume.",
                    focus_area="General",
                    prep_notes="Pick one real project and prepare the situation, task, action, and result.",
                )
            )
        )
    return questions[:6]


def interview_coach_node(state) -> dict:
    resume_profile = state.get("resume_profile") or {}
    jd_analysis = state.get("jd_analysis") or {}
    retrieved_context = state.get("retrieved_context") or {}
    try:
        if can_use_llm():
            raw = invoke_interview_array(resume_profile, jd_analysis, retrieved_context)
            questions = [model_to_dict(validate_dict(InterviewQuestion, item)) for item in raw]
        else:
            questions = fallback_interview_questions(resume_profile, jd_analysis, retrieved_context)
        return {
            "interview_questions": questions,
            "workflow_trace": [f"InterviewCoachNode: Generated {len(questions)} interview practice questions."],
        }
    except Exception as exc:
        questions = fallback_interview_questions(resume_profile, jd_analysis, retrieved_context)
        return {
            "interview_questions": questions,
            "errors": [f"InterviewCoachNode failed and used fallback questions: {exc}"],
            "workflow_trace": [f"InterviewCoachNode: Fallback generated {len(questions)} questions."],
        }


def invoke_interview_array(resume_profile: dict, jd_analysis: dict, retrieved_context: dict) -> list[dict]:
    from src.services.llm_client import get_llm

    llm = get_llm()
    prompt = (
        "Return a JSON array of InterviewQuestion objects with question, focus_area, and prep_notes. "
        "Questions must include role-specific technical practice and project deep-dive follow-ups grounded in the resume/JD evidence.\n"
        f"Resume profile: {resume_profile}\nJD analysis: {jd_analysis}\nRAG context: {retrieved_context}"
    )
    response = llm.invoke([("system", INTERVIEW_COACH_SYSTEM), ("human", prompt)])
    content = getattr(response, "content", response)
    parsed = loads_json(str(content))
    if isinstance(parsed, dict) and "items" in parsed:
        return parsed["items"]
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array for interview questions.")
    return parsed
