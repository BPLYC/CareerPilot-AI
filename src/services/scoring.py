"""Deterministic scoring helpers used by agents and evaluation."""

from collections.abc import Iterable

from src.services.skill_taxonomy import canonical_skill
from src.utils.text_utils import contains_keyword, normalize_token, unique_preserve_order


def matched_and_missing_skills(resume_skills: Iterable[str], required_skills: Iterable[str]) -> tuple[list[str], list[str]]:
    resume_tokens = {normalize_token(canonical_skill(skill)) for skill in resume_skills}
    matched = []
    missing = []
    for skill in required_skills:
        key = normalize_token(canonical_skill(skill))
        if key and key in resume_tokens:
            matched.append(skill)
        else:
            missing.append(skill)
    return unique_preserve_order(matched), unique_preserve_order(missing)


def skill_match_rate(resume_skills: Iterable[str], required_skills: Iterable[str]) -> float:
    required = list(required_skills)
    if not required:
        return 0.0
    matched, _ = matched_and_missing_skills(resume_skills, required)
    return len(matched) / len(required)


def keyword_coverage(text: str, keywords: Iterable[str]) -> float:
    keywords = unique_preserve_order(keywords)
    if not keywords:
        return 0.0
    hits = sum(1 for keyword in keywords if contains_keyword(text, keyword))
    return hits / len(keywords)


ACTION_WORDS = {
    "built", "developed", "implemented", "analyzed", "created", "improved",
    "assisted", "contributed", "开发", "构建", "实现", "分析", "创建", "优化", "协助",
}
RESULT_WORDS = {
    "result", "achieved", "improved", "reduced", "increased", "enabled",
    "supporting", "helped", "结果", "提升", "降低", "减少", "增加", "支持", "完成",
}


def _term_coverage_rate(bullets: Iterable[str], terms: set[str]) -> float:
    bullets = list(bullets)
    if not bullets:
        return 0.0
    return sum(1 for bullet in bullets if any(term in (bullet or "").lower() for term in terms)) / len(bullets)


def action_evidence_rate(bullets: Iterable[str]) -> float:
    return _term_coverage_rate(bullets, ACTION_WORDS)


def result_evidence_rate(bullets: Iterable[str]) -> float:
    return _term_coverage_rate(bullets, RESULT_WORDS)


def star_coverage_rate(bullets: Iterable[str]) -> float:
    """Language-aware STAR proxy: a bullet has both an action and a result cue."""

    bullets = list(bullets)
    if not bullets:
        return 0.0
    covered = sum(
        1
        for bullet in bullets
        if any(term in (bullet or "").lower() for term in ACTION_WORDS)
        and any(term in (bullet or "").lower() for term in RESULT_WORDS)
    )
    return covered / len(bullets)
