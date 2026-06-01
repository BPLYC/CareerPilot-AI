from src.workflow.careerpilot_graph import route_after_match_scoring, route_after_reflection, run_workflow
from src.workflow.state import create_initial_state


def test_low_match_route():
    state = {"match_report": {"overall_score": 30}}
    assert route_after_match_scoring(state) == "low_match_warning"


def test_reflection_route_stops_at_limit():
    assert route_after_reflection({"has_exaggeration": True, "reflection_iteration": 1}) == "resume_optimizer"
    assert route_after_reflection({"has_exaggeration": True, "reflection_iteration": 2}) == "final_report"


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


def test_low_match_skips_phase_two_prep():
    resume = "Alex Chen\nSkills: Tableau\nProject: Sales Data Dashboard."
    jd = "Machine Learning Intern required skills include Python, PyTorch, TensorFlow, Docker, AWS."
    final_state = run_workflow(create_initial_state(resume, jd))
    assert final_state["match_report"]["overall_score"] < 45
    assert final_state["optimized_bullets"] == []
    assert final_state["application_answers"] == {}
    assert final_state["interview_questions"] == []
