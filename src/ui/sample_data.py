"""Bundled sample resume and job descriptions."""

SAMPLE_JDS = {
    "AI Intern": "data/sample_jd_ai_intern.txt",
    "Data Analyst": "data/sample_jd_data_analyst.txt",
    "SWE Intern": "data/sample_jd_swe_intern.txt",
}

SAMPLE_RESUME_PATH = "data/sample_resume.txt"


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def load_sample(selected_jd: str) -> tuple[str, str]:
    """Return (resume_text, jd_text) for the chosen sample role."""

    return read_text(SAMPLE_RESUME_PATH), read_text(SAMPLE_JDS[selected_jd])
