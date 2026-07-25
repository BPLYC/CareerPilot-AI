"""Comparison runners for evaluation ablations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from numbers import Number

from src.agents.application_answer_agent import application_answer_node
from src.agents.final_report_agent import final_report_node
from src.agents.interview_coach_agent import interview_coach_node
from src.agents.jd_analyzer_agent import fallback_analyze_jd, jd_analyzer_node
from src.agents.match_scoring_agent import fallback_score_match, match_scoring_node
from src.agents.resume_optimizer_agent import resume_optimizer_node
from src.agents.resume_parser_agent import fallback_parse_resume, resume_parser_node
from src.services.evaluation import evaluate_state
from src.workflow.careerpilot_graph import run_workflow
from src.workflow.state import create_initial_state

METHOD_BASELINE = "Baseline"
METHOD_LLM_ONLY = "LLM-only"
METHOD_FULL = "CareerPilot Full"
METHOD_ORDER = [METHOD_BASELINE, METHOD_LLM_ONLY, METHOD_FULL]


def _merge_state(state: dict, update: dict) -> dict:
    merged = dict(state)
    for key, value in update.items():
        if key in {"workflow_trace", "errors", "warnings", "fallback_nodes"}:
            merged[key] = list(merged.get(key, [])) + list(value or [])
        else:
            merged[key] = value
    return merged


def _run_nodes(state: dict, nodes: list[Callable[[dict], dict]]) -> dict:
    current = dict(state)
    for node in nodes:
        current = _merge_state(current, node(current))
    return current


def run_baseline(resume_text: str, jd_text: str) -> dict:
    """Run deterministic parsing, JD analysis, and scoring only."""

    state = create_initial_state(resume_text, jd_text)
    resume_profile = fallback_parse_resume(resume_text)
    jd_analysis = fallback_analyze_jd(jd_text)
    match_report = fallback_score_match(resume_profile, jd_analysis)
    state = _merge_state(
        state,
        {
            "resume_profile": resume_profile,
            "jd_analysis": jd_analysis,
            "match_report": match_report,
            "workflow_trace": [
                "Baseline: Deterministic resume parsing completed.",
                "Baseline: Deterministic JD analysis completed.",
                "Baseline: Deterministic match scoring completed.",
            ],
        },
    )
    return _merge_state(state, final_report_node(state))


def run_llm_only(resume_text: str, jd_text: str) -> dict:
    """Run generation without RAG retrieval, low-match branching, or reflection."""

    state = create_initial_state(resume_text, jd_text)
    return _run_nodes(
        state,
        [
            resume_parser_node,
            jd_analyzer_node,
            match_scoring_node,
            resume_optimizer_node,
            application_answer_node,
            interview_coach_node,
            final_report_node,
        ],
    )


def run_careerpilot_full(resume_text: str, jd_text: str) -> dict:
    """Run the full CareerPilot graph/fallback workflow."""

    return run_workflow(create_initial_state(resume_text, jd_text))


def evaluate_methods(resume_text: str, jd_text: str) -> list[dict]:
    runners = {
        METHOD_BASELINE: run_baseline,
        METHOD_LLM_ONLY: run_llm_only,
        METHOD_FULL: run_careerpilot_full,
    }
    rows = []
    for method in METHOD_ORDER:
        state = runners[method](resume_text, jd_text)
        rows.append({"method": method, **evaluate_state(state)})
    return rows


def summarize_comparison(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["method"]].append(row)

    summary_rows = []
    for method in METHOD_ORDER:
        method_rows = grouped.get(method, [])
        if not method_rows:
            continue
        metric_names = [
            key
            for key, value in method_rows[0].items()
            if key not in {"case", "method"} and isinstance(value, Number)
        ]
        summary = {"method": method, "case_count": len(method_rows)}
        for metric in metric_names:
            average = sum(float(row.get(metric, 0.0)) for row in method_rows) / len(method_rows)
            summary[f"avg_{metric}"] = round(average, 4)
        summary_rows.append(summary)
    return summary_rows
