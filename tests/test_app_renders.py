"""Run the actual Streamlit script headlessly and assert it does not raise.

An HTTP 200 from the server only proves the shell HTML was served; Streamlit
does not execute app.py until a session connects. After splitting app.py into
eight modules, an import error or a bad attribute would surface only at render
time, so the script has to be executed to be verified.
"""

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

TAB_LABELS = [
    "信息输入",
    "匹配报告",
    "简历优化",
    "申请与面试",
    "职位对比",
    "工作流记录",
    "运行历史",
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

    assert "开始职位对比" in button_labels
    assert "加载全部示例职位" in button_labels
    assert "职位描述" in textarea_labels


def test_sidebar_offers_the_provider_controls():
    app = _run()
    sidebar_labels = [element.label for element in app.sidebar.selectbox] + [
        element.label for element in app.sidebar.text_input
    ]

    assert "模型" in sidebar_labels
    assert "深度思考模式" in sidebar_labels
    assert "推理强度" in sidebar_labels


def test_untouched_tabs_prompt_for_an_analysis_rather_than_erroring():
    app = _run()
    messages = [element.value for element in app.info]

    assert any("请先运行分析" in message for message in messages)


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
    assert "下载完整报告（Markdown）" in labels

    metrics = {element.label: element.value for element in app.metric}
    # No API key in tests, so the model IS the reference scorer and the two
    # agree, collapsing to the single-score layout.
    assert "离线规则评分" in metrics


def test_diverging_scores_render_side_by_side():
    """When the AI score and the baseline differ, both are shown, not one."""

    app = AppTest.from_file("app.py", default_timeout=60)
    app.session_state["last_result"] = {
        "match_report": {
            "overall_score": 45,
            "matched_skills": ["Python"],
            "missing_skills": ["Docker"],
            "explanation": "x",
        },
        "reference_score": 72,
        "warnings": [],
    }
    app.run()

    assert not app.exception, [str(e) for e in app.exception]
    labels = {element.label for element in app.metric}
    assert {"AI 评分", "规则基准评分"} <= labels
    assert "匹配评分" not in labels


def test_match_report_renders_score_breakdown():
    app = AppTest.from_file("app.py", default_timeout=60)
    app.session_state["last_result"] = {
        "match_report": {
            "overall_score": 55,
            "matched_skills": ["Python"],
            "missing_skills": ["Docker"],
            "explanation": "x",
            "score_breakdown": {
                "required_skills": 20,
                "preferred_skills": 5,
                "project_evidence": 10,
                "experience_evidence": 10,
                "education": 10,
            },
            "score_reliable": True,
        },
        "reference_score": 55,
        "warnings": [],
    }
    app.run()

    assert not app.exception, [str(e) for e in app.exception]
    assert any("评分明细" in element.value for element in app.markdown)
    assert len(app.dataframe) >= 1


def test_load_all_sample_jds_actually_fills_the_boxes():
    """A keyed widget ignores `value=` after its first render.

    The Compare Jobs tab originally passed `value=` alongside `key=`, so both
    boxes stayed empty however often the button was pressed and the tab could
    only ever report "Please provide a resume." The unit tests covered
    compare_jobs() directly and never touched this path.
    """

    from src.ui.tabs.compare_tab import JD_KEY, RESUME_KEY

    app = AppTest.from_file("app.py", default_timeout=60)
    app.run()

    button = next(b for b in app.button if b.label == "加载全部示例职位")
    button.click().run()

    assert not app.exception, [str(e) for e in app.exception]
    assert "Alex Chen" in app.session_state[RESUME_KEY]
    jd_text = app.session_state[JD_KEY]
    assert "AI Intern" in jd_text
    assert jd_text.count("===") >= 2, "every sample JD should be present"


def test_comparison_runs_end_to_end_in_the_ui():
    from eval.run_eval import use_deterministic_agents

    use_deterministic_agents()

    app = AppTest.from_file("app.py", default_timeout=120)
    app.run()
    next(b for b in app.button if b.label == "加载全部示例职位").click().run()
    next(b for b in app.button if b.label == "开始职位对比").click().run()

    assert not app.exception, [str(e) for e in app.exception]
    result = app.session_state["comparison_result"]
    assert result.best is not None
    assert len(result.jobs) == 3
    assert all(not job.failed for job in result.jobs)


def test_sensitive_reminder_is_not_shown_before_any_analysis():
    """It used to render unconditionally, warning about content not on screen."""

    from src.ui.tabs.application_tab import SENSITIVE_REMINDER

    app = _run()
    warnings = [element.value for element in app.warning]

    assert SENSITIVE_REMINDER not in warnings


def test_match_report_labels_fallback_score_as_offline():
    app = AppTest.from_file("app.py", default_timeout=60)
    app.session_state["last_result"] = {
        "match_report": {
            "overall_score": 8,
            "matched_skills": [],
            "missing_skills": ["Java"],
            "explanation": "离线说明",
        },
        "reference_score": 8,
        "fallback_nodes": ["ResumeParserNode", "JDAnalyzerNode", "MatchScoringNode"],
        "warnings": [],
    }
    app.run()

    assert not app.exception, [str(e) for e in app.exception]
    labels = {element.label for element in app.metric}
    assert "离线规则评分" in labels
    warnings = [element.value for element in app.warning]
    assert any("离线规则" in warning for warning in warnings)
