"""Sidebar: provider status, model settings, and the sample data loader."""

from dataclasses import dataclass

import streamlit as st

from src.services.provider_config import get_provider_config
from src.ui.sample_data import SAMPLE_JDS, load_sample

THINKING_OPTIONS = ["disabled", "enabled"]
EFFORT_OPTIONS = ["low", "medium", "high"]
THINKING_LABELS = {"disabled": "关闭", "enabled": "开启"}
EFFORT_LABELS = {"low": "低", "medium": "中", "high": "高"}


@dataclass
class ProviderSettings:
    """What the user picked in the sidebar, carried as a value.

    Returning these instead of writing them straight to os.environ is what keeps
    sidebar rendering free of side effects; run_analysis applies them for the
    duration of one run.
    """

    model: str
    thinking: str
    reasoning_effort: str

    def as_overrides(self) -> dict:
        return {
            "model": self.model,
            "thinking": self.thinking,
            "reasoning_effort": self.reasoning_effort,
        }


def _index_of(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def render_sidebar() -> ProviderSettings:
    with st.sidebar:
        st.title("CareerPilot AI")
        st.divider()

        config = get_provider_config()
        if config.api_key:
            st.success("已配置 DeepSeek API 密钥")
        else:
            st.warning("未配置 DeepSeek API 密钥，将使用确定性离线模式。")

        model = st.text_input("模型", value=config.model, placeholder="请输入 DeepSeek 模型名称")

        thinking = st.selectbox(
            "深度思考模式",
            THINKING_OPTIONS,
            index=_index_of(THINKING_OPTIONS, config.thinking),
            format_func=THINKING_LABELS.get,
        )
        reasoning_effort = st.selectbox(
            "推理强度",
            EFFORT_OPTIONS,
            index=_index_of(EFFORT_OPTIONS, config.reasoning_effort),
            disabled=thinking == "disabled",
            format_func=EFFORT_LABELS.get,
        )

        st.caption(f"接口地址：{config.base_url}")
        st.divider()

        selected_jd = st.selectbox("选择示例职位", list(SAMPLE_JDS))
        if st.button("加载示例数据", use_container_width=True):
            resume_text, jd_text = load_sample(selected_jd)
            st.session_state["sample_resume"] = resume_text
            st.session_state["sample_jd"] = jd_text
            st.success("示例数据已加载")

    return ProviderSettings(model=model, thinking=thinking, reasoning_effort=reasoning_effort)
