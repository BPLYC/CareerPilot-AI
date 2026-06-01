"""Provider configuration for OpenAI-compatible LLM endpoints."""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


if load_dotenv:
    load_dotenv()


@dataclass
class ProviderConfig:
    api_key: str
    base_url: str
    model: str
    embedding_provider: str = "local_hash"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)


def get_provider_config(model_override: str = "") -> ProviderConfig:
    model = model_override or os.getenv("DEEPSEEK_MODEL", "")
    return ProviderConfig(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=model,
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local_hash"),
    )
