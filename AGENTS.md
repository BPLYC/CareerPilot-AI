# Agent Guide For CareerPilot AI

This file is for future coding agents working in this repository. Read it before changing code.

## Project Summary

CareerPilot AI is a local Streamlit app for resume and job-description matching. It uses a LangGraph workflow with conditional routing, a reflection loop, structured Pydantic outputs, and local RAG knowledge to help students prepare internship applications.

Read these files first:

- `docs/PROJECT_SPEC.md`: full consolidated product and implementation spec.
- `docs/IMPLEMENTATION_PLAN.md`: current status, near-term plan, and progress tracking.
- `README.md`: user-facing setup and run instructions.

## Current Status

The MVP is implemented and locally stabilized. Phase 2 now has multiple completed slices on the normal-match path:

- Conservative application answer starters and interview practice questions.
- Optional user-provided application questions, sensitive-question refusal, role-specific interview fallback questions, and project follow-up prompts.
- Expanded Phase 2 evaluation metrics.
- RAG Chroma dependency cleanup.
- Parallel application answer and interview prep execution.

Completed in code:

- Streamlit UI in `app.py`.
- LangGraph workflow with low-match branching and reflection loop.
- Deterministic fallback agents for offline tests and demos.
- DeepSeek OpenAI-compatible provider path with configurable model, thinking mode, and reasoning effort.
- Local markdown RAG fallback plus optional ChromaDB vectorstore path.
- TXT, PDF, and DOCX parser modules.
- Cache, evaluation script, sample data, knowledge base files, and tests.
- Phase 2 application answer and interview prep nodes on the normal-match path.
- Optional application question input in Streamlit.
- Cache key versioning for custom application questions.
- Sensitive application-question refusal for visa, work authorization, sponsorship, salary, legal eligibility, and compensation questions.
- Role-specific deterministic interview questions and project follow-up prompts.
- Structured-output normalization for common real DeepSeek schema drift.
- Expanded evaluation metrics for keyword coverage delta, application answer evidence, sensitive-question refusal, and interview prep coverage.
- Parallel Phase 2 application answer and interview prep execution with final-report join.
- SQLite-backed local run history summaries that do not persist raw resumes or raw job descriptions.
- Full comparison evaluation across Baseline, LLM-only, and CareerPilot Full.

Verified so far:

- `.venv` exists with Python 3.12.13.
- Streamlit 1.58.0 is installed in `.venv`.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed with 26 tests in the latest project docs.
- `python eval/run_eval.py` generated `outputs/evaluation_results.csv` and `outputs/evaluation_comparison_summary.csv` with MVP, Phase 2, and comparison metrics.
- `streamlit run app.py --server.port 8501 --server.headless true` returned HTTP 200 in prior verification.
- A full default DeepSeek-backed sample workflow ran with `errors=0`.
- ChromaDB is installed and `data/vectorstore/` has been created.
- `langchain-chroma` is installed and the old `langchain-community` dependency has been removed.

Historical Phase 1 closure check on 2026-06-08:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with the then-current test suite.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs/evaluation_results.csv`.
- A real DeepSeek-backed AI Intern sample workflow ran with score 55, 10 optimized bullets, 4 application answer fields, 6 interview questions, and `errors=0`.
- Streamlit was reachable at `http://127.0.0.1:8501` with HTTP 200.
- Conclusion: Phase 1 core workflow is complete enough to begin Phase 2. Keep manual all-tab UI QA as a short follow-up item, not a Phase 2 blocker.

Latest Phase 2 expansion check on 2026-06-09:

- `.\.venv\Scripts\python.exe -m py_compile app.py src\services\cache.py src\models\schemas.py src\workflow\state.py src\agents\application_answer_agent.py src\agents\interview_coach_agent.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 19 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs/evaluation_results.csv`.
- `http://127.0.0.1:8501` returned HTTP 200 from an already-running Streamlit server.
- Manual Streamlit UI verification passed after the user reran sample data with optional application questions.
- The Application & Interview tab showed Application Answer Starters, Custom Application Questions, Interview Practice, and safety notices.
- Conclusion: the custom application-question and role-specific interview fallback slice is implemented and manually verified in the UI.

Latest evaluation metrics check on 2026-06-11:

- `.\.venv\Scripts\python.exe -m py_compile src\services\evaluation.py src\utils\text_utils.py tests\test_evaluation.py tests\test_scoring.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 20 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs/evaluation_results.csv` with Phase 2 quality metrics.
- `http://127.0.0.1:8501` returned HTTP 200 after starting Streamlit with the documented `PATH` workaround.
- README screenshot capture was deferred because the in-app browser failed at its sandbox boundary and Playwright/Selenium were not installed locally.

Latest RAG dependency cleanup on 2026-06-11:

