"""Helpers for safe JSON and Pydantic parsing."""

import json
import re
from typing import Any


def extract_json_object(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    if cleaned.startswith("{") or cleaned.startswith("["):
        return cleaned
    match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
    if match:
        return match.group(1)
    raise ValueError("No JSON object found in LLM response.")


def model_to_dict(model_instance: Any) -> dict:
    if hasattr(model_instance, "model_dump"):
        return model_instance.model_dump()
    return model_instance.dict()


def validate_json(model_cls: type[Any], text: str) -> Any:
    return validate_dict(model_cls, loads_json(text))


def validate_dict(model_cls: type[Any], data: dict) -> Any:
    data = normalize_model_data(model_cls, data)
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


def loads_json(text: str) -> Any:
    return json.loads(extract_json_object(text))


def normalize_model_data(model_cls: type[Any], data: dict) -> dict:
    """Tolerate small LLM schema deviations without accepting new facts."""

    if not isinstance(data, dict):
        return data
    normalized = dict(data)
    model_name = getattr(model_cls, "__name__", "")
    aliases = {
        "WorkExperience": {"title": "role", "position": "role"},
        "BulletSuggestion": {
            "original": "original_bullet",
            "bullet": "optimized_bullet",
            "optimized": "optimized_bullet",
            "optimized_text": "optimized_bullet",
            "suggestion": "optimized_bullet",
            "suggested_bullet": "optimized_bullet",
            "suggested_text": "optimized_bullet",
            "improved_bullet": "optimized_bullet",
            "rewritten_bullet": "optimized_bullet",
            "new_bullet": "optimized_bullet",
            "reason": "rationale",
            "explanation": "rationale",
        },
        "InterviewQuestion": {"area": "focus_area", "notes": "prep_notes"},
    }
    for source, target in aliases.get(model_name, {}).items():
        if source in normalized and target not in normalized:
            normalized[target] = normalized[source]

    if model_name == "ResumeProfile":
        normalized = normalize_resume_profile(normalized)

    if model_name == "MatchReport":
        normalized = normalize_match_report(normalized)

    if model_name == "BulletSuggestion":
        normalized.setdefault("context", normalized.get("original_bullet") or "Resume experience")
        normalized.setdefault(
            "rationale",
            "Grounded in existing resume evidence and target job-description requirements.",
        )
        if "optimized_bullet" not in normalized:
            normalized["optimized_bullet"] = longest_text_value(
                normalized,
                excluded_keys={"context", "original_bullet", "original", "rationale", "reason", "id"},
            )

    fields = getattr(model_cls, "model_fields", {})
    for field_name, field in fields.items():
        if isinstance(normalized.get(field_name), list) and str(field.annotation) == "<class 'str'>":
            normalized[field_name] = "; ".join(str(item) for item in normalized[field_name] if item)
        if normalized.get(field_name) is None and not field.is_required():
            try:
                normalized[field_name] = field.get_default(call_default_factory=True)
            except TypeError:
                normalized[field_name] = field.default
    return normalized


def normalize_overall_score(value: object) -> object:
    """Put a score onto the 0-100 scale the schema expects.

    Observed from the real model: `"overall_score": 0.4`, meaning 40 percent on
    a 0-1 scale. Pydantic rejects a float with a fractional part, so the node
    discarded the model's answer and fell back, quietly turning a scoring
    difference into a scoring failure.

    A bare 0 or 1 is left alone: those are valid 0-100 scores and there is no
    way to tell which scale was meant.
    """

    if isinstance(value, str):
        text = value.strip().rstrip("%")
        try:
            value = float(text)
        except ValueError:
            return value

    if isinstance(value, float):
        if 0 < value < 1:
            return round(value * 100)
        return round(value)
    return value


def normalize_match_report(data: dict) -> dict:
    normalized = dict(data)
    if "overall_score" in normalized:
        normalized["overall_score"] = normalize_overall_score(normalized["overall_score"])
    if isinstance(normalized.get("relevant_projects"), list):
        normalized["relevant_projects"] = [
            project_name(item) for item in normalized["relevant_projects"]
        ]
    for key in ["matched_skills", "missing_skills", "weak_sections"]:
        if isinstance(normalized.get(key), str):
            normalized[key] = split_text_items(normalized[key])
    return normalized


def project_name(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("project") or item.get("title") or item)
    return str(item)


def normalize_resume_profile(data: dict) -> dict:
    normalized = dict(data)
    if isinstance(normalized.get("skills"), str):
        normalized["skills"] = split_text_items(normalized["skills"])
    for key in ["publications", "awards"]:
        if isinstance(normalized.get(key), str):
            normalized[key] = split_text_items(normalized[key])

    if isinstance(normalized.get("education"), str):
        normalized["education"] = [education_from_text(normalized["education"])]
    elif isinstance(normalized.get("education"), list):
        normalized["education"] = [
            education_from_text(item) if isinstance(item, str) else item
            for item in normalized["education"]
        ]

    if isinstance(normalized.get("projects"), str):
        normalized["projects"] = [project_from_text(item) for item in split_text_items(normalized["projects"])]
    if isinstance(normalized.get("projects"), list):
        normalized["projects"] = [
            project_from_text(item) if isinstance(item, str) else item
            for item in normalized["projects"]
        ]

    if isinstance(normalized.get("work_experience"), str):
        normalized["work_experience"] = [work_from_text(item) for item in split_text_items(normalized["work_experience"])]
    if isinstance(normalized.get("work_experience"), list):
        normalized["work_experience"] = [
            work_from_text(item) if isinstance(item, str) else item
            for item in normalized["work_experience"]
        ]
    return normalized


def education_from_text(text: str) -> dict:
    return {"school": text, "degree": "unknown", "major": "unknown", "graduation_date": "unknown"}


def project_from_text(text: str) -> dict:
    name = text.split(":", 1)[0].strip() if ":" in text else "Resume project"
    return {"name": name or "Resume project", "description": text, "technologies": [], "outcome": ""}


def work_from_text(text: str) -> dict:
    role = text.split(",", 1)[0].strip() if "," in text else "Work Experience"
    return {"company": "unknown", "role": role or "Work Experience", "duration": "", "description": text}


def split_text_items(text: str) -> list[str]:
    items = [item.strip(" -\t") for item in re.split(r"\n|;|,", text or "") if item.strip(" -\t")]
    return items or [text]


def longest_text_value(data: dict, excluded_keys: set[str]) -> str:
    values = [
        value.strip()
        for key, value in data.items()
        if key not in excluded_keys and isinstance(value, str) and value.strip()
    ]
    if not values:
        return data.get("original_bullet") or data.get("original") or "Resume evidence available for revision."
    return max(values, key=len)
