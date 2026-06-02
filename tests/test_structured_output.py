from src.models.schemas import BulletSuggestion, JobDescriptionAnalysis, MatchReport, ResumeProfile
from src.services.structured_output import model_to_dict, validate_dict


def test_jd_analysis_normalizes_string_list_fields():
    analysis = validate_dict(
        JobDescriptionAnalysis,
        {
            "job_title": "AI Intern",
            "company": None,
            "education_requirements": ["Computer Science", "Data Science"],
            "experience_requirements": [],
        },
    )
    data = model_to_dict(analysis)
    assert data["company"] == "unknown"
    assert data["education_requirements"] == "Computer Science; Data Science"
    assert data["experience_requirements"] == ""


def test_bullet_suggestion_accepts_minimal_llm_shape():
    suggestion = validate_dict(
        BulletSuggestion,
        {
            "bullet": "Implemented a Python dashboard using resume-supported project evidence.",
        },
    )
    data = model_to_dict(suggestion)
    assert data["context"] == "Resume experience"
    assert data["optimized_bullet"].startswith("Implemented")
    assert data["rationale"]


def test_bullet_suggestion_accepts_original_optimized_aliases():
    suggestion = validate_dict(
        BulletSuggestion,
        {
            "original": "Built a dashboard.",
            "optimized": "Built a Python dashboard aligned with the target analyst role.",
            "context": "Sales Data Dashboard",
            "reason": "Uses verified project evidence.",
        },
    )
    data = model_to_dict(suggestion)
    assert data["original_bullet"] == "Built a dashboard."
    assert data["optimized_bullet"].startswith("Built a Python")
    assert data["rationale"] == "Uses verified project evidence."


def test_bullet_suggestion_accepts_suggested_text_alias():
    suggestion = validate_dict(
        BulletSuggestion,
        {
            "suggested_text": "Evaluated model output using verified project evidence.",
        },
    )
    data = model_to_dict(suggestion)
    assert data["optimized_bullet"].startswith("Evaluated")


def test_resume_profile_accepts_nested_strings():
    profile = validate_dict(
        ResumeProfile,
        {
            "education": "University of California, B.S. Computer Science",
            "projects": ["Movie Recommendation System: Built with Python and scikit-learn."],
            "work_experience": ["Data Analyst Intern, Local Startup: Assisted dashboard work."],
        },
    )
    data = model_to_dict(profile)
    assert data["education"][0]["school"].startswith("University")
    assert data["projects"][0]["name"] == "Movie Recommendation System"
    assert data["work_experience"][0]["role"] == "Data Analyst Intern"


def test_resume_profile_accepts_string_collections():
    profile = validate_dict(
        ResumeProfile,
        {
            "skills": "Python, SQL, Flask",
            "projects": "Movie Recommendation System: Built with Python.",
            "work_experience": "Data Analyst Intern, Local Startup: Assisted dashboard work.",
        },
    )
    data = model_to_dict(profile)
    assert data["skills"] == ["Python", "SQL", "Flask"]
    assert data["projects"][0]["description"].startswith("Movie Recommendation")
    assert data["work_experience"][0]["description"].startswith("Data Analyst")


def test_bullet_suggestion_uses_longest_text_when_field_name_is_unknown():
    suggestion = validate_dict(
        BulletSuggestion,
        {
            "id": "resume_bullet_001",
            "generated_text": "Analyzed customer behavior with verified dashboard project evidence.",
        },
    )
    data = model_to_dict(suggestion)
    assert data["optimized_bullet"].startswith("Analyzed customer")


def test_match_report_accepts_relevant_project_objects():
    report = validate_dict(
        MatchReport,
        {
            "overall_score": 79,
            "matched_skills": "Python, SQL",
            "missing_skills": ["PyTorch"],
            "relevant_projects": [{"name": "Movie Recommendation System"}, {"project": "Sales Data Dashboard"}],
            "weak_sections": "Skill gaps",
            "explanation": "Scored from explicit evidence.",
        },
    )
    data = model_to_dict(report)
    assert data["matched_skills"] == ["Python", "SQL"]
    assert data["relevant_projects"] == ["Movie Recommendation System", "Sales Data Dashboard"]
    assert data["weak_sections"] == ["Skill gaps"]
