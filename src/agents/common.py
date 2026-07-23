"""Shared agent utilities."""

import json
from collections.abc import Callable
from typing import Any

from src.services.llm_client import get_llm
from src.services.provider_config import get_provider_config
from src.services.structured_output import loads_json, model_to_dict, validate_json


def can_use_llm(model: str = "") -> bool:
    return get_provider_config(model).is_configured


def invoke_structured(model_cls: type[Any], system_prompt: str, user_prompt: str, model: str = "") -> dict:
    llm = get_llm(model=model)
    response = llm.invoke([("system", system_prompt), ("human", user_prompt)])
    content = getattr(response, "content", response)
    if not isinstance(content, str):
        content = json.dumps(content)
    return model_to_dict(validate_json(model_cls, content))


def invoke_structured_list(system_prompt: str, user_prompt: str, what: str, model: str = "") -> list[dict]:
    """Invoke the LLM for a JSON array, tolerating a single {"items": [...]} wrapper."""

    llm = get_llm(model=model)
    response = llm.invoke([("system", system_prompt), ("human", user_prompt)])
    content = getattr(response, "content", response)
    parsed = loads_json(str(content))
    if isinstance(parsed, dict) and "items" in parsed:
        return parsed["items"]
    if not isinstance(parsed, list):
        raise ValueError(f"Expected a JSON array for {what}.")
    return parsed


def run_node(
    node_name: str,
    output_key: str,
    llm_branch: Callable[[], Any],
    fallback_branch: Callable[[], Any],
    describe: Callable[[Any], str],
    refine: Callable[[Any], Any] | None = None,
    extra_state: Callable[[Any], dict] | None = None,
    base_update: dict | None = None,
) -> dict:
    """Run a node's LLM branch with a deterministic fallback and uniform error handling.

    Every LLM-backed node shares one shape: use the model when credentials are
    configured, otherwise compute the same output deterministically, and on any
    failure fall back rather than propagate, so one bad response cannot abort
    the workflow.

    `refine` and `extra_state` run on whichever branch produced the result. That
    is deliberate: they carry schema validation, output sanitisation, and derived
    state such as low-score warnings, and applying them to the success path only
    is exactly how the two branches drift apart.
    """

    def finish(result: Any, failure: Exception | None) -> dict:
        if refine is not None:
            result = refine(result)
        update = dict(base_update or {})
        if extra_state is not None:
            update.update(extra_state(result))
        update[output_key] = result
        if failure is None:
            update["workflow_trace"] = [f"{node_name}: {describe(result)}"]
        else:
            update["errors"] = [f"{node_name} failed and used its deterministic fallback: {failure}"]
            update["workflow_trace"] = [f"{node_name}: Fallback used. {describe(result)}"]
        return update

    try:
        return finish(llm_branch() if can_use_llm() else fallback_branch(), None)
    except Exception as exc:
        return finish(fallback_branch(), exc)


def trace(message: str) -> dict:
    return {"workflow_trace": [message]}


def error(message: str) -> dict:
    return {"errors": [message]}
