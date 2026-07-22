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


def test_all_six_tabs_are_present():
    app = _run()
    labels = [tab.label for tab in app.tabs]

    for expected in TAB_LABELS:
        assert expected in labels


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


def test_sensitive_reminder_is_not_shown_before_any_analysis():
    """It used to render unconditionally, warning about content not on screen."""

    from src.ui.tabs.application_tab import SENSITIVE_REMINDER

    app = _run()
    warnings = [element.value for element in app.warning]

    assert SENSITIVE_REMINDER not in warnings
