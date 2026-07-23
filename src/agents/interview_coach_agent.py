"""Interview preparation node."""

from src.agents.common import invoke_structured_list, run_node
from src.models.schemas import InterviewQuestion
from src.services.prompts import INTERVIEW_COACH_SYSTEM, context_block
from src.services.structured_output import model_to_dict, validate_dict


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

    def from_llm() -> list[dict]:
        user_prompt = (
            "Return a JSON array of InterviewQuestion objects with question, focus_area, and prep_notes. "
            "Questions must include role-specific technical practice and project deep-dive follow-ups "
            "grounded in the resume/JD evidence.\n"
            + context_block(
                resume_profile=resume_profile,
                jd_analysis=jd_analysis,
                rag_context=retrieved_context,
            )
        )
        raw = invoke_structured_list(INTERVIEW_COACH_SYSTEM, user_prompt, "interview questions")
        return [model_to_dict(validate_dict(InterviewQuestion, item)) for item in raw]

    return run_node(
        node_name="InterviewCoachNode",
        output_key="interview_questions",
        llm_branch=from_llm,
        fallback_branch=lambda: fallback_interview_questions(resume_profile, jd_analysis, retrieved_context),
        describe=lambda questions: f"Generated {len(questions)} interview practice questions.",
    )
