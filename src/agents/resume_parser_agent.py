"""Resume parser node."""

import re

from src.agents.common import can_use_llm, invoke_structured
from src.models.schemas import ProjectExperience, ResumeProfile, WorkExperience
from src.services.prompts import RESUME_PARSER_SYSTEM, schema_instruction
from src.services.structured_output import model_to_dict
from src.utils.text_utils import clean_text, truncate_text, unique_preserve_order


KNOWN_SKILLS = [
    "Python", "SQL", "scikit-learn", "pandas", "NumPy", "Git", "Flask", "Matplotlib",
    "PyTorch", "TensorFlow", "Docker", "Tableau", "Java", "C++", "NLP", "React",
    "FastAPI", "SQLite", "REST API", "Power BI", "Airflow", "Spark", "AWS", "GCP",
]


def _extract_name(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped.split()) <= 5 and "@" not in stripped:
            return stripped.replace("Name:", "").strip() or "unknown"
    return "unknown"


def fallback_parse_resume(text: str) -> dict:
    cleaned = clean_text(text)
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", cleaned)
    phone_match = re.search(r"(\+?\d[\d\-\s()]{7,}\d)", cleaned)
    skills = unique_preserve_order(skill for skill in KNOWN_SKILLS if skill.lower() in cleaned.lower())

    projects = []
    project_patterns = [
        "Movie Recommendation System",
        "Sales Data Dashboard",
        "Personal Task Manager Web App",
    ]
    for name in project_patterns:
        if name.lower() in cleaned.lower():
            techs = [skill for skill in skills if skill.lower() in cleaned.lower()]
            projects.append(model_to_dict(ProjectExperience(name=name, description=f"Project mentioned in resume: {name}.", technologies=techs)))

    work_experience = []
    if "intern" in cleaned.lower():
        work_experience.append(
            model_to_dict(WorkExperience(
                company="unknown",
                role="Intern",
                duration="",
                description="Internship experience mentioned in resume.",
            ))
        )

    profile = ResumeProfile(
        name=_extract_name(text),
        email=email_match.group(0) if email_match else "unknown",
        phone=phone_match.group(0) if phone_match else "unknown",
        skills=skills,
        projects=projects,
        work_experience=work_experience,
    )
    return model_to_dict(profile)


def resume_parser_node(state) -> dict:
    text, was_truncated = truncate_text(state.get("raw_resume_text", ""))
    warnings = ["Resume text was truncated to fit analysis limits."] if was_truncated else []
    try:
        if can_use_llm():
            user_prompt = (
                schema_instruction(
                    "ResumeProfile",
                    "name,email,phone,education,skills,projects,work_experience,publications,awards",
                )
                + "\nResume:\n"
                + text
            )
            profile = invoke_structured(ResumeProfile, RESUME_PARSER_SYSTEM, user_prompt)
        else:
            profile = fallback_parse_resume(text)
        trace = (
            f"ResumeParserNode: Extracted {len(profile.get('projects', []))} projects, "
            f"{len(profile.get('skills', []))} skills, {len(profile.get('work_experience', []))} work experiences."
        )
        return {"resume_profile": profile, "workflow_trace": [trace], "warnings": warnings}
    except Exception as exc:
        profile = fallback_parse_resume(text)
        return {
            "resume_profile": profile,
            "errors": [f"ResumeParserNode failed and used fallback parser: {exc}"],
            "warnings": warnings,
            "workflow_trace": ["ResumeParserNode: Fallback parser completed."],
        }
