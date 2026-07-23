"""Multi-JD comparison: ranking, shared gaps, and per-job failure isolation."""

import pytest

from src.services.multi_jd import (
    JobComparison,
    compare_jobs,
    find_common_missing_skills,
    to_table_rows,
)
from src.ui.tabs.compare_tab import split_job_descriptions

RESUME = "Alex Chen\nSkills: Python, SQL, Flask\nProject: Task Manager using Flask and SQLite."


def fake_runner(scores):
    """A runner that returns a scripted state per call, in order."""

    calls = iter(scores)

    def runner(state):
        score, missing = next(calls)
        return {
            "match_report": {
                "overall_score": score,
                "matched_skills": ["Python"],
                "missing_skills": list(missing),
                "relevant_projects": [],
                "weak_sections": [],
                "explanation": "",
            },
            "jd_analysis": {"job_title": f"Role {score}"},
            "optimized_bullets": [{"context": "x", "optimized_bullet": "y", "rationale": "z"}],
            "errors": [],
        }

    return runner


def test_jobs_are_ranked_best_first():
    result = compare_jobs(
        RESUME,
        [("Low", "jd one"), ("High", "jd two"), ("Mid", "jd three")],
        runner=fake_runner([(40, []), (85, []), (60, [])]),
        use_cache=False,
    )

    assert [job.label for job in result.ranked] == ["High", "Mid", "Low"]
    assert result.best.label == "High"
    assert result.best.score == 85


def test_common_missing_skills_are_the_intersection():
    result = compare_jobs(
        RESUME,
        [("A", "jd"), ("B", "jd"), ("C", "jd")],
        runner=fake_runner([
            (50, ["Docker", "AWS", "PyTorch"]),
            (60, ["AWS", "PyTorch", "Spark"]),
            (70, ["PyTorch", "AWS"]),
        ]),
        use_cache=False,
    )

    # Docker and Spark appear in only some roles; AWS and PyTorch in all three.
    # Order follows the first job's list, not set iteration order.
    assert result.common_missing_skills == ["AWS", "PyTorch"]


def test_no_common_gap_when_roles_want_different_things():
    result = compare_jobs(
        RESUME,
        [("A", "jd"), ("B", "jd")],
        runner=fake_runner([(50, ["Docker"]), (60, ["Tableau"])]),
        use_cache=False,
    )

    assert result.common_missing_skills == []


def test_a_single_job_has_no_shared_gap():
    # An intersection over one set is just that set, which would be a
    # misleading answer to "what do all these roles want".
    assert find_common_missing_skills([JobComparison(label="A", job_title="A", score=50, missing_skills=["AWS"])]) == []


def test_one_failing_job_does_not_lose_the_others():
    def flaky(state):
        if "boom" in state["raw_jd_text"]:
            raise RuntimeError("workflow exploded")
        return {
            "match_report": {
                "overall_score": 70,
                "matched_skills": [],
                "missing_skills": [],
                "relevant_projects": [],
                "weak_sections": [],
                "explanation": "",
            },
            "jd_analysis": {"job_title": "Fine"},
            "errors": [],
        }

    result = compare_jobs(
        RESUME,
        [("Good", "a normal jd"), ("Bad", "boom"), ("AlsoGood", "another jd")],
        runner=flaky,
        use_cache=False,
    )

    assert len([job for job in result.jobs if job.failed]) == 1
    assert result.best.score == 70
    # Failures sort last so they never occupy the top recommendation.
    assert result.ranked[-1].label == "Bad"
    assert "exploded" in result.ranked[-1].failure_reason


def test_empty_job_description_is_reported_not_run():
    def should_not_run(state):
        raise AssertionError("the workflow ran for an empty job description")

    result = compare_jobs(RESUME, [("Blank", "   ")], runner=should_not_run, use_cache=False)

    assert result.jobs[0].failed
    assert "Empty" in result.jobs[0].failure_reason


def test_table_rows_are_ranked_and_labelled():
    result = compare_jobs(
        RESUME,
        [("Low", "jd"), ("High", "jd")],
        runner=fake_runner([(40, ["AWS"]), (90, [])]),
        use_cache=False,
    )

    rows = to_table_rows(result)

    assert rows[0]["Rank"] == 1
    assert rows[0]["Job"] == "High"
    assert rows[0]["Status"] == "OK"
    assert rows[1]["Job"] == "Low"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("first jd\n===\nsecond jd", [("Job 1", "first jd"), ("Job 2", "second jd")]),
        ("# AI Intern\nbody one\n===\n# SWE\nbody two", [("AI Intern", "body one"), ("SWE", "body two")]),
        ("only one jd", [("Job 1", "only one jd")]),
        ("", []),
        ("\n===\n\n===\n", []),
        ("# \nbody", [("Job 1", "body")]),
    ],
)
def test_split_job_descriptions(text, expected):
    assert split_job_descriptions(text) == expected


def test_real_workflow_across_the_sample_jds():
    """End to end on the deterministic path, with the bundled sample data."""

    from eval.run_eval import use_deterministic_agents

    use_deterministic_agents()
    from src.ui.sample_data import SAMPLE_JDS, read_text

    resume = read_text("data/sample_resume.txt")
    jobs = [(role, read_text(path)) for role, path in SAMPLE_JDS.items()]

    result = compare_jobs(resume, jobs, use_cache=False)

    assert len(result.jobs) == len(SAMPLE_JDS)
    assert all(not job.failed for job in result.jobs)
    assert result.best is not None
    scores = [job.score for job in result.ranked]
    assert scores == sorted(scores, reverse=True)
