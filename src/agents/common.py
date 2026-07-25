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

    def finish(result: Any, failure: Exception | None, used_fallback: bool) -> dict:
        if refine is not None:
            result = refine(result)
        update = dict(base_update or {})
        if extra_state is not None:
            update.update(extra_state(result))
        update[output_key] = result
        if not used_fallback:
            update["workflow_trace"] = [f"{node_name}: {describe(result)}"]
        else:
            update["fallback_nodes"] = [node_name]
            if failure is not None:
                update["errors"] = [f"{node_name} 调用大模型失败，已采用离线规则：{failure}"]
            update["workflow_trace"] = [f"{node_name}：已采用离线规则。{describe(result)}"]
        return update

    try:
        if can_use_llm():
            return finish(llm_branch(), None, False)
        return finish(fallback_branch(), None, True)
    except Exception as exc:
        return finish(fallback_branch(), exc, True)


def trace(message: str) -> dict:
    return {"workflow_trace": [message]}


def error(message: str) -> dict:
    return {"errors": [message]}
