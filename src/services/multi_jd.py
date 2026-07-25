"""Score one resume against several job descriptions and rank the results.

Students apply to many internships at once. Running them one at a time answers
"is this a fit" but not "which of these is the best use of my time" or "what one
skill would unlock the most of them".

Pure logic, no Streamlit, so it can be tested and reused.
"""

from dataclasses import dataclass, field

from src.services.cache import get_cache_key, load_from_cache, save_to_cache
from src.workflow.careerpilot_graph import run_workflow
from src.workflow.state import create_initial_state


@dataclass
class JobComparison:
    """One job's outcome, flattened for display."""

    label: str
    job_title: str
    score: int
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    bullet_count: int = 0
    error_count: int = 0
    failed: bool = False
    failure_reason: str = ""


@dataclass
class ComparisonResult:
    jobs: list[JobComparison] = field(default_factory=list)
    common_missing_skills: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[JobComparison]:
        """Best fit first. Jobs that failed to run sort last."""

        return sorted(self.jobs, key=lambda job: (not job.failed, job.score), reverse=True)

    @property
    def best(self) -> JobComparison | None:
        ranked = [job for job in self.ranked if not job.failed]
        return ranked[0] if ranked else None


def _summarise(label: str, state: dict) -> JobComparison:
    report = state.get("match_report") or {}
    analysis = state.get("jd_analysis") or {}
    return JobComparison(
        label=label,
        job_title=analysis.get("job_title") or label,
        score=report.get("overall_score", 0),
        matched_skills=list(report.get("matched_skills", [])),
        missing_skills=list(report.get("missing_skills", [])),
        bullet_count=len(state.get("optimized_bullets", [])),
        error_count=len(state.get("errors", [])),
    )


def find_common_missing_skills(jobs: list[JobComparison]) -> list[str]:
    """Skills missing from every job that ran.

    The intersection rather than the union: a skill only every posting wants is
    the one worth learning first. Order follows the first job's list so the
    result is stable rather than set-ordered.
    """

    usable = [job for job in jobs if not job.failed]
    if len(usable) < 2:
        return []

    shared = set(usable[0].missing_skills)
    for job in usable[1:]:
        shared &= set(job.missing_skills)
    return [skill for skill in usable[0].missing_skills if skill in shared]


def compare_jobs(
    resume_text: str,
    jobs: list[tuple[str, str]],
    runner=run_workflow,
    use_cache: bool = True,
) -> ComparisonResult:
    """Run the workflow for each (label, jd_text) pair and rank the outcomes.

    One job failing must not lose the others, so failures are recorded per job
    rather than raised.
    """

    results = []
    for label, jd_text in jobs:
        if not (jd_text or "").strip():
            results.append(
                JobComparison(label=label, job_title=label, score=0, failed=True, failure_reason="Empty job description.")
            )
            continue

        try:
            state = None
            key = get_cache_key(resume_text, jd_text, []) if use_cache else ""
            if use_cache:
                state = load_from_cache(key)
            if state is None:
                state = runner(create_initial_state(resume_text, jd_text))
                if use_cache:
                    save_to_cache(key, state)
            results.append(_summarise(label, state))
        except Exception as exc:
            results.append(
                JobComparison(label=label, job_title=label, score=0, failed=True, failure_reason=str(exc))
            )

    return ComparisonResult(jobs=results, common_missing_skills=find_common_missing_skills(results))


def to_table_rows(result: ComparisonResult) -> list[dict]:
    """Ranked rows shaped for st.dataframe."""

    rows = []
    for rank, job in enumerate(result.ranked, start=1):
        rows.append(
            {
                "排名": rank,
                "职位": job.label,
                "识别职位": job.job_title,
                "评分": "-" if job.failed else job.score,
                "匹配技能": len(job.matched_skills),
                "缺失技能": len(job.missing_skills),
                "简历建议": job.bullet_count,
                "状态": job.failure_reason if job.failed else "正常",
            }
        )
    return rows
