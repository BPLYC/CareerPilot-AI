from src.agents.interview_coach_agent import fallback_interview_questions
from src.services.cache import get_cache_key
from src.workflow.careerpilot_graph import (
    graph,
    route_after_match_scoring,
    route_after_reflection,
    run_workflow,
    stream_workflow,
)
from src.workflow.state import create_initial_state


def test_low_match_route():
    state = {"match_report": {"overall_score": 30}}
    assert route_after_match_scoring(state) == "low_match_warning"


def test_reflection_route_stops_at_limit():
    assert route_after_reflection({"has_exaggeration": True, "reflection_iteration": 1}) == "resume_optimizer"
    assert route_after_reflection({"has_exaggeration": True, "reflection_iteration": 2}) == "phase_two_parallel"


def test_workflow_runs_with_sample_text():
    resume = (
        "Alex Chen\nSkills: Python, SQL, Flask, Git, Docker, REST API\n"
        "Intern experience building backend tools.\n"
        "Project: Personal Task Manager Web App using Flask and SQLite."
    )
    jd = "Software Engineering Intern required skills include Python, Git, databases, REST API, Docker."
    final_state = run_workflow(create_initial_state(resume, jd))
    assert final_state["match_report"] is not None
    assert final_state["application_answers"]["why_this_role"]
    assert final_state["interview_questions"]
    assert final_state["workflow_trace"]


def test_stream_workflow_runs_phase_two_parallel_before_final_report():
    resume = (
        "Alex Chen\nSkills: Python, SQL, Flask, Git, Docker, REST API\n"
        "Intern experience building backend tools.\n"
        "Project: Personal Task Manager Web App using Flask and SQLite."
    )
    jd = "Software Engineering Intern required skills include Python, Git, databases, REST API, Docker."
    events = list(stream_workflow(create_initial_state(resume, jd)))
    event_names = [next(iter(event)) for event in events]

    assert "phase_two_parallel" in event_names
    assert "application_answer" in event_names
    assert "interview_coach" in event_names
    assert event_names.index("phase_two_parallel") < event_names.index("application_answer")
    assert event_names.index("phase_two_parallel") < event_names.index("interview_coach")
    assert event_names[-1] == "final_report"
    assert event_names.count("final_report") == 1


def test_langgraph_path_joins_parallel_phase_two_nodes_once():
    if graph is None:
        return

    resume = (
        "Alex Chen\nSkills: Python, SQL, Flask, Git, Docker, REST API\n"
        "Intern experience building backend tools.\n"
        "Project: Personal Task Manager Web App using Flask and SQLite."
    )
    jd = "Software Engineering Intern required skills include Python, Git, databases, REST API, Docker."
    final_state = graph.invoke(create_initial_state(resume, jd))
    trace = final_state["workflow_trace"]

    assert final_state["application_answers"]["why_this_role"]
    assert final_state["interview_questions"]
    assert any("PhaseTwoParallelNode" in item for item in trace)
    assert sum(1 for item in trace if "FinalReportNode" in item) == 1


def test_workflow_answers_custom_application_questions_safely():
    resume = (
        "Alex Chen\nSkills: Python, SQL, Flask, Git, Docker, REST API\n"
        "Project: Personal Task Manager Web App using Flask and SQLite."
    )
    jd = "Software Engineering Intern required skills include Python, Git, databases, REST API, Docker."
    state = create_initial_state(
        resume,
        jd,
        [
            "Why are you interested in this internship?",
            "Will you require visa sponsorship?",
        ],
    )
    final_state = run_workflow(state)
    custom_answers = final_state["application_answers"]["custom_answers"]
    assert len(custom_answers) == 2
    assert custom_answers[0]["question"] == "Why are you interested in this internship?"
    assert "简历中已经验证" in custom_answers[0]["answer"]
    assert custom_answers[1]["question"] == "Will you require visa sponsorship?"
    assert "必须由申请人本人填写" in custom_answers[1]["answer"]


def test_cache_key_includes_custom_application_questions():
    base_key = get_cache_key("resume", "jd", [])
    question_key = get_cache_key("resume", "jd", ["Why this role?"])
    assert base_key != question_key


def test_interview_fallback_includes_role_specific_and_project_followups():
    resume_profile = {
        "projects": [
            {
                "name": "Recommendation System",
                "description": "Built a recommender with Python.",
                "technologies": ["Python", "scikit-learn"],
            }
        ]
    }
    jd_analysis = {
        "job_title": "AI Intern",
        "required_skills": ["Python", "PyTorch"],
        "tools_and_technologies": ["PyTorch"],
        "keywords": ["machine learning"],
    }
    questions = fallback_interview_questions(resume_profile, jd_analysis, {})
    focus_areas = {question["focus_area"] for question in questions}
    assert "项目追问" in focus_areas
    assert "机器学习评估" in focus_areas


def test_low_match_skips_phase_two_prep():
    resume = "Alex Chen\nSkills: Tableau\nProject: Sales Data Dashboard."
    jd = "Machine Learning Intern required skills include Python, PyTorch, TensorFlow, Docker, AWS."
    final_state = run_workflow(create_initial_state(resume, jd))
    assert final_state["match_report"]["overall_score"] < 45
    assert final_state["optimized_bullets"] == []
    assert final_state["application_answers"] == {}
    assert final_state["interview_questions"] == []
