"""Text cleaning, truncation, and simple keyword utilities."""

import re
from typing import Iterable, List, Tuple


def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate_text(text: str, max_chars: int = 16000) -> Tuple[str, bool]:
    text = text or ""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars].strip(), True


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", "", (value or "").lower()).strip(".")


def contains_keyword(text: str, keyword: str) -> bool:
    normalized_text = (text or "").lower()
    keyword = (keyword or "").strip().lower()
    if not keyword:
        return False
    if len(keyword.split()) > 1:
        return keyword in normalized_text
    return normalize_token(keyword) in {normalize_token(token) for token in normalized_text.split()}


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = (value or "").strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result
