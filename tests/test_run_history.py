import json
import sqlite3

from src.services.run_history import list_recent_runs, record_run, summarize_state


def sample_state():
    return {
        "raw_resume_text": "Alex Chen private resume text",
        "raw_jd_text": "Private job description text",
        "jd_analysis": {"job_title": "AI Intern"},
        "match_report": {
            "overall_score": 82,
            "matched_skills": ["Python", "SQL"],
            "missing_skills": ["PyTorch"],
        },
        "optimized_bullets": [{"optimized_bullet": "Built a project."}],
        "application_answers": {
            "why_this_role": "Draft answer",
            "key_strengths": "Draft strengths",
            "custom_answers": [{"question": "Why us?", "answer": "Draft"}],
        },
        "interview_questions": [{"question": "Tell me about Python."}],
        "warnings": ["Review before submitting."],
        "errors": [],
    }


def test_summarize_state_counts_outputs():
    summary = summarize_state(sample_state())

    assert summary["job_title"] == "AI Intern"
    assert summary["match_score"] == 82
    assert summary["matched_skills_count"] == 2
    assert summary["missing_skills_count"] == 1
    assert summary["optimized_bullets_count"] == 1
    assert summary["application_answer_count"] == 3
    assert summary["interview_question_count"] == 1


def test_record_run_stores_summary_without_raw_inputs(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    run_id = record_run("cache-key", sample_state(), str(db_path))

    rows = list_recent_runs(db_path=str(db_path))
    assert rows[0]["id"] == run_id
    assert rows[0]["job_title"] == "AI Intern"
    assert rows[0]["match_score"] == 82

    with sqlite3.connect(db_path) as conn:
        stored_json = conn.execute("SELECT summary_json FROM run_history").fetchone()[0]

    summary = json.loads(stored_json)
    assert summary["matched_skills"] == ["Python", "SQL"]
    assert "raw_resume_text" not in summary
    assert "raw_jd_text" not in summary
    assert "Alex Chen private resume text" not in stored_json
    assert "Private job description text" not in stored_json
