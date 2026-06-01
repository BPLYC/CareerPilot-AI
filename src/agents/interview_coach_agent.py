"""Interview preparation node."""

from src.agents.common import can_use_llm
from src.models.schemas import InterviewQuestion
from src.services.prompts import INTERVIEW_COACH_SYSTEM
from src.services.structured_output import loads_json, model_to_dict, validate_dict


def _project_questions(projects: list[dict]) -> list[dict]:
    questions = []
    for project in projects[:2]:
        name = project.get("name", "your project")
        questions.append(
            model_to_dict(
                InterviewQuestion(
                    question=f"Walk me through {name}. What problem did it solve, and what tradeoffs did you make?",
                    focus_area="Project deep dive",
                    prep_notes="Use only implementation details and outcomes already present in your resume.",
                )
            )
        )
    return questions


def fallback_interview_questions(resume_profile: dict, jd_analysis: dict, retrieved_context: dict) -> list[dict]:
    questions = _project_questions(resume_profile.get("projects", []))
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
        "Questions must be grounded in the resume/JD evidence.\n"
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
