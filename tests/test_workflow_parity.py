"""The compiled graph and the hand-written runner must agree.

careerpilot_graph.py carries two implementations of the same workflow: the
LangGraph StateGraph built by build_graph(), and the sequential runner in
stream_workflow(). Routing rules, the reflection loop bound, and the Phase 2
fan-out are expressed twice, so the two can drift apart without any test
noticing. These tests pin them together.

Written before switching the runtime path onto the compiled graph, so that any
pre-existing divergence shows up as a failure here rather than as a behaviour
change attributed to the switch.
"""

import pytest

from src.workflow.careerpilot_graph import graph, run_sequential_workflow, stream_workflow
from src.workflow.state import create_initial_state

pytestmark = pytest.mark.skipif(graph is None, reason="langgraph is not installed")

STRONG_RESUME = (
    "Alex Chen\nSkills: Python, SQL, Flask, Git, Docker, REST API\n"
    "Intern experience building backend tools.\n"
    "Project: Personal Task Manager Web App using Flask and SQLite."
)
STRONG_JD = "Software Engineering Intern required skills include Python, Git, databases, REST API, Docker."

WEAK_RESUME = "Alex Chen\nSkills: Tableau\nProject: Sales Data Dashboard."
WEAK_JD = "Machine Learning Intern required skills include Python, PyTorch, TensorFlow, Docker, AWS."

NODE_NAMES = [
    "ResumeParserNode",
    "JDAnalyzerNode",
    "RAGRetrieverNode",
    "MatchScoringNode",
    "LowMatchWarningNode",
    "ResumeOptimizerNode",
    "ReflectionNode",
    "PhaseTwoParallelNode",
    "ApplicationAnswerNode",
    "InterviewCoachNode",
    "FinalReportNode",
]


def careerpilot_stream(state: dict) -> list[dict]:
    return list(stream_workflow(state))


def _sequential_events(state: dict) -> list[dict]:
    from src.workflow.careerpilot_graph import _stream_sequential

    return list(_stream_sequential(state))


def _nodes_visited(state: dict) -> set[str]:
    trace = " || ".join(state.get("workflow_trace", []))
    return {name for name in NODE_NAMES if name in trace}


def _comparable(state: dict) -> dict:
    """The parts of the final state that carry meaning for the user.

    Deliberately excludes trace ordering and exact wording: the two engines
    interleave the parallel Phase 2 nodes differently, and that is allowed.
    """

    report = state.get("match_report") or {}
    answers = state.get("application_answers") or {}
    return {
        "score": report.get("overall_score"),
        "matched_skills": sorted(report.get("matched_skills", [])),
        "missing_skills": sorted(report.get("missing_skills", [])),
        "relevant_projects": sorted(report.get("relevant_projects", [])),
        "bullet_count": len(state.get("optimized_bullets", [])),
        "bullet_texts": [b.get("optimized_bullet") for b in state.get("optimized_bullets", [])],
        "interview_count": len(state.get("interview_questions", [])),
        "application_keys": sorted(answers),
        "custom_answers": answers.get("custom_answers", []),
        "warnings": sorted(state.get("warnings", [])),
        "error_count": len(state.get("errors", [])),
        "has_exaggeration": state.get("has_exaggeration"),
        "reflection_iteration": state.get("reflection_iteration"),
        "nodes_visited": sorted(_nodes_visited(state)),
    }


@pytest.mark.parametrize(
    ("resume", "jd", "questions", "label"),
    [
        (STRONG_RESUME, STRONG_JD, [], "normal match"),
        (WEAK_RESUME, WEAK_JD, [], "low match"),
        (
            STRONG_RESUME,
            STRONG_JD,
            ["Why are you interested in this internship?", "Will you require visa sponsorship?"],
            "custom application questions",
        ),
    ],
)
def test_graph_and_sequential_runner_agree(resume, jd, questions, label):
    from_graph = graph.invoke(create_initial_state(resume, jd, questions))
    from_runner = run_sequential_workflow(create_initial_state(resume, jd, questions))

    assert _comparable(from_graph) == _comparable(from_runner), f"engines disagree on the {label} case"


def test_final_report_runs_exactly_once_on_both_engines():
    for state in (
        graph.invoke(create_initial_state(STRONG_RESUME, STRONG_JD)),
        run_sequential_workflow(create_initial_state(STRONG_RESUME, STRONG_JD)),
    ):
        trace = state["workflow_trace"]
        assert sum(1 for item in trace if "FinalReportNode" in item) == 1


def test_stream_workflow_uses_the_compiled_graph(monkeypatch):
    """The compiled graph must be what actually runs, not just what gets built.

    Before this slice, build_graph() compiled a StateGraph that only a test ever
    invoked: app.py and the comparison evaluation both called the sequential
    runner, so the graph was decorative.
    """

    from src.workflow import careerpilot_graph

    def fail_if_called(_state):
        raise AssertionError("stream_workflow fell back to the sequential runner")
        yield  # pragma: no cover - marks this a generator

    monkeypatch.setattr(careerpilot_graph, "_stream_sequential", fail_if_called)

    events = list(careerpilot_graph.stream_workflow(create_initial_state(STRONG_RESUME, STRONG_JD)))
    node_names = [next(iter(event)) for event in events]

    # The two intake nodes run concurrently, so their order relative to each
    # other is not defined. Only their position before rag_retriever is.
    assert set(node_names[:2]) == {"resume_parser", "jd_analyzer"}
    assert node_names[-1] == "final_report"
    assert node_names.count("final_report") == 1
    assert {"phase_two_parallel", "application_answer", "interview_coach"} <= set(node_names)


def test_stream_workflow_falls_back_when_langgraph_is_missing(monkeypatch):
    from src.workflow import careerpilot_graph

    monkeypatch.setattr(careerpilot_graph, "graph", None)

    events = list(careerpilot_graph.stream_workflow(create_initial_state(STRONG_RESUME, STRONG_JD)))
    node_names = [next(iter(event)) for event in events]

    assert set(node_names[:2]) == {"resume_parser", "jd_analyzer"}
    assert node_names[-1] == "final_report"


def test_intake_nodes_run_before_retrieval_on_both_engines():
    """resume_parser and jd_analyzer are independent, but rag_retriever needs both."""

    for events in (
        careerpilot_stream(create_initial_state(STRONG_RESUME, STRONG_JD)),
        _sequential_events(create_initial_state(STRONG_RESUME, STRONG_JD)),
    ):
        node_names = [next(iter(event)) for event in events]
        assert set(node_names[:2]) == {"resume_parser", "jd_analyzer"}
        assert node_names[2] == "rag_retriever"


def test_each_streamed_event_carries_the_accumulated_state():
    """app.py reads the last trace line off each event, so state must accumulate."""

    events = list(stream_workflow(create_initial_state(STRONG_RESUME, STRONG_JD)))
    trace_lengths = [len(next(iter(event.values()))["workflow_trace"]) for event in events]

    assert trace_lengths == sorted(trace_lengths), "state went backwards between events"
    assert trace_lengths[-1] >= len(events)


def test_low_match_skips_phase_two_on_both_engines():
    for state in (
        graph.invoke(create_initial_state(WEAK_RESUME, WEAK_JD)),
        run_sequential_workflow(create_initial_state(WEAK_RESUME, WEAK_JD)),
    ):
        visited = _nodes_visited(state)
        assert "LowMatchWarningNode" in visited
        assert "ApplicationAnswerNode" not in visited
        assert "InterviewCoachNode" not in visited
