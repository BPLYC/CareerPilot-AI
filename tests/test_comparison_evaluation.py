from src.services.comparison_evaluation import (
    METHOD_BASELINE,
    METHOD_FULL,
    METHOD_LLM_ONLY,
    evaluate_ablations,
    evaluate_controlled_reflection_probe,
    evaluate_methods,
    evaluate_score_perturbations,
    summarize_ablations,
    summarize_comparison,
)

RESUME = (
    "Alex Chen\nSkills: Python, SQL, Flask, Git, Docker, REST API\n"
    "Project: Personal Task Manager Web App using Flask and SQLite."
)

JD = "Software Engineering Intern required skills include Python, Git, databases, REST API, Docker."


def test_evaluate_methods_returns_all_comparison_methods():
    rows = evaluate_methods(RESUME, JD)

    assert [row["method"] for row in rows] == [METHOD_BASELINE, METHOD_LLM_ONLY, METHOD_FULL]
    assert rows[0]["bullet_count_generated"] == 0
    assert rows[1]["bullet_count_generated"] > 0
    assert rows[2]["bullet_count_generated"] > 0
    assert rows[0]["interview_question_count"] == 0
    assert rows[2]["interview_question_count"] > 0


def test_summarize_comparison_averages_numeric_metrics_by_method():
    rows = [
        {"case": "a", "method": METHOD_BASELINE, "keyword_coverage_delta": 0.0, "bullet_count_generated": 0},
        {"case": "b", "method": METHOD_BASELINE, "keyword_coverage_delta": 0.2, "bullet_count_generated": 0},
        {"case": "a", "method": METHOD_LLM_ONLY, "keyword_coverage_delta": 0.4, "bullet_count_generated": 2},
        {"case": "a", "method": METHOD_FULL, "keyword_coverage_delta": 0.6, "bullet_count_generated": 3},
    ]

    summary = summarize_comparison(rows)

    assert [row["method"] for row in summary] == [METHOD_BASELINE, METHOD_LLM_ONLY, METHOD_FULL]
    assert summary[0]["case_count"] == 2
    assert summary[0]["avg_keyword_coverage_delta"] == 0.1
    assert summary[1]["avg_bullet_count_generated"] == 2.0


def test_score_perturbations_are_monotonic():
    rows = evaluate_score_perturbations(RESUME, JD)
    by_variant = {row["variant"]: row for row in rows}

    assert all(row["passed"] for row in rows)
    assert by_variant["remove_required_skill"]["score_delta"] <= 0
    assert by_variant["remove_project_and_work_evidence"]["score_delta"] <= 0
    assert by_variant["add_irrelevant_skill"]["score_delta"] == 0


def test_ablations_change_only_the_target_workflow_components():
    rows = {row["ablation"]: row for row in evaluate_ablations(RESUME, JD)}

    assert rows["Full"]["rag_snippet_count"] > 0
    assert rows["Full-no-RAG"]["rag_snippet_count"] == 0
    assert rows["Full"]["reflection_review_count"] > 0
    assert rows["Full-no-reflection"]["reflection_review_count"] == 0
    assert {row["phase_two_parallel_count"] for row in rows.values()} == {1}
    assert len({row["reference_score"] for row in rows.values()}) == 1


def test_controlled_reflection_probe_reduces_unsupported_claims_without_losing_evidence():
    result = evaluate_controlled_reflection_probe()

    assert result["before_unsupported_claim_count"] == 3
    assert result["after_unsupported_claim_count"] == 0
    assert result["grounded_evidence_preserved"] == 1
    assert result["reflection_triggered"] == 1


def test_summarize_ablations_keeps_components_separate():
    summary = summarize_ablations(
        [
            {"case": "a", "ablation": "Full", "unsupported_claim_count": 0},
            {"case": "b", "ablation": "Full", "unsupported_claim_count": 2},
            {"case": "a", "ablation": "Full-no-RAG", "unsupported_claim_count": 3},
            {"case": "a", "ablation": "Full-no-reflection", "unsupported_claim_count": 1},
        ]
    )

    assert summary[0]["avg_unsupported_claim_count"] == 1.0
    assert summary[1]["avg_unsupported_claim_count"] == 3.0
