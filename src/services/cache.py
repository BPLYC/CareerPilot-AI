"""Simple JSON cache for completed workflow states."""

import hashlib
import json
import os

CACHE_DIR = os.path.join("outputs", "cache")
CACHE_VERSION = "v6"

# Raw resume and job-description text are inputs, never rendered from the cached
# state, and the project promises they are not persisted. Redact them before the
# workflow state is written to disk.
_SENSITIVE_KEYS = ("raw_resume_text", "raw_jd_text")


def _redact_sensitive(state: dict) -> dict:
    redacted = dict(state)
    for key in _SENSITIVE_KEYS:
        if key in redacted:
            redacted[key] = ""
    return redacted


def get_cache_key(resume_text: str, jd_text: str, application_questions: list[str] | None = None) -> str:
    questions = json.dumps(application_questions or [], ensure_ascii=False, sort_keys=True)
    content = CACHE_VERSION + "|||" + (resume_text or "") + "|||" + (jd_text or "") + "|||" + questions
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def load_from_cache(key: str) -> dict | None:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_to_cache(key: str, state: dict) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(_redact_sensitive(state), handle, ensure_ascii=False, indent=2)
