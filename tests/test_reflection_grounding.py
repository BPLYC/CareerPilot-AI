from src.agents.reflection_agent import reflection_node


def _state(bullet):
    return {
        "raw_resume_text": "Built Task Manager with Python and Flask.",
        "resume_profile": {
            "skills": ["Python", "Flask"],
            "projects": [{"name": "Task Manager", "technologies": ["Python", "Flask"]}],
            "work_experience": [],
        },
        "jd_analysis": {"required_skills": ["Python", "Kubernetes"], "preferred_skills": []},
        "optimized_bullets": [bullet],
        "reflection_iteration": 0,
    }


def test_reflection_flags_unsupported_skill_and_project_context():
    update = reflection_node(
        _state(
            {
                "context": "Quantum Ledger",
                "optimized_bullet": "Built Quantum Ledger with Python and Kubernetes.",
            }
        )
    )

    assert update["has_exaggeration"] is True
    assert "Kubernetes" in update["reflection_feedback"]
    assert "不存在的项目或经历" in update["reflection_feedback"]


def test_reflection_preserves_supported_skill_and_context():
    update = reflection_node(
        _state(
            {
                "context": "Task Manager",
                "optimized_bullet": "Built Task Manager with Python and Flask.",
            }
        )
    )

    assert update["has_exaggeration"] is False
