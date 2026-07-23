"""SQLite-backed local run history for summary metadata only."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any

HISTORY_DB_PATH = os.path.join("outputs", "history.sqlite3")


def _connect(db_path: str = HISTORY_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_history(db_path: str = HISTORY_DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                job_title TEXT NOT NULL,
                match_score INTEGER,
                matched_skills_count INTEGER NOT NULL,
                missing_skills_count INTEGER NOT NULL,
                optimized_bullets_count INTEGER NOT NULL,
                application_answer_count INTEGER NOT NULL,
                interview_question_count INTEGER NOT NULL,
                warnings_count INTEGER NOT NULL,
                errors_count INTEGER NOT NULL,
                summary_json TEXT NOT NULL
            )
            """
        )


def _count_application_answers(answers: dict[str, Any]) -> int:
    fixed_fields = ["why_this_role", "key_strengths", "project_example"]
    count = sum(1 for field in fixed_fields if answers.get(field))
    count += len(answers.get("custom_answers", []) or [])
    return count


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    jd_analysis = state.get("jd_analysis") or {}
    match_report = state.get("match_report") or {}
    matched_skills = match_report.get("matched_skills") or []
    missing_skills = match_report.get("missing_skills") or []
    application_answers = state.get("application_answers") or {}

    return {
        "job_title": jd_analysis.get("job_title") or "Unknown role",
        "match_score": match_report.get("overall_score"),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_skills_count": len(matched_skills),
        "missing_skills_count": len(missing_skills),
        "optimized_bullets_count": len(state.get("optimized_bullets") or []),
        "application_answer_count": _count_application_answers(application_answers),
        "interview_question_count": len(state.get("interview_questions") or []),
        "warnings_count": len(state.get("warnings") or []),
        "errors_count": len(state.get("errors") or []),
    }


def record_run(cache_key: str, state: dict[str, Any], db_path: str = HISTORY_DB_PATH) -> int:
    initialize_history(db_path)
    summary = summarize_state(state)
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO run_history (
                created_at,
                cache_key,
                job_title,
                match_score,
                matched_skills_count,
                missing_skills_count,
                optimized_bullets_count,
                application_answer_count,
                interview_question_count,
                warnings_count,
                errors_count,
                summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                cache_key,
                summary["job_title"],
                summary["match_score"],
                summary["matched_skills_count"],
                summary["missing_skills_count"],
                summary["optimized_bullets_count"],
                summary["application_answer_count"],
                summary["interview_question_count"],
                summary["warnings_count"],
                summary["errors_count"],
                json.dumps(summary, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def list_recent_runs(limit: int = 10, db_path: str = HISTORY_DB_PATH) -> list[dict[str, Any]]:
    if not os.path.exists(db_path):
        return []
    initialize_history(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                created_at,
                job_title,
                match_score,
                matched_skills_count,
                missing_skills_count,
                optimized_bullets_count,
                application_answer_count,
                interview_question_count,
                warnings_count,
                errors_count,
                summary_json
            FROM run_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
