"""Provider configuration for OpenAI-compatible LLM endpoints."""

import os
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
