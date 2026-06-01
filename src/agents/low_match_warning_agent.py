"""Low-match conditional node."""


def low_match_warning_node(state) -> dict:
    report = state.get("match_report") or {}
    missing = report.get("missing_skills", [])[:5]
    advice = "Critical missing skills: " + (", ".join(missing) if missing else "not enough explicit JD overlap found")
    warning = (
        f"{advice}. Build one small portfolio project around these requirements or consider a role closer to your current background."
    )
    return {
        "warnings": [warning],
        "optimized_bullets": [],
        "workflow_trace": ["LowMatchWarningNode: Score below threshold (45). Optimization skipped. See warnings for recommended next steps."],
    }
