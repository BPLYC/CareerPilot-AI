"""Simple JSON cache for completed workflow states."""

import hashlib
import json
import os
from typing import Optional


CACHE_DIR = os.path.join("outputs", "cache")


def get_cache_key(resume_text: str, jd_text: str) -> str:
    content = (resume_text or "") + "|||" + (jd_text or "")
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def load_from_cache(key: str) -> Optional[dict]:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_to_cache(key: str, state: dict) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
