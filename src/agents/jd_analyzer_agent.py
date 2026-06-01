"""Job description analyzer node."""

import re

from src.agents.common import can_use_llm, invoke_structured
from src.agents.resume_parser_agent import KNOWN_SKILLS
from src.models.schemas import JobDescriptionAnalysis
from src.services.prompts import JD_ANALYZER_SYSTEM, schema_instruction
from src.services.structured_output import model_to_dict
from src.utils.text_utils import clean_text, unique_preserve_order


def fallback_analyze_jd(text: str) -> dict:
    cleaned = clean_text(text)
    lower = cleaned.lower()
    skills = unique_preserve_order(skill for skill in KNOWN_SKILLS if skill.lower() in lower)
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

    title_match = re.search(r"(?i)(ai|data analyst|software|machine learning|ml|swe)[\w\s/-]*intern", cleaned)
    analysis = JobDescriptionAnalysis(
        job_title=title_match.group(0).strip() if title_match else "Internship Role",
        company="unknown",
        required_skills=required,
        preferred_skills=preferred,
        responsibilities=[sentence for sentence in sentences if "respons" in sentence.lower()][:5],
        keywords=unique_preserve_order(required + preferred + ["internship"]),
        tools_and_technologies=skills,
    )
    return model_to_dict(analysis)


def jd_analyzer_node(state) -> dict:
    text = state.get("raw_jd_text", "")
    try:
        if can_use_llm():
            user_prompt = (
                schema_instruction(
                    "JobDescriptionAnalysis",
                    "job_title,company,required_skills,preferred_skills,responsibilities,keywords,education_requirements,experience_requirements,tools_and_technologies",
                )
                + "\nJob description:\n"
                + text
            )
            analysis = invoke_structured(JobDescriptionAnalysis, JD_ANALYZER_SYSTEM, user_prompt)
        else:
            analysis = fallback_analyze_jd(text)
        trace = (
            f"JDAnalyzerNode: Identified {len(analysis.get('required_skills', []))} required skills, "
            f"{len(analysis.get('preferred_skills', []))} preferred skills, {len(analysis.get('keywords', []))} keywords."
        )
        return {"jd_analysis": analysis, "workflow_trace": [trace]}
    except Exception as exc:
        analysis = fallback_analyze_jd(text)
        return {
            "jd_analysis": analysis,
            "errors": [f"JDAnalyzerNode failed and used fallback analyzer: {exc}"],
            "workflow_trace": ["JDAnalyzerNode: Fallback analyzer completed."],
        }
