"""CareerPilot LangGraph workflow and fallback runner."""

from concurrent.futures import ThreadPoolExecutor

from src.agents.application_answer_agent import application_answer_node
from src.agents.final_report_agent import final_report_node
from src.agents.interview_coach_agent import interview_coach_node
from src.agents.jd_analyzer_agent import jd_analyzer_node
from src.agents.low_match_warning_agent import low_match_warning_node
from src.agents.match_scoring_agent import match_scoring_node
from src.agents.rag_retriever_agent import rag_retriever_node
from src.agents.reflection_agent import reflection_node
from src.agents.resume_optimizer_agent import resume_optimizer_node
from src.agents.resume_parser_agent import resume_parser_node


def route_after_match_scoring(state) -> str:
    score = (state.get("match_report") or {}).get("overall_score", 0)
    if score < 45:
        return "low_match_warning"
    return "resume_optimizer"


def route_after_reflection(state) -> str:
    has_exaggeration = state.get("has_exaggeration", False)
    iteration = state.get("reflection_iteration", 0)
    if has_exaggeration and iteration < 2:
        return "resume_optimizer"
    return "phase_two_parallel"


def phase_two_parallel_node(state) -> dict:
    return {
        "workflow_trace": [
            "PhaseTwoParallelNode: Running application answers and interview coaching in parallel."
        ]
    }


def _merge_state(state: dict, update: dict) -> dict:
    merged = dict(state)
    for key, value in update.items():
        if key in {"workflow_trace", "errors", "warnings"}:
            merged[key] = list(merged.get(key, [])) + list(value or [])
        else:
            merged[key] = value
    return merged


def _run_phase_two_parallel(state: dict) -> list[tuple[str, dict]]:
    phase_two_nodes = [
        ("application_answer", application_answer_node),
        ("interview_coach", interview_coach_node),
    ]
    base_state = dict(state)
    with ThreadPoolExecutor(max_workers=len(phase_two_nodes)) as executor:
        futures = [(name, executor.submit(node, dict(base_state))) for name, node in phase_two_nodes]
        return [(name, future.result()) for name, future in futures]


def stream_workflow(initial_state: dict):
    state = dict(initial_state)
    sequence = [
        ("resume_parser", resume_parser_node),
        ("jd_analyzer", jd_analyzer_node),
        ("rag_retriever", rag_retriever_node),
        ("match_scoring", match_scoring_node),
    ]
    for name, node in sequence:
        update = node(state)
        state = _merge_state(state, update)
        yield {name: state}

    if route_after_match_scoring(state) == "low_match_warning":
        update = low_match_warning_node(state)
        state = _merge_state(state, update)
        yield {"low_match_warning": state}
    else:
        while True:
            update = resume_optimizer_node(state)
            state = _merge_state(state, update)
            yield {"resume_optimizer": state}

            update = reflection_node(state)
            state = _merge_state(state, update)
            yield {"reflection": state}

            if route_after_reflection(state) == "phase_two_parallel":
                break

        update = phase_two_parallel_node(state)
        state = _merge_state(state, update)
        yield {"phase_two_parallel": state}

        for name, update in _run_phase_two_parallel(state):
            state = _merge_state(state, update)
            yield {name: state}

    update = final_report_node(state)
    state = _merge_state(state, update)
    yield {"final_report": state}


def run_workflow(initial_state: dict) -> dict:
    final_state = initial_state
    for event in stream_workflow(initial_state):
        final_state = list(event.values())[0]
    return final_state


def build_graph():
    try:
        from langgraph.graph import END, StateGraph
        from src.workflow.state import CareerPilotState
    except ImportError:
        return None

    workflow = StateGraph(CareerPilotState)
    workflow.add_node("resume_parser", resume_parser_node)
    workflow.add_node("jd_analyzer", jd_analyzer_node)
    workflow.add_node("rag_retriever", rag_retriever_node)
    workflow.add_node("match_scoring", match_scoring_node)
    workflow.add_node("low_match_warning", low_match_warning_node)
    workflow.add_node("resume_optimizer", resume_optimizer_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("phase_two_parallel", phase_two_parallel_node)
    workflow.add_node("application_answer", application_answer_node)
    workflow.add_node("interview_coach", interview_coach_node)
    workflow.add_node("final_report", final_report_node)

    workflow.set_entry_point("resume_parser")
    workflow.add_edge("resume_parser", "jd_analyzer")
    workflow.add_edge("jd_analyzer", "rag_retriever")
    workflow.add_edge("rag_retriever", "match_scoring")
    workflow.add_edge("resume_optimizer", "reflection")
    workflow.add_edge("phase_two_parallel", "application_answer")
    workflow.add_edge("phase_two_parallel", "interview_coach")
    workflow.add_edge(["application_answer", "interview_coach"], "final_report")
    workflow.add_edge("low_match_warning", "final_report")
    workflow.add_edge("final_report", END)
    workflow.add_conditional_edges(
        "match_scoring",
        route_after_match_scoring,
        {"low_match_warning": "low_match_warning", "resume_optimizer": "resume_optimizer"},
    )
    workflow.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {"resume_optimizer": "resume_optimizer", "phase_two_parallel": "phase_two_parallel"},
    )
    return workflow.compile()


graph = build_graph()
