"""Centralized prompts for LLM-backed agents."""

import json
from typing import Any

RESUME_PARSER_SYSTEM = (
    "You are a conservative resume parser. Extract only facts explicitly present "
    "in the resume. Do not infer or invent missing fields. Return strict JSON only."
)

JD_ANALYZER_SYSTEM = (
    "You analyze internship job descriptions. Separate required skills from "
    "preferred skills using the wording in the JD. Return strict JSON only."
)

MATCH_SCORING_SYSTEM = (
    "You score resume-JD fit using explicit evidence only. Use the requested "
    "schema and return strict JSON only."
)

RESUME_OPTIMIZER_SYSTEM = (
    "You improve resume bullets without fabricating facts. Use only projects, "
    "skills, technologies, and outcomes present in the source resume. Return JSON only."
)

REFLECTION_SYSTEM = (
    "You are a factual consistency reviewer. Flag fabricated metrics, skills, "
    "responsibilities, or technologies not supported by the resume. Return JSON only."
)

APPLICATION_ANSWER_SYSTEM = (
    "You draft conservative internship application answers using only verified resume "
    "and job-description evidence. Do not answer visa, work authorization, sponsorship, "
    "salary, legal eligibility, or personal constraint questions. Return JSON only."
)

INTERVIEW_COACH_SYSTEM = (
    "You generate interview practice questions grounded in the candidate resume and "
    "target job description. Do not invent project details. Return JSON only."
)


def schema_instruction(schema_name: str, fields: str) -> str:
    return f"Return one JSON object matching {schema_name}. Fields: {fields}"


def context_block(**sections: Any) -> str:
    """Render named context sections as JSON.

    Interpolating a dict straight into an f-string yields its Python repr:
    single-quoted keys, None, True. That is not JSON, so every prompt that did
    it was showing the model Python literals while the system prompt demanded
    "strict JSON only". Worse, a value containing an apostrophe flips repr to
    double quotes for that one string, so the model sees both quoting styles in
    a single object. Resume text is full of apostrophes ("Dean's List").

    Section names become labels: context_block(resume_profile=...) renders as
    "Resume profile:".
    """

    blocks = []
    for name, value in sections.items():
        label = name.replace("_", " ").capitalize()
        if isinstance(value, str):
            rendered = value
        else:
            rendered = json.dumps(value, ensure_ascii=False, default=str)
        blocks.append(f"{label}:\n{rendered}")
    return "\n".join(blocks)
