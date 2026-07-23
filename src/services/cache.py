"""Simple JSON cache for completed workflow states."""

import hashlib
import json
import os

CACHE_DIR = os.path.join("outputs", "cache")
CACHE_VERSION = "v3"


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
        json.dump(state, handle, ensure_ascii=False, indent=2)
