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
            "PhaseTwoParallelNode：正在并行生成申请回答和面试准备内容。"
        ]
    }


def _merge_state(state: dict, update: dict) -> dict:
    merged = dict(state)
    for key, value in update.items():
        if key in {"workflow_trace", "errors", "warnings", "fallback_nodes"}:
            merged[key] = list(merged.get(key, [])) + list(value or [])
        else:
            merged[key] = value
    return merged


def _run_in_parallel(state: dict, nodes: list[tuple[str, object]]) -> list[tuple[str, dict]]:
    """Run independent nodes concurrently against a snapshot of the state.

    Each node gets its own copy so none can observe another's partial writes.
    Results come back in the declared order rather than completion order, which
    keeps the trace stable between runs.
    """

    base_state = dict(state)
    with ThreadPoolExecutor(max_workers=len(nodes)) as executor:
        futures = [(name, executor.submit(node, dict(base_state))) for name, node in nodes]
        return [(name, future.result()) for name, future in futures]


# resume_parser reads raw_resume_text and jd_analyzer reads raw_jd_text. Neither
# looks at the other's output, so running them in sequence spent two round trips
# where one would do.
INTAKE_NODES = [
    ("resume_parser", resume_parser_node),
    ("jd_analyzer", jd_analyzer_node),
]

PHASE_TWO_NODES = [
    ("application_answer", application_answer_node),
    ("interview_coach", interview_coach_node),
]


def stream_workflow(initial_state: dict):
    """Stream {node_name: state_so_far} for each node the workflow runs.

    Uses the compiled LangGraph when langgraph is installed, and the sequential
    runner below otherwise. Both are kept because the deterministic fallback has
    to work without the dependency; tests/test_workflow_parity.py pins them to
    the same results.
    """

    if graph is None:
        yield from _stream_sequential(initial_state)
        return
    yield from _stream_graph(initial_state)


def _stream_graph(initial_state: dict):
    """Stream the compiled graph, pairing node names with accumulated state.

    "updates" carries the node name but only that node's partial return value;
    "values" carries the full state after LangGraph applies its own reducers.
    Streaming both and pairing them means the accumulated state comes from
    LangGraph rather than from a second merge implementation here.

    The Phase 2 pair runs concurrently, so two "updates" arrive before the next
    "values". Both are reported against the state that follows the join, which
    is the first point where either node's output is actually observable.
    """

    pending: list[str] = []
    for mode, payload in graph.stream(dict(initial_state), stream_mode=["updates", "values"]):
        if mode == "updates":
            pending.extend(payload)
        elif pending:
            for node_name in pending:
                yield {node_name: payload}
            pending = []


def _stream_sequential(initial_state: dict):
    state = dict(initial_state)

    for name, update in _run_in_parallel(state, INTAKE_NODES):
        state = _merge_state(state, update)
        yield {name: state}

    for name, node in [("rag_retriever", rag_retriever_node), ("match_scoring", match_scoring_node)]:
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

        for name, update in _run_in_parallel(state, PHASE_TWO_NODES):
            state = _merge_state(state, update)
            yield {name: state}

    update = final_report_node(state)
    state = _merge_state(state, update)
    yield {"final_report": state}


def _final_state(events) -> dict:
    final_state: dict = {}
    for event in events:
        final_state = next(iter(event.values()))
    return final_state


def run_workflow(initial_state: dict) -> dict:
    return _final_state(stream_workflow(initial_state)) or initial_state


def run_sequential_workflow(initial_state: dict) -> dict:
    """Run the workflow without LangGraph.

    This is the path taken when langgraph is not installed. It needs its own
    entry point so parity tests can compare the two engines: once stream_workflow
    prefers the compiled graph, a test calling run_workflow would be comparing
    the graph against itself and would pass without checking anything.
    """

    return _final_state(_stream_sequential(initial_state)) or initial_state


def build_graph():
    try:
        from langgraph.graph import END, START, StateGraph

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

    # Fan out to both intake nodes and join at rag_retriever, which is the first
    # node that needs jd_analyzer's output.
    workflow.add_edge(START, "resume_parser")
    workflow.add_edge(START, "jd_analyzer")
    workflow.add_edge(["resume_parser", "jd_analyzer"], "rag_retriever")
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
