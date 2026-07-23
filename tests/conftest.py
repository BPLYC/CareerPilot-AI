"""Pytest configuration for deterministic offline tests."""

import pytest


@pytest.fixture(autouse=True)
def disable_deepseek_for_tests(monkeypatch):
    for key in [
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_THINKING",
        "DEEPSEEK_REASONING_EFFORT",
    ]:
        monkeypatch.delenv(key, raising=False)
    # Pinned, not cleared: a maintainer who configures the documented
    # EMBEDDING_PROVIDER=openai would otherwise see retrieval tests fail on
    # their machine and pass in CI.
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local_hash")