- Installed `langchain-chroma` 1.1.0 in `.venv`.
- Updated `src/rag/build_vectorstore.py` to import `Chroma` from `langchain_chroma`.
- Updated `requirements.txt` to require `langchain-chroma>=1.1.0` and `chromadb>=1.3.5`.
- Removed the unused `langchain-community` requirement and uninstalled the old local package from `.venv`.
- `get_or_build_vectorstore()` returned a `Chroma` object and `retrieve_context()` returned snippets from all expected RAG collections.
- `importlib.util.find_spec("langchain_community")` returned `None`.
- `.\.venv\Scripts\python.exe -m pip check` reported no broken requirements.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 20 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs/evaluation_results.csv` without the old Chroma deprecation warning.

Latest Phase 2 parallel execution check on 2026-06-11:

- `src/workflow/careerpilot_graph.py` now routes normal-match workflows from reflection into `phase_two_parallel`.
- The fallback runner executes `ApplicationAnswerNode` and `InterviewCoachNode` concurrently with `ThreadPoolExecutor`.
- The LangGraph path fans out from `phase_two_parallel` to both Phase 2 nodes and joins them before `final_report`.
- `.\.venv\Scripts\python.exe -m py_compile src\workflow\careerpilot_graph.py tests\test_workflow.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 22 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs/evaluation_results.csv`.
- A fallback workflow smoke test showed `PhaseTwoParallelNode`, both Phase 2 nodes, and exactly one final report trace entry.

Latest README screenshot capture on 2026-06-12:

- Added README screenshots under `docs/assets/`.
- `docs/assets/careerpilot-home.png` shows the initial Streamlit input screen with DeepSeek settings and the Phase 2 tabs.
- `docs/assets/careerpilot-sample-input.png` shows the sample resume and AI Intern job description loaded through the sidebar.
- `tools/capture_streamlit_screenshot.mjs` starts Streamlit, opens local Chrome headless through DevTools, waits for real Streamlit text instead of the loading skeleton, and writes both PNGs.
- Use the `node tools\capture_streamlit_screenshot.mjs` command documented in `README.md` to regenerate screenshots after UI changes.

Latest SQLite run history check on 2026-06-12:

- Added `src/services/run_history.py` with a standard-library SQLite store at `outputs/history.sqlite3`.
- Added a Streamlit `Run History` tab that shows the 10 most recent local run summaries.
- History records summary metadata only: role, score, output counts, warning/error counts, and matched/missing skills.
- Raw resume text and raw job-description text are not stored in SQLite.
- `outputs/*.sqlite3` is ignored by Git.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 24 tests.
- `http://127.0.0.1:8501` returned HTTP 200 after starting Streamlit with the new Run History tab.

Latest full comparison evaluation check on 2026-06-12:

- Added `src/services/comparison_evaluation.py` with reproducible `Baseline`, `LLM-only`, and `CareerPilot Full` evaluation paths.
- Updated `eval/run_eval.py` to write per-case method rows to `outputs/evaluation_results.csv` and method averages to `outputs/evaluation_comparison_summary.csv`.
- Added workflow structure metrics: RAG snippet count, workflow trace count, reflection review count, and Phase 2 parallel execution count.
- In the latest generated summary, Baseline has no generated bullets or RAG snippets, LLM-only has generated bullets but no RAG/reflection/parallel workflow counts, and CareerPilot Full includes RAG snippets, reflection review, and Phase 2 parallel execution.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 26 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated both evaluation CSV files.

Not fully verified yet:

- DeepSeek thinking mode with high reasoning effort is verified for a direct smoke test, but full multi-node workflow can be slow and should be used selectively.

## Local Web App Notes

Use the project virtual environment rather than the system Python:

```powershell
cd D:\CareerPilot_AI
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Then open:

```text
http://127.0.0.1:8501
```

If the page will not open:

- First check whether Streamlit is running:

```powershell
try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501 -TimeoutSec 5 | Select-Object StatusCode,StatusDescription } catch { $_.Exception.Message }
```

- If it says it cannot connect, start Streamlit with the `.venv` command above.
- If `localhost` fails, try `127.0.0.1`.
- In Codex's in-app browser, local HTTP may show `net::ERR_BLOCKED_BY_CLIENT` even when the server is healthy. In that case, trust `Invoke-WebRequest` or use the user's normal browser.
- If `Start-Process` fails while launching Streamlit on this Windows setup, clear the process `PATH` first because both `Path` and `PATH` may exist in the process environment.

## Development Principles

- Keep changes small and verifiable.
- Do not add speculative features.
- Do not hard-code a model name.
- Do not hard-code API keys.
- Preserve deterministic fallback behavior so tests can run without a real API key.
- Treat DeepSeek as an OpenAI-compatible endpoint.
- If an optional dependency is missing, use a fallback instead of crashing where possible.
- Never persist uploaded resumes to disk.
- Do not invent resume facts, metrics, skills, visa status, work authorization, or compensation details.

## Important Entry Points

- UI: `app.py`
- Workflow: `src/workflow/careerpilot_graph.py`
- State: `src/workflow/state.py`
- Schemas: `src/models/schemas.py`
- Provider config: `src/services/provider_config.py`
- LLM client: `src/services/llm_client.py`
- Prompts: `src/services/prompts.py`
- Structured output normalization: `src/services/structured_output.py`
- RAG retrieval: `src/rag/retriever.py`
- Vectorstore build: `src/rag/build_vectorstore.py`
- Evaluation: `eval/run_eval.py`

## Commands

Run tests in this environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; .\.venv\Scripts\python.exe -m pytest -q
```

Run evaluation:

```powershell
.\.venv\Scripts\python.exe eval\run_eval.py
```

Run the app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=low
EMBEDDING_PROVIDER=local_hash
```

Use non-thinking mode and low reasoning effort for faster local demos unless the user specifically asks for deeper reasoning output.

## Near-Term Next Work

1. Do focused Streamlit UI polish based on manual testing.
2. Add parser-specific tests and edge-case coverage for TXT, PDF, and DOCX uploads.
3. Expand tests around real LLM parsing failures and end-to-end UI workflows.
4. Optionally add a short demo GIF if the README needs a walkthrough.
