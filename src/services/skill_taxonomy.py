"""Skill vocabulary shared by the deterministic parsers.

Both the resume parser and the JD analyzer need this list. It used to live in
resume_parser_agent.py with jd_analyzer_agent importing it from there, which
made one agent depend on another for what is really shared domain data.
"""

KNOWN_SKILLS = [
    "Python", "SQL", "scikit-learn", "pandas", "NumPy", "Git", "Flask", "Matplotlib",
    "PyTorch", "TensorFlow", "Docker", "Tableau", "Java", "C++", "NLP", "React",
    "FastAPI", "SQLite", "REST API", "Power BI", "Airflow", "Spark", "AWS", "GCP",
]


def find_known_skills(text: str) -> list[str]:
    """Return the known skills mentioned in text, in taxonomy order."""

    lowered = (text or "").lower()
    return [skill for skill in KNOWN_SKILLS if skill.lower() in lowered]
