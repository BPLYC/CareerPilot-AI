"""Job description analyzer node."""

import re

from src.agents.common import invoke_structured, run_node
from src.models.schemas import JobDescriptionAnalysis
from src.services.prompts import JD_ANALYZER_SYSTEM, schema_instruction
from src.services.skill_taxonomy import find_known_skills
from src.services.structured_output import model_to_dict
from src.utils.text_utils import clean_text, unique_preserve_order


def _extract_education_requirements(cleaned: str) -> dict:
    """Conservatively extract explicit education constraints from English/Chinese JDs."""
    education_sentences = [
        sentence.strip()
        for sentence in re.split(r"[。\n.!?]", cleaned)
        if re.search(
            r"(?i)\b(?:degree|bachelor|master|phd|doctorate|graduate|graduat(?:e|ing)|gpa|major)\b"
            r"|学历|本科|学士|硕士|研究生|博士|专业|毕业|绩点",
            sentence,
        )
    ]
    if not education_sentences:
        return {}

    requirement = "；".join(education_sentences)
    lower = requirement.lower()
    level = None
    if re.search(r"(?i)\b(?:phd|doctorate|doctoral)\b|博士", requirement):
        level = "doctorate"
    elif re.search(r"(?i)\b(?:master'?s?|graduate degree)\b|硕士|研究生", requirement):
        level = "master"
    elif re.search(r"(?i)\b(?:bachelor'?s?|undergraduate degree)\b|本科|学士", requirement):
        level = "bachelor"

    major = None
    major_patterns = [
        r"(?i)(?:degree|major)\s+in\s+(.+?)(?=\s+(?:is\s+)?(?:required|preferred)|[,;；]|$)",
        r"(?i)(?:bachelor'?s?|master'?s?)\s+(?:degree\s+)?in\s+(.+?)(?=\s+(?:is\s+)?(?:required|preferred)|[,;；]|$)",
        r"(计算机(?:科学与技术|科学)?|软件工程|数据科学|人工智能|信息技术|统计学|数学)(?:相关)?专业",
    ]
    for pattern in major_patterns:
        match = re.search(pattern, requirement)
        if match:
            major = match.group(1).strip()
            break

    graduation = None
    graduation_match = re.search(
        r"(?i)(?:graduat(?:e|ing|ion)(?:\s+(?:between|in|by))?\s*)(20\d{2}(?:\s*[-–—到至]\s*20\d{2})?)"
        r"|(?:毕业(?:时间|年份)?(?:在|为)?\s*)(20\d{2}(?:\s*[-–—到至]\s*20\d{2})?)"
        r"|(20\d{2}(?:\s*[-–—到至]\s*20\d{2})?)\s*年?毕业",
        requirement,
    )
    if graduation_match:
        graduation = next(group for group in graduation_match.groups() if group)

    gpa = None
    gpa_match = re.search(r"(?i)\bGPA\s*(?:of|>=|≥|at least|不低于)?\s*(\d(?:\.\d+)?)", cleaned)
    if gpa_match:
        gpa = float(gpa_match.group(1))

    preferred = any(
        phrase in lower
        for phrase in ("preferred", "nice to have", "a plus", "优先", "加分", "更佳")
    )
    required = any(
        phrase in lower
        for phrase in ("required", "must", "minimum", "at least", "要求", "须", "至少")
    )
    return {
        "education_requirements": requirement,
        "education_level": level,
        "education_major": major,
        "graduation_requirement": graduation,
        "gpa_requirement": gpa,
        "education_is_required": False if preferred and not required else True if required else None,
    }


def fallback_analyze_jd(text: str) -> dict:
    cleaned = clean_text(text)
    lower = cleaned.lower()
    skills = unique_preserve_order(find_known_skills(lower))
    sentences = [sentence.strip() for sentence in re.split(r"[.\n]", cleaned) if sentence.strip()]
    preferred = []
    required = []
    for skill in skills:
        matching_sentence = next((sentence for sentence in sentences if skill.lower() in sentence.lower()), "")
        context = matching_sentence.lower()
        if any(word in context for word in ["preferred", "nice to have", "bonus", "plus"]):
            preferred.append(skill)
        else:
            required.append(skill)

    # Lazy, not greedy: [\w\s/-]* used to run past the first "Intern" and stop
    # at the last one in the document, so "AI Intern\n\nWe are looking for an AI
    # Intern to..." yielded that whole span as the job title.
    title_match = re.search(r"(?i)(ai|data analyst|software|machine learning|ml|swe)[\w\s/-]*?intern", cleaned)
    education = _extract_education_requirements(cleaned)
    analysis = JobDescriptionAnalysis(
        job_title=title_match.group(0).strip() if title_match else "Internship Role",
        company="unknown",
        required_skills=required,
        preferred_skills=preferred,
        responsibilities=[sentence for sentence in sentences if "respons" in sentence.lower()][:5],
        keywords=unique_preserve_order(required + preferred + ["internship"]),
        tools_and_technologies=skills,
        **education,
    )
    return model_to_dict(analysis)


def _describe(analysis: dict) -> str:
    return (
        f"识别到 {len(analysis.get('required_skills', []))} 项必需技能、"
        f"{len(analysis.get('preferred_skills', []))} 项加分技能和 {len(analysis.get('keywords', []))} 个关键词。"
    )


def jd_analyzer_node(state) -> dict:
    text = state.get("raw_jd_text", "")

    def from_llm() -> dict:
        user_prompt = (
            schema_instruction(
                "JobDescriptionAnalysis",
                "job_title,company,required_skills,preferred_skills,responsibilities,keywords,"
                "education_requirements,education_level,education_major,graduation_requirement,"
                "gpa_requirement,education_is_required,experience_requirements,tools_and_technologies",
            )
            + "\nJob description:\n"
            + text
        )
        return invoke_structured(JobDescriptionAnalysis, JD_ANALYZER_SYSTEM, user_prompt)

    return run_node(
        node_name="JDAnalyzerNode",
        output_key="jd_analysis",
        llm_branch=from_llm,
        fallback_branch=lambda: fallback_analyze_jd(text),
        describe=_describe,
    )
