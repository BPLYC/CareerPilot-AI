from src.services import cache


def sample_state():
    return {
        "raw_resume_text": "Alex Chen private resume text",
        "raw_jd_text": "Private job description text",
        "match_report": {
            "overall_score": 70,
            "matched_skills": ["Python"],
            "missing_skills": [],
        },
        "optimized_bullets": [{"optimized_bullet": "Built a project."}],
        "workflow_trace": ["done"],
    }


def test_get_cache_key_is_stable_and_input_sensitive():
    key = cache.get_cache_key("resume", "jd", ["q"])
    assert key == cache.get_cache_key("resume", "jd", ["q"])
    assert key != cache.get_cache_key("resume", "jd", ["different"])
    assert key != cache.get_cache_key("other resume", "jd", ["q"])


def test_save_to_cache_does_not_persist_raw_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
    key = cache.get_cache_key("resume", "jd")

    cache.save_to_cache(key, sample_state())

    stored = (tmp_path / f"{key}.json").read_text(encoding="utf-8")
    assert "Alex Chen private resume text" not in stored
    assert "Private job description text" not in stored


def test_round_trip_preserves_derived_outputs_but_not_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
    key = cache.get_cache_key("resume", "jd")

    cache.save_to_cache(key, sample_state())
    loaded = cache.load_from_cache(key)

    assert loaded is not None
    assert loaded["match_report"]["overall_score"] == 70
    assert loaded["optimized_bullets"][0]["optimized_bullet"] == "Built a project."
    assert not loaded.get("raw_resume_text")
    assert not loaded.get("raw_jd_text")


def test_save_to_cache_does_not_mutate_caller_state(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
    state = sample_state()

    cache.save_to_cache(cache.get_cache_key("resume", "jd"), state)

    # The in-memory state the UI keeps rendering must be untouched.
    assert state["raw_resume_text"] == "Alex Chen private resume text"


def test_load_from_cache_missing_key_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
    assert cache.load_from_cache("does-not-exist") is None
