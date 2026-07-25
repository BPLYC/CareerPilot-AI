from src.services.skill_taxonomy import skill_relationship, transferable_skills


def test_skill_relationship_distinguishes_exact_related_and_category():
    assert skill_relationship("Postgres", "PostgreSQL") == "exact"
    assert skill_relationship("Power BI", "Tableau") == "related"
    assert skill_relationship("Java", "Python") == "same_category"
    assert skill_relationship("React", "SQL") == "unrelated"


def test_transferable_skills_explain_gaps_without_claiming_exact_matches():
    result = transferable_skills(
        ["Power BI", "TensorFlow", "Java"],
        ["Tableau", "PyTorch", "Python", "Docker"],
    )

    assert result == {
        "Tableau": ["Power BI"],
        "PyTorch": ["TensorFlow"],
        "Python": ["Java"],
    }
