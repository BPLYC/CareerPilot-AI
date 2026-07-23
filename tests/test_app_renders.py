"""Run the actual Streamlit script headlessly and assert it does not raise.

An HTTP 200 from the server only proves the shell HTML was served; Streamlit
does not execute app.py until a session connects. After splitting app.py into
eight modules, an import error or a bad attribute would surface only at render
time, so the script has to be executed to be verified.
"""

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

TAB_LABELS = [
    "Input",
    "Match Report",
    "Resume Tips",
    "Application & Interview",
    "Compare Jobs",
    "Workflow Trace",
    "Run History",
]


def _run():
    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()
    return app


def test_app_renders_without_exceptions():
    app = _run()

    assert not app.exception, [str(e) for e in app.exception]


def test_all_tabs_are_present():
    app = _run()
    labels = [tab.label for tab in app.tabs]

    for expected in TAB_LABELS:
        assert expected in labels


def test_compare_tab_renders_its_controls():
    app = _run()
    button_labels = [button.label for button in app.button]
    textarea_labels = [area.label for area in app.text_area]

    assert "Compare roles" in button_labels
    assert "Load all sample JDs" in button_labels
    assert "Job descriptions" in textarea_labels


def test_sidebar_offers_the_provider_controls():
    app = _run()
    sidebar_labels = [element.label for element in app.sidebar.selectbox] + [
        element.label for element in app.sidebar.text_input
    ]

    assert "Model" in sidebar_labels
    assert "Thinking Mode" in sidebar_labels
    assert "Reasoning Effort" in sidebar_labels


def test_untouched_tabs_prompt_for_an_analysis_rather_than_erroring():
    app = _run()
    messages = [element.value for element in app.info]

    assert any("Run the analysis first" in message for message in messages)


def test_download_button_appears_once_a_result_exists():
    """Seed a finished analysis and confirm the export control renders."""

    from eval.run_eval import use_deterministic_agents

    use_deterministic_agents()
    from src.workflow.careerpilot_graph import run_workflow
    from src.workflow.state import create_initial_state

    resume = "Alex Chen\nSkills: Python, SQL, Flask\nProject: Task Manager using Flask."
    jd = "Software Engineering Intern needs Python, Flask, SQL."

    app = AppTest.from_file("app.py", default_timeout=60)
    app.session_state["last_result"] = run_workflow(create_initial_state(resume, jd))
    app.run()

    # AppTest exposes no download_button accessor in this Streamlit version, so
    # reach for the element by type. Rendering without an exception already
    # shows st.download_button accepted the generated report.
    assert not app.exception, [str(e) for e in app.exception]
    labels = [element.label for element in app.get("download_button")]
    assert "Download full report (Markdown)" in labels

    metrics = {element.label: element.value for element in app.metric}
    assert "Match Score" in metrics


def test_sensitive_reminder_is_not_shown_before_any_analysis():
    """It used to render unconditionally, warning about content not on screen."""

    from src.ui.tabs.application_tab import SENSITIVE_REMINDER

    app = _run()
    warnings = [element.value for element in app.warning]

    assert SENSITIVE_REMINDER not in warnings
