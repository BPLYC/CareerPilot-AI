"""Timeout and retry settings must be configurable without editing source."""

import pytest

from src.services.provider_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    get_provider_config,
)


def test_defaults_match_the_previously_hardcoded_values():
    config = get_provider_config()

    assert config.request_timeout == DEFAULT_REQUEST_TIMEOUT == 60
    assert config.max_retries == DEFAULT_MAX_RETRIES == 2


def test_settings_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_REQUEST_TIMEOUT", "300")
    monkeypatch.setenv("DEEPSEEK_MAX_RETRIES", "5")

    config = get_provider_config()

    assert config.request_timeout == 300
    assert config.max_retries == 5


@pytest.mark.parametrize("bad_value", ["", "abc", "0", "-1", "12.5"])
def test_unusable_values_fall_back_to_the_default(monkeypatch, bad_value):
    # A typo in .env should not silently produce a zero timeout, which would
    # make every request fail instantly.
    monkeypatch.setenv("DEEPSEEK_REQUEST_TIMEOUT", bad_value)

    assert get_provider_config().request_timeout == DEFAULT_REQUEST_TIMEOUT
