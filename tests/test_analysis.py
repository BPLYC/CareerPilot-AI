"""Unit tests for the UI analysis runner, with Streamlit stubbed out."""

import pytest

from src.ui import analysis


class _FakeStatus:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def update(self, *args, **kwargs):
        pass


class _FakeSt:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def write(self, *args, **kwargs):
        pass

    def status(self, *args, **kwargs):
        return _FakeStatus()


@pytest.fixture
def fake_st(monkeypatch):
    st = _FakeSt()
    monkeypatch.setattr(analysis, "st", st)
    return st


def test_cache_hit_does_not_record_history_again(fake_st, monkeypatch):
    recorded = []
    monkeypatch.setattr(
        analysis, "load_from_cache", lambda key: {"match_report": {"overall_score": 70}}
    )
    monkeypatch.setattr(analysis, "record_run", lambda key, state: recorded.append(key))

    result = analysis.run_analysis("resume", "jd")

    assert result["match_report"]["overall_score"] == 70
    # Viewing a cached result is not a new analysis; history must not grow.
    assert recorded == []
    assert any("缓存" in message for message in fake_st.infos)


def test_online_run_rejects_cached_fallback_result():
    cached = {
        "match_report": {"overall_score": 8},
        "fallback_nodes": ["ResumeParserNode", "JDAnalyzerNode", "MatchScoringNode"],
    }

    assert not analysis.cache_result_is_usable(cached, llm_available=True)
    assert analysis.cache_result_is_usable(cached, llm_available=False)


def test_online_run_rejects_legacy_connection_error_cache():
    cached = {
        "match_report": {"overall_score": 8},
        "errors": ["ResumeParserNode failed: Connection error."],
    }

    assert not analysis.cache_result_is_usable(cached, llm_available=True)


def test_fresh_run_records_history_exactly_once(fake_st, monkeypatch):
    recorded = []
    monkeypatch.setattr(analysis, "load_from_cache", lambda key: None)
    monkeypatch.setattr(analysis, "save_to_cache", lambda key, state: None)
    monkeypatch.setattr(analysis, "record_run", lambda key, state: recorded.append(key))

    result = analysis.run_analysis("Resume mentioning Python", "Role needs Python", [])

    assert result is not None
    assert len(recorded) == 1


def test_completed_analysis_survives_a_cache_write_failure(fake_st, monkeypatch):
    recorded = []

    def _boom(key, state):
        raise OSError("disk full")

    monkeypatch.setattr(analysis, "load_from_cache", lambda key: None)
    monkeypatch.setattr(analysis, "save_to_cache", _boom)
    monkeypatch.setattr(analysis, "record_run", lambda key, state: recorded.append(key))

    # Caching is an optimization; its failure must not sink a finished analysis.
    result = analysis.run_analysis("Resume mentioning Python", "Role needs Python", [])

    assert result is not None
    assert result.get("match_report")
    assert len(recorded) == 1
    assert any("缓存" in message for message in fake_st.warnings)
