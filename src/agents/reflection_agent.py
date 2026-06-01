"""Reflection node for factual consistency checks."""

import re


def _unsupported_metric(bullet: str, resume_text: str) -> bool:
    metrics = re.findall(r"\b\d+(?:\.\d+)?%|\b\d+x\b|\$\d+", bullet or "", flags=re.IGNORECASE)
    return any(metric not in (resume_text or "") for metric in metrics)


def reflection_node(state) -> dict:
    bullets = state.get("optimized_bullets", [])
    resume_text = state.get("raw_resume_text", "")
    iteration = state.get("reflection_iteration", 0)
    issues = []
    for index, bullet in enumerate(bullets, start=1):
        text = bullet.get("optimized_bullet", "")
        if _unsupported_metric(text, resume_text):
            issues.append(f"Suggestion {index} contains a metric not present in the resume.")

    if issues and iteration < 2:
        next_iteration = iteration + 1
        return {
            "has_exaggeration": True,
            "reflection_feedback": " ".join(issues) + " Regenerate without unsupported numbers or claims.",
            "reflection_iteration": next_iteration,
            "workflow_trace": [f"ReflectionNode (Iteration {next_iteration}): {len(issues)} issue(s) found. Revising."],
        }

    finalized = []
    for bullet in bullets:
        updated = dict(bullet)
        if iteration > 0:
            updated["is_revised_by_reflection"] = True
        finalized.append(updated)
    feedback = "Max iterations reached." if issues else "Passed review."
    return {
        "has_exaggeration": False,
        "reflection_feedback": feedback,
        "optimized_bullets": finalized,
        "workflow_trace": [f"ReflectionNode (Iteration {iteration}): {len(issues)} issue(s) found. Finalizing."],
    }
