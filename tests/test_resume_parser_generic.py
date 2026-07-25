from src.agents.resume_parser_agent import fallback_parse_resume


def test_fallback_parser_extracts_unseen_projects_and_multiple_jobs():
    resume = """Jordan Lee
jordan@example.com

Education
River State University
Bachelor of Science in Information Systems, May 2026

Skills
Python, SQL, FastAPI, PostgreSQL

Projects
Campus Shuttle Tracker
Built a FastAPI service backed by PostgreSQL for live shuttle updates.

Budget Insight Tool
Analyzed transaction exports with Python and SQL.

Work Experience
Northwind Labs | Software Engineering Intern | Jun 2025 - Aug 2025
Implemented API validation and wrote integration tests.

City Library | Technology Assistant | Sep 2024 - May 2025
Supported staff systems and documented recurring issues.
"""

    profile = fallback_parse_resume(resume)

    assert [project["name"] for project in profile["projects"]] == [
        "Campus Shuttle Tracker",
        "Budget Insight Tool",
    ]
    assert profile["projects"][0]["technologies"] == ["FastAPI", "PostgreSQL"]
    assert profile["projects"][1]["technologies"] == ["Python", "SQL"]
    assert [job["company"] for job in profile["work_experience"]] == [
        "Northwind Labs",
        "City Library",
    ]
    assert [job["role"] for job in profile["work_experience"]] == [
        "Software Engineering Intern",
        "Technology Assistant",
    ]
    assert profile["education"][0]["school"] == "River State University"
    assert "Bachelor of Science" in profile["education"][0]["degree"]
    assert profile["education"][0]["major"] == "Information Systems"


def test_fallback_parser_supports_common_chinese_section_headings():
    resume = """林晓

教育背景
华南大学
计算机科学学士，预计 2026 年毕业

技能
Python、SQL、React

项目经历
校园活动平台
使用 React 开发活动页面，并通过 Python 和 SQL 提供数据接口。

工作经历
星河科技 | 软件开发实习生 | 2025.06 - 2025.08
参与内部工具开发和测试。
"""

    profile = fallback_parse_resume(resume)

    assert profile["projects"][0]["name"] == "校园活动平台"
    assert profile["projects"][0]["technologies"] == ["Python", "SQL", "React"]
    assert profile["work_experience"][0]["company"] == "星河科技"
    assert profile["work_experience"][0]["role"] == "软件开发实习生"
    assert profile["education"][0]["school"] == "华南大学"
    assert profile["education"][0]["major"] == "计算机科学"


def test_section_parser_does_not_turn_skills_or_education_into_projects():
    resume = """Sam Rivera
Skills
Python
Education
Example College
Bachelor of Arts, 2024
"""

    profile = fallback_parse_resume(resume)

    assert profile["projects"] == []
    assert profile["work_experience"] == []


def test_fallback_parser_keeps_single_line_project_compatibility():
    profile = fallback_parse_resume(
        "Taylor\nSkills: Python, Flask\nProject: Task Tracker using Python and Flask."
    )

    assert profile["projects"][0]["name"] == "Task Tracker"
    assert profile["projects"][0]["technologies"] == ["Python", "Flask"]
