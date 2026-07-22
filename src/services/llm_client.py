"""LLM and embedding client factories."""

import hashlib

from src.services.provider_config import get_provider_config


class LocalHashEmbeddings:
    """Deterministic local embeddings for offline tests and demos."""

    def __init__(self, size: int = 64):
        self.size = size

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        tokens = (text or "").lower().split()
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = digest[0] % self.size
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_llm(model: str = "", temperature: float = 0.3):
    """Return a DeepSeek/OpenAI-compatible LangChain chat model."""

    config = get_provider_config(model_override=model)
    if not config.is_configured:
        raise RuntimeError("DeepSeek API is not configured. Set DEEPSEEK_API_KEY and DEEPSEEK_MODEL.")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install langchain-openai to use the LLM client.") from exc
    thinking_enabled = config.thinking == "enabled"
    kwargs = {
        "model": config.model,
        "api_key": config.api_key,
        "base_url": config.base_url,
        "max_retries": 2,
        "request_timeout": 60,
    }
    if thinking_enabled:
        kwargs["reasoning_effort"] = config.reasoning_effort
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        kwargs["temperature"] = temperature
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return ChatOpenAI(
        **kwargs,
    )


def get_embeddings():
    """Return embeddings. Defaults to local deterministic vectors for DeepSeek-only setups."""

    config = get_provider_config()
    if config.embedding_provider.lower() == "openai":
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install langchain-openai to use OpenAI embeddings.") from exc
        return OpenAIEmbeddings()
    return LocalHashEmbeddings()
