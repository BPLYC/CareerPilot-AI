from src.agents.jd_analyzer_agent import fallback_analyze_jd
from src.agents.match_scoring_agent import fallback_score_match


def _score(education, jd):
    resume = {"skills": [], "projects": [], "work_experience": [], "education": education}
    return fallback_score_match(resume, jd)["score_breakdown"]["education"]


def test_fallback_extracts_english_required_education():
    result = fallback_analyze_jd(
        "Software Intern. A bachelor's degree in Computer Science is required. "
        "Graduating in 2027. Minimum GPA 3.2."
    )
    assert result["education_level"] == "bachelor"
    assert result["education_major"] == "Computer Science"
    assert result["graduation_requirement"] == "2027"
    assert result["gpa_requirement"] == 3.2
    assert result["education_is_required"] is True


def test_fallback_extracts_chinese_preferred_education():
    result = fallback_analyze_jd("数据分析实习生。统计学相关专业硕士优先，2026至2027年毕业。")
    assert result["education_level"] == "master"
    assert result["education_major"] == "统计学"
    assert result["graduation_requirement"] == "2026至2027"
    assert result["education_is_required"] is False


def test_no_requirement_gets_full_education_points():
    assert _score([], {}) == 10


def test_matching_structured_requirement_gets_full_points():
    jd = {
        "education_requirements": "Bachelor's in Computer Science, graduating 2027",
        "education_level": "bachelor",
        "education_major": "Computer Science",
        "graduation_requirement": "2027",
        "education_is_required": True,
    }
    education = [
        {
            "school": "Example University",
            "degree": "Bachelor of Science",
            "major": "Computer Science",
            "graduation_date": "2027",
        }
    ]
    assert _score(education, jd) == 10


def test_unknown_fields_are_information_insufficient_not_a_match():
    jd = {
        "education_requirements": "Bachelor's degree required",
        "education_level": "bachelor",
        "education_is_required": True,
    }
    education = [{"school": "Prestigious University", "degree": "unknown", "major": "unknown"}]
    assert _score(education, jd) == 7


def test_missing_required_education_scores_zero_and_school_reputation_is_ignored():
    jd = {
        "education_requirements": "Master's degree required",
        "education_level": "master",
        "education_is_required": True,
    }
    assert _score([], jd) == 0
    assert _score([{"school": "Famous University", "degree": "Bachelor", "major": "CS"}], jd) == 2


def test_missing_preferred_education_receives_partial_points():
    jd = {
        "education_requirements": "Master's degree preferred",
        "education_level": "master",
        "education_is_required": False,
    }
    assert _score([], jd) == 5
