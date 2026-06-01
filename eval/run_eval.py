"""Run MVP evaluation cases."""

import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.services.evaluation import evaluate_state
from src.workflow.careerpilot_graph import run_workflow
from src.workflow.state import create_initial_state


def read_text(path: str) -> str:
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def main() -> None:
    cases_path = os.path.join(ROOT, "eval", "evaluation_cases.json")
    with open(cases_path, "r", encoding="utf-8") as handle:
        cases = json.load(handle)

    rows = []
    for case in cases:
        state = create_initial_state(read_text(case["resume_path"]), read_text(case["jd_path"]))
        final_state = run_workflow(state)
        metrics = evaluate_state(final_state)
        rows.append({"case": case["case"], "method": "CareerPilot", **metrics})

    output_path = os.path.join(ROOT, "outputs", "evaluation_results.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
