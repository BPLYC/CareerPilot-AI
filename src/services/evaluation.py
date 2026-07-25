"""Evaluation metric helpers."""

import re

from src.rag.knowledge_loader import load_all_knowledge_docs
from src.services.scoring import (
    action_evidence_rate,
    keyword_coverage,
    result_evidence_rate,
    skill_match_rate,
    star_coverage_rate,
)
from src.utils.text_utils import contains_keyword

SENSITIVE_TERMS = (
    "visa",
    "work authorization",
    "authorization",
    "authorized",
    "sponsorship",
    "sponsor",
    "salary",
    "compensation",
    "eligible",
    "eligibility",
    "legal",
)

FIXED_APPLICATION_FIELDS = ("why_this_role", "key_strengths", "project_example")
ROLE_SPECIFIC_FOCUS_AREAS = {"ml evaluation", "analytics validation", "software engineering"}
METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?x\b|\$\d+(?:\.\d+)?", re.IGNORECASE)


def rag_corpus_headroom(retrieved_context: dict) -> float:
    """What share of the knowledge base a single query pulled back.

    This is a corpus-size guard, not a measure of retrieval quality. Because
    fallback_retrieve always fills its k, the value is pinned at
    requested / corpus_size whenever the corpus exceeds the request: 0.36 today,
    and constant across cases. It moves only when a collection runs short, which
    is the failure it exists to catch -- retrieval that returns everything it
    has is not selecting at all, which is what 1.0 means.

    It deliberately does not claim to say whether the ranking is any good. That
    needs comparing the contexts retrieved for different roles; see
    summarize_comparison's rag_context_overlap.
    """

    if not retrieved_context:
        return 0.0

    corpus_size = len(load_all_knowledge_docs())
    if not corpus_size:
        return 0.0

    retrieved = sum(len(items) for items in retrieved_context.values())
    return round(min(retrieved / corpus_size, 1.0), 4)


def rag_context_overlap(contexts: list[dict]) -> float:
    """Mean pairwise Jaccard overlap of the snippets retrieved for each case.

    This is the metric that actually tracks ranking quality, and the one
    rag_corpus_headroom cannot be. 1.0 means every role received the same
    snippets, which is what the knowledge base produced before it was chunked
    per section; lower means retrieval discriminated between them. It degrades
    if ranking degrades, so it is worth watching rather than merely recording.
    """

    snippet_sets = [
        {snippet for items in context.values() for snippet in items}
        for context in contexts
        if context
    ]
    if len(snippet_sets) < 2:
        return 0.0

    scores = []
    for index, first in enumerate(snippet_sets):
        for second in snippet_sets[index + 1:]:
            union = first | second
            scores.append(len(first & second) / len(union) if union else 0.0)
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def _is_sensitive_question(question: str) -> bool:
    lowered = (question or "").lower()
    return any(term in lowered for term in SENSITIVE_TERMS)


def _application_answer_items(answers: dict) -> list[dict]:
    items = [
        {"question": field, "answer": answers.get(field, "")}
        for field in FIXED_APPLICATION_FIELDS
        if answers.get(field)
    ]
    for item in answers.get("custom_answers", []) or []:
        if item.get("answer"):
            items.append({"question": item.get("question", ""), "answer": item.get("answer", "")})
    return items


def _resume_evidence_terms(resume_profile: dict, match_report: dict) -> list[str]:
    terms = []
    terms.extend(resume_profile.get("skills", []) or [])
    terms.extend(match_report.get("matched_skills", []) or [])
    for project in resume_profile.get("projects", []) or []:
        if project.get("name"):
            terms.append(project["name"])
        terms.extend(project.get("technologies", []) or [])
    return [term for term in terms if term]


def _application_answer_evidence_rate(answers: dict, resume_profile: dict, match_report: dict) -> float:
    items = [
        item
        for item in _application_answer_items(answers)
        if not _is_sensitive_question(item.get("question", ""))
    ]
    if not items:
        return 0.0

    evidence_terms = _resume_evidence_terms(resume_profile, match_report)
    if not evidence_terms:
        return 0.0

    grounded = sum(
        1
        for item in items
        if any(contains_keyword(item.get("answer", ""), term) for term in evidence_terms)
        or "verified resume evidence" in item.get("answer", "").lower()
    )
    return grounded / len(items)


def _sensitive_refusal_count(answers: dict) -> int:
    count = 0
    for item in answers.get("custom_answers", []) or []:
        answer = (item.get("answer") or "").lower()
        if _is_sensitive_question(item.get("question", "")) and "must be filled by the applicant directly" in answer:
            count += 1
    return count


def _rate_with_field(items: list[dict], field: str) -> float:
    if not items:
        return 0.0
    return sum(1 for item in items if item.get(field)) / len(items)


