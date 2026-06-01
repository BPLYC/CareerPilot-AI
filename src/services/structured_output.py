"""Helpers for safe JSON and Pydantic parsing."""

import json
import re
from typing import Any, Type


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


def validate_json(model_cls: Type[Any], text: str) -> Any:
    json_text = extract_json_object(text)
    if hasattr(model_cls, "model_validate_json"):
        return model_cls.model_validate_json(json_text)
    return model_cls.parse_raw(json_text)


def validate_dict(model_cls: Type[Any], data: dict) -> Any:
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


def loads_json(text: str) -> Any:
    return json.loads(extract_json_object(text))
