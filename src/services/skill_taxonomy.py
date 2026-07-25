"""Skill vocabulary shared by the deterministic parsers.

Both the resume parser and the JD analyzer need this list. It used to live in
resume_parser_agent.py with jd_analyzer_agent importing it from there, which
made one agent depend on another for what is really shared domain data.
"""

import re

KNOWN_SKILLS = [
    "Python", "SQL", "scikit-learn", "pandas", "NumPy", "Git", "Flask", "Matplotlib",
    "PyTorch", "TensorFlow", "Docker", "Tableau", "Java", "C++", "NLP", "React",
    "FastAPI", "SQLite", "REST API", "Power BI", "Airflow", "Spark", "AWS", "GCP",
    "RAG", "LangChain", "LangGraph", "Agent", "Hadoop", "Hive", "PostgreSQL",
    "Machine Learning", "大模型", "深度学习",
    "自然语言处理", "多模态", "搜索算法",
]

SKILL_ALIASES = {
    "scikit-learn": ["scikit-learn", "sklearn"],
    "PyTorch": ["pytorch", "torch"],
    "PostgreSQL": ["postgresql", "postgres"],
    "REST API": ["rest api", "restful api", "restful apis"],
    "Machine Learning": ["machine learning", "ml", "机器学习"],
    "Agent": ["agent", "智能体"],
    "NLP": ["nlp", "自然语言处理"],
    "RAG": ["rag", "检索增强"],
    "大模型": ["大模型", "llm"],
    "深度学习": ["深度学习", "deep learning"],
    "多模态": ["多模态", "multimodal"],
    "搜索算法": ["搜索算法"],
}

SKILL_CATEGORIES = {
    "python": "programming",
    "java": "programming",
    "c++": "programming",
    "sql": "data",
    "postgresql": "database",
    "sqlite": "database",
    "tableau": "visualization",
    "power bi": "visualization",
    "pytorch": "machine_learning",
    "tensorflow": "machine_learning",
    "scikit-learn": "machine_learning",
    "machine learning": "machine_learning",
    "aws": "cloud",
    "gcp": "cloud",
    "flask": "backend",
    "fastapi": "backend",
    "rest api": "backend",
}

# Related tools are useful transfer evidence, but are deliberately not treated
# as exact required-skill matches. The UI can explain them without inflating the
# deterministic required-skill score.
RELATED_SKILLS = {
    "tableau": {"power bi"},
    "power bi": {"tableau"},
    "pytorch": {"tensorflow"},
    "tensorflow": {"pytorch"},
    "aws": {"gcp"},
    "gcp": {"aws"},
    "flask": {"fastapi"},
    "fastapi": {"flask"},
    "postgresql": {"sqlite"},
    "sqlite": {"postgresql"},
}


def canonical_skill(value: str) -> str:
    """Return a stable comparison key while preserving display labels elsewhere."""

    lowered = (value or "").strip().lower()
    for skill, aliases in SKILL_ALIASES.items():
        if lowered == skill.lower() or any(lowered == alias.lower() for alias in aliases):
            return skill.lower()
    return lowered


def skill_relationship(candidate_skill: str, target_skill: str) -> str:
    """Classify a skill pair as exact, related, same-category, or unrelated."""

    candidate = canonical_skill(candidate_skill)
    target = canonical_skill(target_skill)
    if candidate == target:
        return "exact"
    if candidate in RELATED_SKILLS.get(target, set()):
        return "related"
    if SKILL_CATEGORIES.get(candidate) and SKILL_CATEGORIES.get(candidate) == SKILL_CATEGORIES.get(target):
        return "same_category"
    return "unrelated"


def transferable_skills(resume_skills: list[str], missing_skills: list[str]) -> dict[str, list[str]]:
    """Return related resume evidence for missing JD skills, preserving labels."""

    result = {}
    for missing in missing_skills:
        related = [
            skill
            for skill in resume_skills
            if skill_relationship(skill, missing) in {"related", "same_category"}
        ]
        if related:
            result[missing] = related
    return result


def find_known_skills(text: str) -> list[str]:
    """Return the known skills mentioned in text, in taxonomy order."""

    lowered = (text or "").lower()

    def mentions(alias: str) -> bool:
        alias = alias.lower()
        if re.fullmatch(r"[a-z0-9+#.]+", alias):
            return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered) is not None
        return alias in lowered

    return [
        skill
        for skill in KNOWN_SKILLS
        if any(mentions(alias) for alias in SKILL_ALIASES.get(skill, [skill]))
    ]