def audit_unsupported_claims(
    bullets: list[str],
    resume_text: str,
    resume_profile: dict,
    *,
    candidate_skills: list[str] | None = None,
    candidate_projects: list[str] | None = None,
) -> dict:
    """Count explicit generated claims that have no resume evidence.

    Candidate lists make the proxy auditable: it only judges named claims the
    caller supplies (normally JD skills, plus controlled evaluation probes).
    """

    generated = " ".join(bullets)
    evidence = " ".join(
        [
            resume_text or "",
            " ".join(resume_profile.get("skills", []) or []),
            " ".join(
                str(value)
                for project in resume_profile.get("projects", []) or []
                for value in [project.get("name", ""), *(project.get("technologies", []) or [])]
                if value
            ),
            " ".join(
                str(value)
                for work in resume_profile.get("work_experience", []) or []
                for value in [work.get("company", ""), work.get("role", "")]
                if value and str(value).lower() != "unknown"
            ),
        ]
    )
    generated_metrics = set(METRIC_PATTERN.findall(generated))
    unsupported_metrics = sorted(metric for metric in generated_metrics if metric not in evidence)
    unsupported_skills = sorted(
        {
            skill
            for skill in candidate_skills or []
            if contains_keyword(generated, skill) and not contains_keyword(evidence, skill)
        }
    )
    unsupported_projects = sorted(
        {
            project
            for project in candidate_projects or []
            if contains_keyword(generated, project) and not contains_keyword(evidence, project)
        }
    )
    return {
        "unsupported_metric_count": len(unsupported_metrics),
        "unsupported_skill_mention_count": len(unsupported_skills),
        "unsupported_project_mention_count": len(unsupported_projects),
        "unsupported_claim_count": len(unsupported_metrics) + len(unsupported_skills) + len(unsupported_projects),
        "unsupported_metrics": unsupported_metrics,
        "unsupported_skills": unsupported_skills,
        "unsupported_projects": unsupported_projects,
    }


def evaluate_state(state: dict) -> dict:
    jd = state.get("jd_analysis") or {}
    resume = state.get("resume_profile") or {}
    report = state.get("match_report") or {}
    bullets = [item.get("optimized_bullet", "") for item in state.get("optimized_bullets", [])]
    optimized_text = " ".join(bullets)
    combined_resume_text = " ".join([state.get("raw_resume_text", ""), optimized_text])
    revised = [item for item in state.get("optimized_bullets", []) if item.get("is_revised_by_reflection")]
    bullet_count = len(bullets)
    answers = state.get("application_answers") or {}
    application_answers = _application_answer_items(answers)
    custom_answers = [item for item in answers.get("custom_answers", []) or [] if item.get("answer")]
    interview_questions = state.get("interview_questions", [])
    retrieved_context = state.get("retrieved_context") or {}
    workflow_trace = state.get("workflow_trace") or []
    keyword_before = keyword_coverage(state.get("raw_resume_text", ""), jd.get("keywords", []))
    keyword_after = keyword_coverage(combined_resume_text, jd.get("keywords", []))
    focus_areas = {(item.get("focus_area") or "").lower() for item in interview_questions}
    claim_audit = audit_unsupported_claims(
        bullets,
        state.get("raw_resume_text", ""),
        resume,
        candidate_skills=(jd.get("required_skills", []) or []) + (jd.get("preferred_skills", []) or []),
        candidate_projects=(
            state.get("evaluation_claim_candidates", {}).get("projects", [])
            + [item.get("context", "") for item in state.get("optimized_bullets", []) if item.get("context")]
        ),
    )
    return {
        "keyword_coverage_before": keyword_before,
        "keyword_coverage_after": keyword_after,
        "keyword_coverage_delta": keyword_after - keyword_before,
        "required_skills_match_rate": skill_match_rate(resume.get("skills", []), jd.get("required_skills", [])),
        "missing_skills_count": len(report.get("missing_skills", [])),
        "bullet_count_generated": bullet_count,
        "reflection_revision_rate": (len(revised) / bullet_count) if bullet_count else 0.0,
        "star_coverage_rate": star_coverage_rate(bullets),
        "action_evidence_rate": action_evidence_rate(bullets),
        "result_evidence_rate": result_evidence_rate(bullets),
        "match_score": report.get("overall_score", 0),
        "reference_score": state.get("reference_score") or report.get("overall_score", 0),
        "score_reliable": int(report.get("score_reliable", True)),
        "application_answer_count": len(application_answers),
        "custom_application_answer_count": len(custom_answers),
        "sensitive_application_refusal_count": _sensitive_refusal_count(answers),
        "application_answer_evidence_rate": _application_answer_evidence_rate(answers, resume, report),
        "interview_question_count": len(interview_questions),
        "interview_prep_notes_rate": _rate_with_field(interview_questions, "prep_notes"),
        "interview_project_followup_count": sum(
            1 for item in interview_questions if "project" in (item.get("focus_area") or "").lower()
        ),
        "interview_role_specific_count": len(focus_areas & ROLE_SPECIFIC_FOCUS_AREAS),
        "interview_required_skill_evidence_count": sum(
            1 for item in interview_questions if (item.get("focus_area") or "").lower() == "required skill evidence"
        ),
        "rag_snippet_count": sum(len(items) for items in retrieved_context.values()),
        "rag_corpus_headroom": rag_corpus_headroom(retrieved_context),
        "workflow_trace_count": len(workflow_trace),
        "reflection_review_count": sum(1 for item in workflow_trace if "ReflectionNode" in item),
        "phase_two_parallel_count": sum(1 for item in workflow_trace if "PhaseTwoParallelNode" in item),
        "unsupported_metric_count": claim_audit["unsupported_metric_count"],
        "unsupported_skill_mention_count": claim_audit["unsupported_skill_mention_count"],
        "unsupported_project_mention_count": claim_audit["unsupported_project_mention_count"],
        "unsupported_claim_count": claim_audit["unsupported_claim_count"],
    }
