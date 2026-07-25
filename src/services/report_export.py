"""Render a completed analysis as Markdown for download.

Kept free of Streamlit so it can be tested directly and reused by anything that
needs the report as text.
"""

import re
from datetime import datetime

REVIEW_NOTICE = (
    "This report contains AI-generated drafts. Review and personalise everything "
    "before sending it to an employer."
)
SENSITIVE_NOTICE = (
    "Visa, work authorization, sponsorship, salary, and legal eligibility questions "
    "are left for you to answer directly."
)

ANSWER_LABELS = [
    ("why_this_role", "Why this role"),
    ("key_strengths", "Key strengths"),
    ("project_example", "Project example"),
]


def _bullet_list(items: list[str], empty: str) -> list[str]:
    return [f"- {item}" for item in items] if items else [f"_{empty}_"]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "role"


def suggested_filename(state: dict, now: datetime | None = None) -> str:
    """A filename carrying the role and date, safe on every platform."""

    role = (state.get("jd_analysis") or {}).get("job_title", "")
    stamp = (now or datetime.now()).strftime("%Y%m%d")
    return f"careerpilot-{_slugify(role)}-{stamp}.md"


def _match_section(state: dict) -> list[str]:
    report = state.get("match_report") or {}
    if not report:
        return []

    score = report.get("overall_score", 0)
    reference = state.get("reference_score")
    if reference is not None and reference != score:
        score_line = f"**Score:** {score}/100 (AI) · {reference}/100 (rule-based baseline)"
    else:
        score_line = f"**Score:** {score}/100"

    lines = [
        "## Match Report",
        "",
        score_line,
        "",
        "### Matched skills",
        *_bullet_list(report.get("matched_skills", []), "None identified."),
        "",
        "### Missing skills",
        *_bullet_list(report.get("missing_skills", []), "None identified."),
        "",
    ]
    breakdown = report.get("score_breakdown") or {}
    if breakdown:
        lines += [
            "### Score breakdown",
            *[f"- {name.replace('_', ' ').title()}: {value}" for name, value in breakdown.items()],
            "",
        ]
    if report.get("relevant_projects"):
        lines += ["### Relevant projects", *_bullet_list(report["relevant_projects"], ""), ""]
    if report.get("weak_sections"):
        lines += ["### Weak sections", *_bullet_list(report["weak_sections"], ""), ""]
    if report.get("explanation"):
        lines += ["### Analysis", "", report["explanation"], ""]
    return lines


HEADING_LIMIT = 60


def _heading_context(bullet: dict) -> str:
    """A short label for the suggestion heading.

    The schema means `context` to name the project or role, and the
    deterministic path supplies exactly that. Real models often return the whole
    rewritten bullet instead, which turns a heading into a paragraph, so long
    values are trimmed rather than trusted.
    """

    context = (bullet.get("context") or "").strip() or "Resume experience"
    if len(context) <= HEADING_LIMIT:
        return context
    return context[:HEADING_LIMIT].rsplit(" ", 1)[0].rstrip(",.;:") + "..."


def _bullets_section(state: dict) -> list[str]:
    bullets = state.get("optimized_bullets") or []
    if not bullets:
        return []

    lines = ["## Resume Bullet Suggestions", ""]
    for index, bullet in enumerate(bullets, start=1):
        lines.append(f"### {index}. {_heading_context(bullet)}")
        lines.append("")
        if bullet.get("original_bullet"):
            lines += ["**Before**", "", f"> {bullet['original_bullet']}", ""]
        lines += ["**After**", "", f"> {bullet.get('optimized_bullet', '')}", ""]
        if bullet.get("rationale"):
            lines += [f"_{bullet['rationale']}_", ""]
    return lines


def _application_section(state: dict) -> list[str]:
    answers = state.get("application_answers") or {}
    if not answers:
        return []

    lines = ["## Application Answer Starters", ""]
    for key, label in ANSWER_LABELS:
        if answers.get(key):
            lines += [f"### {label}", "", answers[key], ""]

    custom = answers.get("custom_answers") or []
    if custom:
        lines += ["### Your application questions", ""]
        for item in custom:
            lines += [f"**{item.get('question', 'Question')}**", "", item.get("answer", ""), ""]
    return lines


def _interview_section(state: dict) -> list[str]:
    questions = state.get("interview_questions") or []
    if not questions:
        return []

    lines = ["## Interview Practice", ""]
    for index, question in enumerate(questions, start=1):
        focus = question.get("focus_area", "Practice")
        lines.append(f"### {index}. {question.get('question', '')}")
        lines += ["", f"_Focus: {focus}_", ""]
        if question.get("prep_notes"):
            lines += [question["prep_notes"], ""]
    return lines


def _warnings_section(state: dict) -> list[str]:
    warnings = state.get("warnings") or []
    if not warnings:
        return []
    return ["## Warnings", "", *_bullet_list(warnings, ""), ""]


def build_markdown_report(state: dict, now: datetime | None = None) -> str:
    """Render the user-facing parts of a finished workflow state as Markdown."""

    if not state:
        return ""

    analysis = state.get("jd_analysis") or {}
    role = analysis.get("job_title") or "Internship role"
    generated = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# CareerPilot AI Report: {role}",
        "",
        f"_Generated {generated}_",
        "",
        f"> {REVIEW_NOTICE}",
        "",
    ]
    lines += _warnings_section(state)
    lines += _match_section(state)
    lines += _bullets_section(state)
    lines += _application_section(state)
    lines += _interview_section(state)
    lines += ["---", "", SENSITIVE_NOTICE, ""]

    return "\n".join(lines).rstrip() + "\n"
