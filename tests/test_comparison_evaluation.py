from src.services.comparison_evaluation import (
    METHOD_BASELINE,
    METHOD_FULL,
    METHOD_LLM_ONLY,
    evaluate_methods,
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
