# Agent Guide For CareerPilot AI

This file is for future coding agents working in this repository. Read it before changing code.

## Project Summary

CareerPilot AI is a local Streamlit app for resume and job-description matching. It uses a LangGraph workflow with conditional routing, a reflection loop, structured Pydantic outputs, and local RAG knowledge to help students prepare internship applications.

Read these files first:

- `docs/PROJECT_SPEC.md`: full consolidated product and implementation spec.
- `docs/IMPLEMENTATION_PLAN.md`: current status, near-term plan, and progress tracking.
- `docs/OPTIMIZATION_LOG.md`: the 2026-07 optimization round, with the evidence behind each change.
- `README.md`: user-facing setup and run instructions.

## Things That Will Waste Your Time If You Do Not Know Them

- **`pytest` needs `--basetemp`** in this environment. Without it, tests using
  `tmp_path` fail with `PermissionError` on the shared temp directory and you
  get a misleading "25 passed, 1 error".
- **Setting `DEEPSEEK_API_KEY=""` in the shell does not force offline mode.**
  `provider_config` calls `load_dotenv()` at import, and python-dotenv searches
  parent directories, so `.env` above the working directory puts the key back.
  Use `eval.run_eval.use_deterministic_agents()`, which clears after import.
- **`eval/run_eval.py` is deterministic by default** and takes `--live` to call
  the real model. Do not remove that gate: before it existed, every evaluation
  run cost money and returned different numbers.
- **HTTP 200 from Streamlit does not verify the UI.** The server returns shell
  HTML without executing `app.py` until a session connects. Use
  `tests/test_app_renders.py`, which runs the script through Streamlit's
  `AppTest`.
- **`tests/conftest.py` clears the API key for every test.** A test meaning to
  exercise the LLM branch must patch `src.agents.common.can_use_llm`, or it will
  pass while testing the fallback instead.
- **A Streamlit widget with a `key` ignores `value=` after its first render.**
  Seed `st.session_state[key]` and write through it instead, and assign before
  the widget is created in that run. Passing both silently broke the Compare
  Jobs sample loader for an entire slice, and unit tests over the underlying
  function did not notice. Drive the UI with `AppTest` when a button is meant
  to change what a widget shows.
- **The LLM scores 15-20 points below the deterministic scorer**, consistently
  across the sample roles (AI Intern 40-55 vs 68, Data Analyst 60-65 vs 79, SWE
  50 vs 72). Run-to-run variation is only 0-15 points, so a single differing run
  is usually the offset rather than a regression. Do not freeze a live score
  into a screenshot; the capture tool defaults to the deterministic path.
- **The Chroma vectorstore is not the better retrieval path by default.**
  `LocalHashEmbeddings` buckets tokens by md5 into 64 dimensions: synonym
  similarity is 0.000 and 839 tokens collide into those buckets 13-deep. Ranking
  by term overlap beats it, so `has_semantic_embeddings()` skips the vectorstore
  unless real embeddings are configured. Enabling Chroma is not an optimisation
  here — measure before assuming otherwise.

## Current Status

An optimization round completed on 2026-07-23 on branch
`claude/project-optimization-e559bf`. Nine slices, each with its own commit and
an entry in `docs/OPTIMIZATION_LOG.md` recording the evidence. Headlines:

- The compiled LangGraph now runs; previously only a test ever invoked it.
- Six copies of the agent LLM/fallback control flow collapsed into
  `common.run_node()`, closing two places where the error path had drifted from
  the success path.
- Evaluation became reproducible and free by default; it had been calling the
  real API on every run while documented as reproducible.
- `app.py` split from 263 lines into `src/ui/`, and sidebar rendering no longer
  mutates `os.environ`.
- Intake nodes run concurrently; a live run measured 7.45s against 4.23s.
- Tests went from 26 to 132, adding the previously uncovered parser and LLM
  branches.
- New: Markdown report export, and multi-JD comparison.

Everything below predates that round.

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

- UI assembly: `app.py` (44 lines; each tab lives in `src/ui/tabs/`)
- Sidebar: `src/ui/sidebar.py`
- Analysis run with caching: `src/ui/analysis.py`
- Workflow: `src/workflow/careerpilot_graph.py`
- Shared agent skeleton: `src/agents/common.py` (`run_node`)
- State: `src/workflow/state.py`
- Schemas: `src/models/schemas.py`
- Provider config: `src/services/provider_config.py`
- LLM client: `src/services/llm_client.py`
- Prompts and JSON context rendering: `src/services/prompts.py`
- Skill taxonomy: `src/services/skill_taxonomy.py`
- Structured output normalization: `src/services/structured_output.py`
- Markdown export: `src/services/report_export.py`
- Multi-JD comparison: `src/services/multi_jd.py`
- RAG retrieval: `src/rag/retriever.py`
- Vectorstore build: `src/rag/build_vectorstore.py`
- Evaluation: `eval/run_eval.py`
- Budget guard for live API runs: `tools/check_deepseek_budget.py`

## Architecture Notes

Knowledge files are chunked **one chunk per markdown section**, and
`chunk.metadata["category"]` comes from that section's own heading. Retrieval
weights heading matches `HEADING_WEIGHT` times body matches, so headings are
load-bearing: adding content under an existing heading extends that topic, while
a new `#` heading creates a separately retrievable unit. `tests/test_rag_retrieval.py`
asserts each collection holds more chunks than the retriever requests; if you add
a collection, keep that true or retrieval has nothing to choose between.

`careerpilot_graph.py` holds two engines. `stream_workflow()` prefers the
compiled LangGraph and falls back to the sequential runner when langgraph is not
installed. `tests/test_workflow_parity.py` pins them to the same results; if you
change routing, change both and let that test tell you whether they still agree.

Every LLM-backed node goes through `common.run_node()`, which owns the
try/LLM-or-fallback/except shape. Its `refine` and `extra_state` hooks run on
both branches deliberately: applying them only on success is how the error path
silently drifted before.

## Commands

Run tests in this environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
```

Lint:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
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

1. Regenerate the README screenshots; they predate the Compare Jobs tab and the
   report export button.
2. Optionally add a short demo GIF if the README needs a walkthrough.
3. Synonym-aware retrieval, if it is ever wanted, needs a real embedding model.
   Do not reach for the Chroma path expecting this: with the default
   `LocalHashEmbeddings` it is measurably worse than term overlap, which is why
   `has_semantic_embeddings()` now gates it. It requires `EMBEDDING_PROVIDER=openai`
   or a local sentence-transformer; DeepSeek has no embeddings endpoint.
