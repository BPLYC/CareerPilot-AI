from src.agents.match_scoring_agent import fallback_score_match
from src.services.scoring import keyword_coverage, matched_and_missing_skills, skill_match_rate


def test_keyword_coverage():
    assert keyword_coverage("Python and SQL project", ["Python", "SQL", "Docker"]) == 2 / 3
    assert keyword_coverage("Built APIs with Python.", ["Python"]) == 1.0
    assert keyword_coverage("参与大模型应用开发", ["大模型"]) == 1.0


def test_skill_matching():
    matched, missing = matched_and_missing_skills(["Python", "SQL"], ["Python", "Docker"])
    assert matched == ["Python"]
    assert missing == ["Docker"]
    assert skill_match_rate(["Python", "SQL"], ["Python", "Docker"]) == 0.5


def test_skill_aliases_match_without_changing_the_jd_label():
    matched, missing = matched_and_missing_skills(
        ["RESTful APIs", "Postgres", "ML", "torch"],
        ["REST API", "PostgreSQL", "Machine Learning", "PyTorch"],
    )
    assert matched == ["REST API", "PostgreSQL", "Machine Learning", "PyTorch"]
    assert missing == []


def test_empty_required_skills_do_not_receive_full_skill_credit():
    assert skill_match_rate(["Python"], []) == 0.0


def test_only_the_project_with_jd_evidence_is_relevant():
    profile = {
        "skills": ["Python", "React"],
        "projects": [
            {"name": "ML prototype", "description": "Trained a Python classifier.", "technologies": ["Python"]},
            {"name": "Weather UI", "description": "Built a browser interface.", "technologies": ["React"]},
        ],
        "education": [],
        "work_experience": [],
    }
    jd = {
        "required_skills": ["Python"],
        "preferred_skills": [],
        "keywords": ["machine learning"],
        "responsibilities": ["Train machine learning models"],
        "tools_and_technologies": ["Python"],
        "education_requirements": "",
    }

    report = fallback_score_match(profile, jd)

    assert report["relevant_projects"] == ["ML prototype"]
    assert report["score_breakdown"]["project_evidence"] > 0


def test_unrelated_projects_do_not_increase_experience_score():
    jd = {
        "required_skills": ["Python"],
        "preferred_skills": [],
        "keywords": ["machine learning"],
        "responsibilities": [],
        "tools_and_technologies": ["Python"],
        "education_requirements": "",
    }
    base = {"skills": [], "projects": [], "education": [], "work_experience": []}
    with_projects = {
        **base,
        "projects": [
            {"name": "Weather UI", "description": "Styled a browser page.", "technologies": ["React"]},
            {"name": "Recipe book", "description": "Collected recipes.", "technologies": []},
        ],
    }

    empty_report = fallback_score_match(base, jd)
    project_report = fallback_score_match(with_projects, jd)

    assert project_report["score_breakdown"]["experience_evidence"] == empty_report["score_breakdown"]["experience_evidence"]
    assert project_report["overall_score"] == empty_report["overall_score"]


def test_score_is_the_sum_of_bounded_components():
    report = fallback_score_match(
        {"skills": ["Python"], "projects": [], "education": [], "work_experience": []},
        {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "keywords": [],
            "responsibilities": [],
            "tools_and_technologies": [],
            "education_requirements": "",
        },
    )

    assert report["overall_score"] == sum(report["score_breakdown"].values())
    assert report["score_reliable"] is True


def test_score_explains_exact_and_transferable_skill_evidence_separately():
    report = fallback_score_match(
        {"skills": ["Python", "Power BI"], "projects": [], "education": [], "work_experience": []},
        {
            "required_skills": ["Python", "Tableau"],
            "preferred_skills": [],
            "keywords": [],
            "responsibilities": [],
            "tools_and_technologies": [],
            "education_requirements": "",
        },
    )

    assert report["score_evidence"]["required_skills"] == ["Python"]
    assert report["transferable_skills"] == {"Tableau": ["Power BI"]}
    assert report["matched_skills"] == ["Python"]
    assert report["missing_skills"] == ["Tableau"]
