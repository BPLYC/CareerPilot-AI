"""Shared agent utilities."""

import json
from typing import Any

from src.services.llm_client import get_llm
from src.services.provider_config import get_provider_config
from src.services.structured_output import model_to_dict, validate_json


def can_use_llm(model: str = "") -> bool:
    return get_provider_config(model).is_configured


def invoke_structured(model_cls: type[Any], system_prompt: str, user_prompt: str, model: str = "") -> dict:
    llm = get_llm(model=model)
    response = llm.invoke([("system", system_prompt), ("human", user_prompt)])
    content = getattr(response, "content", response)
    if not isinstance(content, str):
        content = json.dumps(content)
    return model_to_dict(validate_json(model_cls, content))


def trace(message: str) -> dict:
    return {"workflow_trace": [message]}


def error(message: str) -> dict:
    return {"errors": [message]}
