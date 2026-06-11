from src.services.scoring import keyword_coverage, matched_and_missing_skills, skill_match_rate


def test_keyword_coverage():
    assert keyword_coverage("Python and SQL project", ["Python", "SQL", "Docker"]) == 2 / 3
    assert keyword_coverage("Built APIs with Python.", ["Python"]) == 1.0


def test_skill_matching():
    matched, missing = matched_and_missing_skills(["Python", "SQL"], ["Python", "Docker"])
    assert matched == ["Python"]
    assert missing == ["Docker"]
    assert skill_match_rate(["Python", "SQL"], ["Python", "Docker"]) == 0.5
