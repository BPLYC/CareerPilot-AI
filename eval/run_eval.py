"""Run evaluation cases across baseline, LLM-only, and full CareerPilot methods.

Runs deterministically by default. `src.services.provider_config` calls
`load_dotenv()` at import time, and python-dotenv searches parent directories,
so a `.env` anywhere above the working directory is enough to make every agent
take its live-LLM branch. That would make each run cost money and return
different numbers, which is useless as a regression check, so this script
suppresses the credentials unless `--live` is passed explicitly.
"""

import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.agents.jd_analyzer_agent import fallback_analyze_jd
from src.rag.build_vectorstore import DISABLE_VECTORSTORE_ENV
from src.rag.retriever import retrieve_context
from src.services.comparison_evaluation import evaluate_methods, summarize_comparison
from src.services.evaluation import rag_context_overlap

# Cleared for deterministic runs. Emptying the key is what flips
# ProviderConfig.is_configured, and therefore can_use_llm(), to False.
LLM_ENV_KEYS = ["DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"]


def read_text(path: str) -> str:
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


def use_deterministic_agents() -> None:
    """Force every agent and the retriever onto their deterministic branches."""

    for key in LLM_ENV_KEYS:
        os.environ.pop(key, None)
    # Otherwise RAG snippet counts depend on whether this machine happens to
    # have built data/vectorstore/, which git does not track.
    os.environ[DISABLE_VECTORSTORE_ENV] = "1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the real LLM. Costs money and produces different numbers on every run.",
    )
    args = parser.parse_args()

    if args.live:
        print("Mode: LIVE. Calling the real LLM; results are not reproducible.")
    else:
        use_deterministic_agents()
        print("Mode: deterministic. Pass --live to call the real LLM.")

    cases_path = os.path.join(ROOT, "eval", "evaluation_cases.json")
    with open(cases_path, encoding="utf-8") as handle:
        cases = json.load(handle)

    rows = []
    for case in cases:
        for metrics in evaluate_methods(read_text(case["resume_path"]), read_text(case["jd_path"])):
            rows.append({"case": case["case"], **metrics})

    # Cross-case, so it cannot live in the per-case metrics: how much the
    # retrieved context is shared between roles. Unlike the per-row RAG numbers
    # this one moves when ranking changes.
    overlap = rag_context_overlap([retrieve_context(fallback_analyze_jd(read_text(c["jd_path"]))) for c in cases])
    print(f"RAG context overlap across the {len(cases)} cases: {overlap} (1.0 = every role got the same snippets)")

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
