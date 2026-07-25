"""Skill vocabulary shared by the deterministic parsers.

Both the resume parser and the JD analyzer need this list. It used to live in
resume_parser_agent.py with jd_analyzer_agent importing it from there, which
made one agent depend on another for what is really shared domain data.
"""

KNOWN_SKILLS = [
    "Python", "SQL", "scikit-learn", "pandas", "NumPy", "Git", "Flask", "Matplotlib",
    "PyTorch", "TensorFlow", "Docker", "Tableau", "Java", "C++", "NLP", "React",
    "FastAPI", "SQLite", "REST API", "Power BI", "Airflow", "Spark", "AWS", "GCP",
    "RAG", "LangChain", "LangGraph", "Agent", "Hadoop", "Hive", "大模型", "深度学习",
    "自然语言处理", "多模态", "搜索算法",
]

SKILL_ALIASES = {
    "Agent": ["agent", "智能体"],
    "NLP": ["nlp", "自然语言处理"],
    "RAG": ["rag", "检索增强"],
    "大模型": ["大模型", "llm"],
    "深度学习": ["深度学习", "deep learning"],
    "多模态": ["多模态", "multimodal"],
    "搜索算法": ["搜索算法"],
}


def find_known_skills(text: str) -> list[str]:
    """Return the known skills mentioned in text, in taxonomy order."""

    lowered = (text or "").lower()
    return [
        skill
        for skill in KNOWN_SKILLS
        if any(alias.lower() in lowered for alias in SKILL_ALIASES.get(skill, [skill]))
    ]
