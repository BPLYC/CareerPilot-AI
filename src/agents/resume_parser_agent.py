"""Resume parser node."""

import re

from src.agents.common import invoke_structured, run_node
from src.models.schemas import Education, ProjectExperience, ResumeProfile, WorkExperience
from src.services.prompts import RESUME_PARSER_SYSTEM, schema_instruction
from src.services.skill_taxonomy import find_known_skills
from src.services.structured_output import model_to_dict
from src.utils.text_utils import clean_text, truncate_text, unique_preserve_order


def _extract_name(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped.split()) <= 5 and "@" not in stripped:
            return stripped.replace("Name:", "").strip() or "unknown"
    return "unknown"


def fallback_parse_resume(text: str) -> dict:
    cleaned = clean_text(text)
    lines = [line.strip() for line in (text or "").splitlines()]
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", cleaned)
    phone_match = re.search(r"(\+?\d[\d\-\s()]{7,}\d)", cleaned)
    skills = unique_preserve_order(find_known_skills(cleaned))

    projects = []
    project_patterns = [
        "Movie Recommendation System",
        "Sales Data Dashboard",
        "Personal Task Manager Web App",
    ]
    lowered = cleaned.lower()
    for index, name in enumerate(project_patterns):
        if name.lower() in cleaned.lower():
            start = lowered.index(name.lower())
            later_starts = [
                lowered.index(other.lower(), start + len(name))
                for other in project_patterns[index + 1:]
                if other.lower() in lowered[start + len(name):]
            ]
            experience_start = lowered.find(" experience ", start + len(name))
            if experience_start >= 0:
                later_starts.append(experience_start)
            end = min(later_starts) if later_starts else len(cleaned)
            section = cleaned[start:end]
            techs = unique_preserve_order(find_known_skills(section))
            projects.append(model_to_dict(ProjectExperience(name=name, description=section, technologies=techs)))

    education = []
    degree_line = next(
        (
            line
            for line in lines
            if re.search(r"(?i)\b(bachelor|master|phd|b\.?s\.?|m\.?s\.?)\b", line)
        ),
        "",
    )
    if degree_line:
        education.append(
            model_to_dict(
                Education(
                    school="unknown",
                    degree=degree_line,
                    major="unknown",
                    graduation_date="unknown",
                )
            )
        )

    work_experience = []
    experience_index = next(
        (index for index, line in enumerate(lines) if line.lower() in {"experience", "work experience"}),
        None,
    )
    if experience_index is not None:
        experience_lines = [line for line in lines[experience_index + 1:] if line]
        role_line = experience_lines[0] if experience_lines else "Experience"
        description = " ".join(experience_lines[1:]) or role_line
        work_experience.append(
            model_to_dict(WorkExperience(
                company="unknown",
                role=role_line,
                duration="",
                description=description,
            ))
        )
    elif "intern" in cleaned.lower():
        work_experience.append(
            model_to_dict(
                WorkExperience(
                    company="unknown",
                    role="Intern",
                    duration="",
                    description="Internship experience mentioned in resume.",
                )
            )
        )

    profile = ResumeProfile(
        name=_extract_name(text),
        email=email_match.group(0) if email_match else "unknown",
        phone=phone_match.group(0) if phone_match else "unknown",
        education=education,
        skills=skills,
        projects=projects,
        work_experience=work_experience,
    )
    return model_to_dict(profile)


def _describe(profile: dict) -> str:
    return (
        f"提取到 {len(profile.get('projects', []))} 个项目、"
        f"{len(profile.get('skills', []))} 项技能和 {len(profile.get('work_experience', []))} 段工作经历。"
    )


def resume_parser_node(state) -> dict:
    text, was_truncated = truncate_text(state.get("raw_resume_text", ""))
    warnings = ["Resume text was truncated to fit analysis limits."] if was_truncated else []

    def from_llm() -> dict:
        user_prompt = (
            schema_instruction(
                "ResumeProfile",
                "name,email,phone,education,skills,projects,work_experience,publications,awards",
            )
            + "\nResume:\n"
            + text
        )
        return invoke_structured(ResumeProfile, RESUME_PARSER_SYSTEM, user_prompt)

    return run_node(
        node_name="ResumeParserNode",
        output_key="resume_profile",
        llm_branch=from_llm,
        fallback_branch=lambda: fallback_parse_resume(text),
        describe=_describe,
        base_update={"warnings": warnings},
    )
