"""Provider configuration for OpenAI-compatible LLM endpoints."""

import os
from contextlib import contextmanager
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


if load_dotenv:
    load_dotenv()


DEFAULT_REQUEST_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 2


def _int_env(name: str, default: int) -> int:
    """Read an integer setting, keeping the default when it is unset or unusable."""

    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass
class ProviderConfig:
    api_key: str
    base_url: str
    model: str
    embedding_provider: str = "local_hash"
    thinking: str = "enabled"
    reasoning_effort: str = "high"
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)


def get_provider_config(model_override: str = "") -> ProviderConfig:
    model = model_override or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    return ProviderConfig(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=model,
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local_hash"),
        thinking=os.getenv("DEEPSEEK_THINKING", "disabled").lower(),
        reasoning_effort=os.getenv("DEEPSEEK_REASONING_EFFORT", "low").lower(),
        # Thinking mode with high reasoning effort is much slower than the
        # default configuration, so the 60s timeout has to be raisable without
        # editing source.
        request_timeout=_int_env("DEEPSEEK_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT),
        max_retries=_int_env("DEEPSEEK_MAX_RETRIES", DEFAULT_MAX_RETRIES),
    )


@contextmanager
def provider_overrides(model: str = "", thinking: str = "", reasoning_effort: str = ""):
    """Apply caller-chosen provider settings for the duration of a block.

    Agents read their configuration from the environment, so settings picked in
    the UI have to reach them that way. Doing it while rendering a widget means
    drawing the sidebar mutates process-wide state on every Streamlit rerun and
    never restores it. Scoping the change to the analysis keeps the mechanism
    but confines the blast radius, and empty values are ignored rather than
    blanking whatever .env supplied.
    """

    overrides = {
        "DEEPSEEK_MODEL": model,
        "DEEPSEEK_THINKING": thinking,
        "DEEPSEEK_REASONING_EFFORT": reasoning_effort,
    }
    applied = {key: value for key, value in overrides.items() if value}
    previous = {key: os.environ.get(key) for key in applied}

    os.environ.update(applied)
    try:
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
