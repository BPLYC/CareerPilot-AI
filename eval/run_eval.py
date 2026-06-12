"""Run evaluation cases across baseline, LLM-only, and full CareerPilot methods."""

import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.services.comparison_evaluation import evaluate_methods, summarize_comparison


def read_text(path: str) -> str:
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def main() -> None:
    cases_path = os.path.join(ROOT, "eval", "evaluation_cases.json")
    with open(cases_path, "r", encoding="utf-8") as handle:
        cases = json.load(handle)

    rows = []
    for case in cases:
        for metrics in evaluate_methods(read_text(case["resume_path"]), read_text(case["jd_path"])):
            rows.append({"case": case["case"], **metrics})

    output_path = os.path.join(ROOT, "outputs", "evaluation_results.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output_path}")

    summary_rows = summarize_comparison(rows)
    summary_path = os.path.join(ROOT, "outputs", "evaluation_comparison_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
