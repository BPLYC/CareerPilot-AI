"""Resume parser node."""

import re

from src.agents.common import invoke_structured, run_node
from src.models.schemas import Education, ProjectExperience, ResumeProfile, WorkExperience
from src.services.prompts import RESUME_PARSER_SYSTEM, schema_instruction
from src.services.skill_taxonomy import find_known_skills
from src.services.structured_output import model_to_dict
from src.utils.text_utils import clean_text, truncate_text, unique_preserve_order

SECTION_HEADINGS = {
    "education": {"education", "education background", "教育", "教育背景"},
    "skills": {"skills", "technical skills", "技能", "专业技能"},
    "projects": {"projects", "project experience", "personal projects", "项目", "项目经历"},
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "工作经历",
        "实习经历",
    },
}


def _extract_name(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped.split()) <= 5 and "@" not in stripped:
            return stripped.replace("Name:", "").strip() or "unknown"
    return "unknown"


def _section_name(line: str) -> str | None:
    normalized = re.sub(r"[:：]\s*$", "", line.strip()).lower()
    for section, headings in SECTION_HEADINGS.items():
        if normalized in headings:
            return section
    return None


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "header"
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        heading = _section_name(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return sections


def _nonempty_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _looks_like_description(line: str) -> bool:
    words = line.split()
    return (
        len(line) > 70
        or len(words) > 10
        or bool(re.match(r"(?i)^(built|developed|created|designed|implemented|analyzed|used|led)\b", line))
        or line.startswith(("使用", "开发", "构建", "设计", "实现", "分析", "负责", "参与"))
    )


def _project_blocks(lines: list[str]) -> list[list[str]]:
    blocks = _nonempty_blocks(lines)
    if len(blocks) > 1:
        return blocks

    # Plain-text exports often remove blank lines. In that case, treat a short
    # line followed by descriptive text as an entry boundary.
    entries: list[list[str]] = []
    current: list[str] = []
    for line in (blocks[0] if blocks else []):
        if current and not _looks_like_description(line):
            entries.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append(current)
    return entries


def _parse_projects(lines: list[str]) -> list[dict]:
    projects = []
    for block in _project_blocks(lines):
        if not block:
            continue
        name = re.sub(r"(?i)^project\s*[:：]\s*", "", block[0]).strip()
        description = " ".join(block[1:]).strip()
        if not name:
            continue
        section_text = " ".join(block)
        projects.append(
            model_to_dict(
                ProjectExperience(
                    name=name,
                    description=description or name,
                    technologies=unique_preserve_order(find_known_skills(section_text)),
                )
            )
        )
    return projects


def _parse_inline_projects(text: str) -> list[dict]:
    projects = []
    for line in (text or "").splitlines():
        match = re.match(r"(?i)\s*(?:project|项目)\s*[:：]\s*(.+)", line)
        if not match:
            continue
        content = match.group(1).strip()
        name = re.split(r"(?i)\s+(?:using|with|使用|采用)\s+", content, maxsplit=1)[0].strip()
        projects.append(
            model_to_dict(
                ProjectExperience(
                    name=name or content,
                    description=content,
                    technologies=unique_preserve_order(find_known_skills(content)),
                )
            )
        )
    return projects


def _parse_education(lines: list[str]) -> list[dict]:
    education = []
    for block in _nonempty_blocks(lines):
        if not block:
            continue
        degree_index = next(
            (
                index
                for index, line in enumerate(block)
                if re.search(
                    r"(?i)\b(bachelor|master|phd|b\.?s\.?|m\.?s\.?)\b|学士|硕士|博士",
                    line,
                )
            ),
            None,
        )
        if degree_index is None:
            continue
        degree_line = block[degree_index]
        school = next((line for line in block[:degree_index] if line), "unknown")
        major = "unknown"
        english_major = re.search(
            r"(?i)\b(?:bachelor|master|phd|b\.?s\.?|m\.?s\.?).*?\bin\s+([^,，]+)",
            degree_line,
        )
        chinese_major = re.search(r"([\u4e00-\u9fff]{2,20})(?:专业)?(?:学士|硕士|博士)", degree_line)
        if english_major:
            major = english_major.group(1).strip()
        elif chinese_major:
            major = chinese_major.group(1).strip()
        graduation = next(
            (
                value
                for value in re.findall(
                    r"(?i)(?:expected\s+)?(?:[A-Z][a-z]{2,8}\s+)?(?:19|20)\d{2}|"
                    r"(?:19|20)\d{2}\s*年",
                    degree_line,
                )
                if value
            ),
            "unknown",
        )
        education.append(
            model_to_dict(
                Education(
                    school=school,
                    degree=degree_line,
                    major=major,
                    graduation_date=graduation,
                )
            )
        )
    return education


def _work_header(line: str) -> tuple[str, str, str] | None:
    pipe_parts = [part.strip() for part in re.split(r"\s*[|｜]\s*", line) if part.strip()]
    if len(pipe_parts) >= 2:
        return pipe_parts[0], pipe_parts[1], pipe_parts[2] if len(pipe_parts) >= 3 else ""

    comma_parts = [part.strip() for part in line.split(",") if part.strip()]
    if len(comma_parts) >= 2:
        has_dated_tail = bool(re.search(r"\b(?:19|20)\d{2}\b", comma_parts[-1]))
        if len(comma_parts) > 2 and not has_dated_tail:
            return None
        if _looks_like_description(comma_parts[0]):
            return None
        duration = comma_parts[-1] if has_dated_tail else ""
        company = comma_parts[1]
        return company, comma_parts[0], duration
    return None


def _parse_work_experience(lines: list[str]) -> list[dict]:
    jobs = []
    current_header: tuple[str, str, str] | None = None
    descriptions: list[str] = []

    def append_current() -> None:
        if current_header is None:
            return
        company, role, duration = current_header
        jobs.append(
            model_to_dict(
                WorkExperience(
                    company=company,
                    role=role,
                    duration=duration,
                    description=" ".join(descriptions).strip() or role,
                )
            )
        )

    for line in lines:
        if not line:
            continue
        parsed_header = _work_header(line)
        if parsed_header:
            append_current()
            current_header = parsed_header
            descriptions = []
        elif current_header:
            descriptions.append(line)
        elif not jobs:
            # Compatibility with simple exports where the first line is only a
            # role and the employer is not stated.
            current_header = ("unknown", line, "")
    append_current()
    return jobs


def fallback_parse_resume(text: str) -> dict:
    cleaned = clean_text(text)
    sections = _split_sections(text)
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", cleaned)
    phone_match = re.search(r"(\+?\d[\d\-\s()]{7,}\d)", cleaned)
    skills = unique_preserve_order(find_known_skills(cleaned))

    projects = _parse_projects(sections.get("projects", []))
    if not projects:
        projects = _parse_inline_projects(text)
    education = _parse_education(sections.get("education", []))
    work_experience = _parse_work_experience(sections.get("experience", []))
    if not work_experience and "intern" in cleaned.lower():
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
