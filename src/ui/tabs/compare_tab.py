"""Compare Jobs tab: one resume against several job descriptions."""

import streamlit as st

from src.parsers.file_parser import parse_resume_file
from src.services.multi_jd import compare_jobs, to_table_rows
from src.services.provider_config import provider_overrides
from src.ui.sample_data import SAMPLE_JDS, load_sample, read_text

JD_SEPARATOR = "==="
MAX_JOBS = 6


def split_job_descriptions(text: str) -> list[tuple[str, str]]:
    """Split the textarea into (label, jd_text) pairs.

    Blocks are separated by a line of ===. A first line of "# Label" names the
    block; otherwise blocks are numbered.
    """

    blocks = [block.strip() for block in (text or "").split(JD_SEPARATOR)]
    jobs = []
    for index, block in enumerate([b for b in blocks if b], start=1):
        lines = block.splitlines()
        if lines and lines[0].strip().startswith("#"):
            label = lines[0].strip().lstrip("#").strip() or f"职位 {index}"
            body = "\n".join(lines[1:]).strip()
        else:
            label = f"职位 {index}"
            body = block
        jobs.append((label, body))
    return jobs


def _load_all_samples() -> str:
    parts = []
    for role, path in SAMPLE_JDS.items():
        parts.append(f"# {role}\n{read_text(path)}")
    return f"\n{JD_SEPARATOR}\n".join(parts)


RESUME_KEY = "compare_resume_text"
JD_KEY = "compare_jd_text"


def render(settings) -> None:
    st.markdown("#### 一份简历对比多个职位")
    st.caption(
        f"请使用单独一行 {JD_SEPARATOR} 分隔不同职位描述。"
        "每段开头可使用“# 职位名称”进行命名。"
    )

    # A keyed widget takes its value from session_state and ignores `value=` on
    # every rerun after the first, so the contents have to be seeded here and
    # written through session_state. Passing `value=` instead left both boxes
    # permanently empty and made "Load all sample JDs" do nothing.
    st.session_state.setdefault(RESUME_KEY, st.session_state.get("sample_resume", ""))
    st.session_state.setdefault(JD_KEY, "")

    # Above the columns: session_state for a widget key cannot be assigned once
    # that widget has been created in the same run.
    if st.button("加载全部示例职位", use_container_width=True):
        st.session_state[RESUME_KEY] = load_sample(next(iter(SAMPLE_JDS)))[0]
        st.session_state[JD_KEY] = _load_all_samples()
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        resume_file = st.file_uploader(
            "上传简历（TXT、PDF 或 DOCX）", type=["txt", "pdf", "docx"], key="compare_resume_upload"
        )
        pasted_resume = st.text_area("或在此粘贴简历文本", height=300, key=RESUME_KEY)
    with col2:
        jd_blocks = st.text_area("职位描述", height=340, key=JD_KEY)

    if st.button("开始职位对比", type="primary", use_container_width=True):
        _run_comparison(resume_file, pasted_resume, jd_blocks, settings)

    _render_result(st.session_state.get("comparison_result"))


def _run_comparison(resume_file, pasted_resume, jd_blocks, settings) -> None:
    try:
        file_text = parse_resume_file(resume_file) if resume_file else ""
        resume_text = file_text or pasted_resume
        jobs = split_job_descriptions(jd_blocks)

        if not resume_text.strip():
            st.error("请提供一份简历。")
            return
        if len(jobs) < 2:
            st.error(f"请至少提供两个职位描述，并使用 {JD_SEPARATOR} 分隔。")
            return
        if len(jobs) > MAX_JOBS:
            st.error(f"每次最多对比 {MAX_JOBS} 个职位。")
            return

        overrides = settings.as_overrides() if settings else {}
        with st.status(f"正在对比 {len(jobs)} 个职位...", expanded=True) as status:
            with provider_overrides(**overrides):
                result = compare_jobs(resume_text, jobs)
            status.update(label="对比完成", state="complete")
        st.session_state["comparison_result"] = result
    except Exception as exc:
        st.error(f"职位对比失败：{exc}")


def _render_result(result) -> None:
    if not result:
        st.info("请添加两个或更多职位描述，然后开始对比。")
        return

    best = result.best
    if best:
        st.success(f"最佳匹配：{best.label}（{best.score}/100）")

    st.dataframe(to_table_rows(result), use_container_width=True, hide_index=True)

    if result.common_missing_skills:
        st.markdown("#### 所有职位均缺失的技能")
        st.caption("这些技能在简历中尚未体现，但在所有对比职位中都有需求，优先补充可拓宽申请范围。")
        for skill in result.common_missing_skills:
            st.error(skill)
    elif len([job for job in result.jobs if not job.failed]) >= 2:
        st.info("没有发现所有职位都共同缺失的技能。")

    for job in result.ranked:
        if job.failed:
            continue
        with st.expander(f"{job.label} - {job.score}/100"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**已匹配**")
                for skill in job.matched_skills:
                    st.success(skill)
            with col2:
                st.markdown("**缺失**")
                for skill in job.missing_skills:
                    st.error(skill)
