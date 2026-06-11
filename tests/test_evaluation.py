from src.services.evaluation import evaluate_state


def test_evaluation_counts_phase_two_quality_metrics():
    state = {
        "raw_resume_text": "Built a Flask API project with Python.",
        "jd_analysis": {
            "keywords": ["Python", "Docker"],
            "required_skills": ["Python", "Docker"],
        },
        "resume_profile": {
            "skills": ["Python", "Flask"],
            "projects": [{"name": "Task Manager", "technologies": ["Flask"]}],
        },
        "match_report": {
            "matched_skills": ["Python"],
            "missing_skills": ["Docker"],
        },
        "optimized_bullets": [
            {
                "optimized_bullet": "Implemented Docker deployment checks that improved release confidence.",
                "is_revised_by_reflection": True,
            }
        ],
        "application_answers": {
            "why_this_role": "I would connect this role to my Python project evidence.",
            "key_strengths": "My strongest fit is Python and Flask.",
            "project_example": "I would discuss Task Manager.",
            "custom_answers": [
                {
                    "question": "Why this internship?",
                    "answer": "Draft starter using verified resume evidence in Python.",
                },
                {
                    "question": "Will you require visa sponsorship?",
                    "answer": "Visa, work authorization, sponsorship, salary, and legal eligibility answers must be filled by the applicant directly.",
                },
            ],
        },
        "interview_questions": [
            {
                "question": "Walk me through Task Manager.",
                "focus_area": "Project deep dive",
                "prep_notes": "Use real implementation details.",
            },
            {
                "question": "How would you debug an API?",
                "focus_area": "Software engineering",
                "prep_notes": "Discuss logs and reproduction steps.",
            },
            {
                "question": "How have you used Python?",
                "focus_area": "Required skill evidence",
                "prep_notes": "Prepare a STAR-style answer.",
            },
        ],
    }

    metrics = evaluate_state(state)

    assert metrics["keyword_coverage_before"] == 0.5
    assert metrics["keyword_coverage_after"] == 1.0
    assert metrics["keyword_coverage_delta"] == 0.5
    assert metrics["star_coverage_rate"] == 1.0
    assert metrics["reflection_revision_rate"] == 1.0
    assert metrics["application_answer_count"] == 5
    assert metrics["custom_application_answer_count"] == 2
    assert metrics["sensitive_application_refusal_count"] == 1
    assert metrics["application_answer_evidence_rate"] == 1.0
    assert metrics["interview_prep_notes_rate"] == 1.0
    assert metrics["interview_project_followup_count"] == 1
    assert metrics["interview_role_specific_count"] == 1
    assert metrics["interview_required_skill_evidence_count"] == 1
