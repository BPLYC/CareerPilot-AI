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
            label = lines[0].strip().lstrip("#").strip() or f"Job {index}"
            body = "\n".join(lines[1:]).strip()
        else:
            label = f"Job {index}"
            body = block
        jobs.append((label, body))
    return jobs


def _load_all_samples() -> str:
    parts = []
    for role, path in SAMPLE_JDS.items():
        parts.append(f"# {role}\n{read_text(path)}")
    return f"\n{JD_SEPARATOR}\n".join(parts)


def render(settings) -> None:
    st.markdown("#### Compare one resume against several roles")
    st.caption(
        f"Separate job descriptions with a line containing {JD_SEPARATOR}. "
        "Start a block with '# Label' to name it."
    )

    col1, col2 = st.columns(2)
    with col1:
        resume_file = st.file_uploader(
            "Upload Resume (TXT, PDF, or DOCX)", type=["txt", "pdf", "docx"], key="compare_resume_upload"
        )
        pasted_resume = st.text_area(
            "Or paste resume text here",
            height=300,
            value=st.session_state.get("sample_resume", ""),
            key="compare_resume_text",
        )
    with col2:
        if st.button("Load all sample JDs", use_container_width=True):
            st.session_state["compare_jds"] = _load_all_samples()
            resume, _ = load_sample(next(iter(SAMPLE_JDS)))
            st.session_state["sample_resume"] = resume
        jd_blocks = st.text_area(
            "Job descriptions",
            height=340,
            value=st.session_state.get("compare_jds", ""),
            key="compare_jd_text",
        )

    if st.button("Compare roles", type="primary", use_container_width=True):
        _run_comparison(resume_file, pasted_resume, jd_blocks, settings)

    _render_result(st.session_state.get("comparison_result"))


def _run_comparison(resume_file, pasted_resume, jd_blocks, settings) -> None:
    try:
        file_text = parse_resume_file(resume_file) if resume_file else ""
        resume_text = file_text or pasted_resume
        jobs = split_job_descriptions(jd_blocks)

        if not resume_text.strip():
            st.error("Please provide a resume.")
            return
        if len(jobs) < 2:
            st.error(f"Please provide at least two job descriptions, separated by {JD_SEPARATOR}.")
            return
        if len(jobs) > MAX_JOBS:
            st.error(f"Please compare at most {MAX_JOBS} roles at a time.")
            return

        overrides = settings.as_overrides() if settings else {}
        with st.status(f"Comparing {len(jobs)} roles...", expanded=True) as status:
            with provider_overrides(**overrides):
                result = compare_jobs(resume_text, jobs)
            status.update(label="Comparison complete", state="complete")
        st.session_state["comparison_result"] = result
    except Exception as exc:
        st.error(f"Comparison failed: {exc}")


def _render_result(result) -> None:
    if not result:
        st.info("Add two or more job descriptions, then run the comparison.")
        return

    best = result.best
    if best:
        st.success(f"Best fit: {best.label} ({best.score}/100)")

    st.dataframe(to_table_rows(result), use_container_width=True, hide_index=True)

    if result.common_missing_skills:
        st.markdown("#### Missing from every role")
        st.caption("Skills absent from your resume across all compared roles. These unlock the most applications.")
        for skill in result.common_missing_skills:
            st.error(skill)
    elif len([job for job in result.jobs if not job.failed]) >= 2:
        st.info("No skill is missing across all of these roles.")

    for job in result.ranked:
        if job.failed:
            continue
        with st.expander(f"{job.label} - {job.score}/100"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Matched**")
                for skill in job.matched_skills:
                    st.success(skill)
            with col2:
                st.markdown("**Missing**")
                for skill in job.missing_skills:
                    st.error(skill)
