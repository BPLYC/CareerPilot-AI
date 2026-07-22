"""Guards for the reproducibility of evaluation runs.

Evaluation is used as the regression check for every optimization slice, so it
must not silently depend on machine-local state: a discoverable .env, or a
data/vectorstore/ directory that git does not track.
"""

import os

from src.rag.build_vectorstore import DISABLE_VECTORSTORE_ENV, get_or_build_vectorstore


def test_vectorstore_can_be_disabled_for_reproducible_retrieval(monkeypatch):
    monkeypatch.setenv(DISABLE_VECTORSTORE_ENV, "1")
    assert get_or_build_vectorstore() is None


def test_eval_script_disables_llm_and_vectorstore(monkeypatch):
    import eval.run_eval as run_eval

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-used")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.delenv(DISABLE_VECTORSTORE_ENV, raising=False)

    run_eval.use_deterministic_agents()

    # A key reachable from any parent directory would otherwise put every agent
    # on its live-LLM branch, which costs money and returns different numbers.
    assert not os.environ.get("DEEPSEEK_API_KEY")
    assert not os.environ.get("DEEPSEEK_MODEL")
    assert os.environ.get(DISABLE_VECTORSTORE_ENV)
