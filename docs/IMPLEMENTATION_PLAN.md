# CareerPilot AI Implementation Plan

## Summary

CareerPilot AI is a local Streamlit application for resume and job-description matching. It uses a LangGraph workflow with conditional routing, a reflection loop, and a local RAG knowledge base to help students prepare internship applications.

This file is the source of truth for the implementation plan and progress tracking. Development follows milestones instead of fixed day-by-day scheduling.

## Key Decisions

- Use DeepSeek through an OpenAI-compatible API client.
- Do not hard-code the model in the plan or business logic. The user can choose the model through environment variables or the UI.
- Keep the LLM provider configurable so the app can later support DeepSeek, other OpenAI-compatible endpoints, or a mock provider.
- Build the core LangGraph branches and reflection loop before adding richer RAG, UI, and evaluation polish.
- Keep API keys out of the repository and never persist uploaded resume files.

## Milestone 0: Save Plan And Project Foundation

Create the project structure, save this plan, and implement the foundation modules:

- `src/models/schemas.py`
- `src/workflow/state.py`
- `src/services/provider_config.py`
- `src/services/llm_client.py`
- `src/utils/text_utils.py`
- `src/services/scoring.py`

Acceptance criteria:

- This plan exists at `docs/IMPLEMENTATION_PLAN.md`.
- The Progress section exists.
- Pydantic models can be instantiated.
- `create_initial_state()` returns a complete state.
- Basic tests do not require a real API key.

## Milestone 1: Minimal LangGraph Workflow

Implement the core workflow without depending on full RAG or UI polish:

- ResumeParserNode
- JDAnalyzerNode
- RAGRetrieverNode
- MatchScoringNode
- LowMatchWarningNode
- ResumeOptimizerNode
- ReflectionNode
- FinalReportNode

Acceptance criteria:

- Normal matches route to resume optimization.
- Scores below 45 route to low-match warning and skip optimization.
- Reflection can loop back to the optimizer.
- Reflection stops after two iterations.
- `workflow_trace`, `warnings`, and `errors` preserve prior entries.

## Milestone 2: DeepSeek LLM Integration

Connect DeepSeek through an OpenAI-compatible client while keeping mock and deterministic fallbacks available.

Environment variables:

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=low
EMBEDDING_PROVIDER=local_hash
```

Acceptance criteria:

- Model name is configurable.
- DeepSeek thinking mode and reasoning effort are configurable.
- LLM parsing errors are recorded in `errors`.
- Prompts are centralized in `src/services/prompts.py`.
- The app does not invent resume facts, skills, metrics, visa details, authorization status, or compensation answers.

## Milestone 3: RAG Knowledge Base

Build a local knowledge base with ChromaDB when dependencies are installed, with a deterministic fallback retriever for tests and offline demos.

MVP collections:

- `resume_bullets`
- `star_examples`
- `skill_taxonomy`

Acceptance criteria:

- Knowledge files exist under `data/knowledge_base/`.
- RAGRetrieverNode does not call the LLM.
- `data/vectorstore/` is ignored by git.

## Milestone 4: Sample Data And Parsers

Add sample data and file parsing.

Acceptance criteria:

- TXT input works.
- Text PDF parsing is supported when PyMuPDF is installed.
- DOCX parsing is present as a Phase 2-ready implementation.
- Uploaded files are handled in memory only.
- Empty inputs do not crash.

## Milestone 5: Streamlit MVP UI

Build the local demo UI:

- Sidebar API/provider status.
- User-selected model.
- Sample data loader.
- Input tab.
- Match Report tab.
- Resume Tips tab.
- Application & Interview tab.
- Workflow Trace tab.

Acceptance criteria:

- `streamlit run app.py` starts the app.
- Sample data can run end to end.
- Low-match warnings and workflow trace are visible.
- AI-generated content includes a review notice.

## Milestone 6: Cache And Evaluation

Add a file cache and basic evaluation metrics.

Acceptance criteria:

- Results can be cached under `outputs/cache/`.
- Evaluation can output CSV.
- Metrics include keyword coverage, skill match rate, missing skills, bullet count, reflection revision rate, and STAR coverage.

## Milestone 7: README And Demo Polish

Document setup, architecture, workflow, RAG, evaluation, safety, limitations, and future work.

## Phase 2 Plan

Implemented:

- ApplicationAnswerNode deterministic/LLM-compatible drafting.
- InterviewCoachNode deterministic/LLM-compatible practice questions.
- Custom application questions with sensitive-question refusal.
- Role-specific interview practice and project follow-up fallback questions.
- Parallel application and interview nodes with a final-report join.
- Basic DOCX text extraction through `python-docx`.
- SQLite summary-only run history.
- Baseline vs LLM-only vs CareerPilot Full comparison evaluation.
- README screenshots and repeatable local Chrome capture tooling.

Remaining quality work:

- Focused Streamlit UI polish based on manual testing.
- Parser-specific tests and edge-case coverage for TXT, PDF, and DOCX uploads.
- Expanded tests for real LLM schema failures and end-to-end UI workflows.
- Optional short demo GIF.

## Optimization Round, 2026-07-23

Nine slices on branch `claude/project-optimization-e559bf`, one commit each.
`docs/OPTIMIZATION_LOG.md` records the evidence behind every change, including
the measurements that contradicted the original plan.

| Slice | Change |
| --- | --- |
| 1 | ruff, GitHub Actions CI, and a reproducible evaluation harness |
| 2 | `common.run_node()` replacing six copies of the LLM/fallback control flow |
| 3 | JSON-rendered prompt context; skill taxonomy moved to its own module |
| 4 | The compiled LangGraph put on the real execution path |
| 5 | Concurrent intake nodes; configurable timeout and retries |
| 6 | Parser and LLM-branch test coverage |
| 7 | `app.py` split into `src/ui/`; provider overrides scoped to a run |
| 8 | Markdown report export |
| 9 | Multi-JD comparison |
| 10 | RAG retrieval made selective (added after the first nine merged) |
| 11 | Vectorstore gated off when embeddings are hash-based, which retrieved worse |
| 12 | Screenshots refreshed; fixed the Compare Jobs sample loader they exposed |
| 13 | Corrected the scoring claim with measurement; fixed a 0-1 scale drift |
| 14 | Code-review fixes: latent chunking bug, honest RAG metric, weak tests |
| 15 | Score alignment: show the AI score against the deterministic baseline |

Slice 10 corrected a diagnosis made in the earlier slices. The RAG problem had
been recorded as "the knowledge base is too small". The corpus size was a
symptom: `split_markdown()` accumulated paragraphs to 1200 characters ignoring
markdown headings, so Machine Learning, Data Analysis, and Software Engineering
bullets shared one chunk and no query could separate them, while `category`
recorded only the last heading absorbed. Chunking per section, growing the
content, and weighting heading matches made retrieval selective; a new
`rag_corpus_fraction` metric measures that, because a snippet count cannot.

Defects found and fixed along the way:

- Evaluation called the real API on every run and returned different numbers
  each time, while being documented as reproducible. It is now deterministic by
  default and takes `--live`.
- The low-match warning was dropped when an LLM failure fell back to a sub-45
  score, so the UI lost the notice telling the applicant the role was a poor fit.
- Sensitive-question boundaries were enforced only on the success path.
- The job title regex was greedy and returned everything up to the last
  "Intern" in the document. That title shows in the Match Report and Run
  History and feeds the RAG query.
- The sensitive-question reminder rendered before any analysis had run.

Three claims in the original plan were wrong and are corrected in the log:
the duplicated control flow was in six nodes rather than ten; Python `repr` in
prompts costs the same tokens as JSON, so the reason to fix it is format
consistency rather than cost; and the two engines already agreed before slice 4,
so the accepted behaviour risk did not materialise.

Verification at the end of the round: `ruff check .` clean, 132 tests passing
(from 26), evaluation output byte-identical across runs.

## Current Status

The MVP is implemented and locally stabilized. Phase 2 application/interview expansion, evaluation metrics, RAG dependency cleanup, parallel execution, summary-only run history, comparison evaluation, and README screenshots are implemented. The project is still a local demo rather than a production service.

Completed in code:

- Project plan, README, requirements, env example, and gitignore.
- Pydantic schemas and LangGraph state.
- DeepSeek-compatible provider configuration.
- Deterministic fallback agents for offline development.
- LangGraph workflow shape with low-match branching and reflection loop.
- Local markdown RAG fallback and optional ChromaDB integration path.
- TXT/PDF/DOCX parser modules.
- Streamlit UI source code.
- Cache, evaluation script, sample data, knowledge base files, and basic tests.
- Phase 2 first slice: application answer starters and interview practice questions on the normal-match path.
- Python 3.12 virtual environment under `.venv` with project dependencies installed.
- DeepSeek V4 model configuration with thinking mode and reasoning effort controls.
- Streamlit sidebar controls for DeepSeek thinking mode and reasoning effort.
- Structured-output normalization for common real DeepSeek schema drift.
- Cache key versioning to avoid stale cached workflow states after LLM parsing fixes.
- Phase 2 expansion slice: optional user-provided application questions, custom answer starters, sensitive-question refusal, and role-specific interview follow-ups.
- Expanded evaluation metrics for keyword coverage delta, application answer evidence, sensitive-question refusal, and interview prep coverage.
- RAG Chroma integration migrated from deprecated `langchain_community.vectorstores.Chroma` to `langchain_chroma.Chroma`.
- Phase 2 application answer and interview prep nodes now run in parallel and join before final report.
- SQLite-backed run history summaries that do not persist raw resumes or raw job descriptions.
- Baseline vs LLM-only vs CareerPilot Full comparison evaluation with per-case and method-level CSV output.
- README screenshots and repeatable local Chrome capture tooling.

Verified:

- `python -m py_compile ...` passed for the main modules.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed with 26 tests.
- `python eval/run_eval.py` generated `outputs/evaluation_results.csv` and `outputs/evaluation_comparison_summary.csv` with MVP, Phase 2, and comparison metrics.
- `streamlit` 1.58.0 is installed in `.venv`.
- `streamlit run app.py --server.port 8501 --server.headless true` returned HTTP 200 on `http://localhost:8501`.
- Direct DeepSeek API smoke test succeeded with `deepseek-v4-pro`, thinking enabled, `reasoning_effort=high`, and returned `reasoning_content`.
- Full DeepSeek-backed CareerPilot sample workflow succeeded with the default `deepseek-v4-pro`, thinking disabled, low effort configuration: score 55, 8 optimized bullets, 4 application answer fields, 5 interview questions, and `errors=0`.
- ChromaDB is installed and `data/vectorstore/` was created.
- `get_or_build_vectorstore()` returned a `Chroma` object through `langchain-chroma`.

Not yet fully verified because of current environment limits:

- DeepSeek thinking enabled with high reasoning effort is verified for a direct smoke test, but full multi-node workflow is slow and should be used selectively.

## Remaining Work

Manual UI verification completed on 2026-06-09:

- Streamlit was open at `http://127.0.0.1:8501`.
- The user reran sample data with optional application questions.
- The Application & Interview tab showed Application Answer Starters, Custom Application Questions, Interview Practice, and safety notices.
- Custom application questions reached the UI after manual input.

Immediate execution plan:

- [x] Create a clean Python 3.11+ virtual environment.
- [x] Install dependencies with `python -m pip install -r requirements.txt`.
- [x] Copy `.env.example` to `.env`.
- [x] Fill `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`.
- [x] Run `streamlit run app.py`.
- [x] Use the sample data loader and run one AI Intern analysis in the UI.
- [x] Confirm the original five tabs render: Input, Match Report, Resume Tips, Application & Interview, Workflow Trace.
- [ ] Manually verify the newer Run History tab after at least one completed analysis.
- [x] Rerun one real DeepSeek-backed workflow after schema normalization and inspect whether JSON parsing is stable.
- [x] If parsing is unstable, tighten prompts or structured parsing in `src/services/structured_output.py`.
- [x] Run `python eval/run_eval.py` after the real workflow path is verified.
- [x] Optionally install `chromadb` and verify vectorstore creation under `data/vectorstore/`.

Near-term MVP follow-up:

- Use the existing `.venv` Python 3.12 environment.
- Keep `.env` configured with `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_THINKING`, and `DEEPSEEK_REASONING_EFFORT`.
- Start the Streamlit app with `.venv\Scripts\python.exe -m streamlit run app.py`.
- Use non-thinking mode for the local demo path unless the user specifically wants slower reasoning output.
- README screenshots were captured on 2026-06-12 with local Chrome headless and added under `docs/assets/`.

Phase 2 follow-up (all closed in the 2026-07-23 optimization round):

- [x] Streamlit UI polish. `app.py` split into `src/ui/`; the unconditional
      sensitive-question reminder fixed.
- [x] Parser edge-case coverage. `tests/test_parsers.py`.
- [x] Tests for LLM schema failures and end-to-end UI. `tests/test_llm_branches.py`
      and `tests/test_app_renders.py`.
- [ ] Optional short demo GIF.

Known technical debt:

- The LLM scores 15-20 points below the deterministic scorer on every sample
  role (AI Intern 40-55 vs 68, Data Analyst 60-65 vs 79, SWE 50 vs 72). Handled
  in slice 15: both scores are shown side by side and a warning fires past a
  20-point gap; the model number is not rewritten. Calibrating the scoring
  prompt to close the gap at the source remains open, if it is wanted.
- Synonym-aware retrieval needs a real embedding model. The Chroma path does not
  provide it: with the default hash embeddings, synonym similarity measures
  0.000 and retrieval ranks worse than term overlap, so it is gated off.
- DeepSeek thinking mode with high reasoning effort is verified only for a direct
  smoke test; full multi-node workflow use should remain selective because it is
  slow. `DEEPSEEK_REQUEST_TIMEOUT` now exists for that case.

Resolved during current stabilization:

- Old cached workflow results could keep showing pre-fix fallback traces in the UI. `src/services/cache.py` now includes a cache version prefix so old cache files are not reused after schema/parser fixes.
- DeepSeek sometimes returns `MatchReport.relevant_projects` as objects instead of strings. `src/services/structured_output.py` now normalizes those objects to project names before Pydantic validation.

## Progress

- [x] Milestone 0: Save Plan And Project Foundation
- [x] Milestone 1: Minimal LangGraph Workflow
- [x] Milestone 2: DeepSeek LLM Integration Code Path
- [x] Milestone 3: RAG Knowledge Base Files And Fallback Retrieval
- [x] Milestone 4: Sample Data And Parsers
- [x] Milestone 5: Streamlit MVP UI Source Code
- [x] Milestone 6: Cache And Evaluation Script
- [x] Milestone 7: README And Demo Polish Draft
- [x] Phase 2 First Slice: Application Answer And Interview Prep Nodes
- [x] Environment: Install full dependencies
- [x] Verification: Run Streamlit UI locally
- [x] Verification: Run real DeepSeek-backed analysis
- [x] Verification: Build ChromaDB vectorstore
- [x] Phase 2: Custom Application Questions And Role-Specific Interview Fallback
- [x] Verification: Manual Streamlit UI Flow With Custom Application Questions
- [x] Phase 2 Evaluation Metrics Expansion
- [x] Phase 2: Parallel Application And Interview Execution
- [x] README Screenshots
- [x] SQLite Run History Summaries
- [x] Full Baseline vs LLM-only vs CareerPilot Full Comparison

### Completed: Initial MVP Implementation

Date: 2026-05-30

Summary: Created the local project scaffold, saved the milestone plan, added schemas, state, DeepSeek-compatible client config, deterministic fallback agents, LangGraph workflow, knowledge base files, parsers, Streamlit UI, cache, evaluation script, README, and tests.

Files changed: project-wide initial scaffold.

Verification: Run `python -m pytest` for tests and `streamlit run app.py` for the UI after installing dependencies.

Next: Install dependencies, configure `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL`, then run the Streamlit app with sample data.

### Completed: Phase 2 First Slice

Date: 2026-05-30

Summary: Added conservative application answer starters and interview practice questions for normal-match workflows. The new nodes use existing resume, JD, match report, and RAG context; they keep sensitive visa, authorization, sponsorship, salary, and legal eligibility answers assigned to the user. The Application & Interview UI tab now renders these outputs instead of a placeholder. Evaluation now records `application_answer_count` and `interview_question_count`.

Files changed:

- `src/models/schemas.py`
- `src/services/prompts.py`
- `src/rag/retriever.py`
- `src/agents/application_answer_agent.py`
- `src/agents/interview_coach_agent.py`
- `src/workflow/careerpilot_graph.py`
- `src/services/evaluation.py`
- `app.py`
- `tests/test_workflow.py`
- `outputs/evaluation_results.csv`

Verification:

- `python -m py_compile app.py src\services\evaluation.py src\models\schemas.py src\workflow\careerpilot_graph.py src\agents\application_answer_agent.py src\agents\interview_coach_agent.py`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed; the current expanded suite is tracked in the latest verification section.
- `python eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.

Next: Verify Streamlit in a clean Python 3.11+ environment, then run one real DeepSeek-backed workflow to confirm structured JSON stability for the new Phase 2 nodes.

### Completed: Local Environment And DeepSeek Setup

Date: 2026-06-01

Summary: Created `.venv` with Python 3.12.13, installed project dependencies including Streamlit 1.58.0 and ChromaDB 1.5.9, configured `.env` locally, updated DeepSeek defaults to `deepseek-v4-pro` with thinking enabled and high reasoning effort, and added small structured-output normalization for real LLM schema drift. The `.env` file is ignored by git and the API key is not stored in documentation.

Files changed:

- `.env`
- `.env.example`
- `README.md`
- `docs/PROJECT_SPEC.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `src/services/provider_config.py`
- `src/services/llm_client.py`
- `src/services/structured_output.py`
- `src/models/schemas.py`
- `tests/conftest.py`
- `data/vectorstore/`

Verification:

- `.venv\Scripts\python.exe -m pip install -r requirements.txt` completed.
- `.venv\Scripts\streamlit.exe --version` returned Streamlit 1.58.0.
- `.venv\Scripts\python.exe -m pytest -q` passed; the current expanded suite is tracked in the latest verification section.
- `.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.
- Direct DeepSeek API smoke test succeeded with `deepseek-v4-pro`, thinking enabled, `reasoning_effort=high`, and returned `reasoning_content`.
- `streamlit run app.py --server.port 8501 --server.headless true` returned HTTP 200 on `http://localhost:8501`.

Remaining: Manually click through the Streamlit UI tabs with sample data, then continue Phase 2 expansion.

### Completed: Real DeepSeek Workflow Stabilization

Date: 2026-06-02

Summary: Re-ran the real DeepSeek-backed sample workflow after network/usage approval was available, fixed additional real LLM schema drift, added test coverage for those output shapes, and changed the local demo default to `DEEPSEEK_THINKING=disabled` with `DEEPSEEK_REASONING_EFFORT=low` for reasonable latency. Thinking mode remains available through `.env` and the Streamlit sidebar.

Files changed:

- `.env`
- `.env.example`
- `app.py`
- `README.md`
- `docs/PROJECT_SPEC.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `src/services/provider_config.py`
- `src/services/structured_output.py`
- `src/models/schemas.py`
- `tests/test_structured_output.py`

Verification:

- `.venv\Scripts\python.exe -m pytest -q` passed with 19 tests.
- `.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.
- Real DeepSeek workflow with current default `.env` succeeded: score 55, 8 optimized bullets, 4 application answer fields, 5 interview questions, `errors=0`.
- `streamlit run app.py --server.port 8501 --server.headless true` returned HTTP 200 on `http://localhost:8501`.

Next: Open `http://localhost:8501`, load sample data, run the app through the UI, and confirm all five tabs render the expected output.

### Completed: UI Cache And Match Report Stabilization

Date: 2026-06-02

Summary: Investigated a UI run where the trace showed `MatchScoringNode: Fallback scoring completed`. The displayed state matched a stale pre-fix cache entry under `outputs/cache/`. Added cache key versioning and `MatchReport.relevant_projects` normalization so future runs do not reuse stale cached workflow states and can tolerate DeepSeek returning relevant projects as objects.

Files changed:

- `.gitignore`
- `docs/IMPLEMENTATION_PLAN.md`
- `src/services/cache.py`
- `src/services/structured_output.py`
- `tests/test_structured_output.py`

Verification:

- `.venv\Scripts\python.exe -m pytest -q` passed with 19 tests.
- `.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.

Note: A post-fix real DeepSeek rerun was not possible in this step because Codex network/usage approval was temporarily unavailable. The behavior is covered by unit tests and the previous default DeepSeek workflow had already reached `errors=0` before this cache-version follow-up.

### Completed: Phase 2 Custom Questions And Interview Expansion

Date: 2026-06-08

Summary: Expanded the Phase 2 application and interview prep slice. The Streamlit input page now accepts optional application questions, passes them through the workflow state, and includes them in the cache key. `ApplicationAnswerNode` generates conservative custom answer starters while forcing visa, work authorization, sponsorship, salary, legal eligibility, and compensation questions back to the applicant. `InterviewCoachNode` now adds role-specific technical questions and project follow-up prompts in deterministic fallback mode.

Files changed:

- `app.py`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/PROJECT_SPEC.md`
- `src/agents/application_answer_agent.py`
- `src/agents/interview_coach_agent.py`
- `src/models/schemas.py`
- `src/services/cache.py`
- `src/workflow/state.py`
- `tests/test_workflow.py`

Verification:

- `.\.venv\Scripts\python.exe -m py_compile app.py src\services\cache.py src\models\schemas.py src\workflow\state.py src\agents\application_answer_agent.py src\agents\interview_coach_agent.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 19 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.
- `http://127.0.0.1:8501` returned HTTP 200 from an already-running Streamlit server.
- Manual UI verification passed after the user reran sample data with optional application questions. The Application & Interview tab showed Application Answer Starters, Custom Application Questions, Interview Practice, and safety notices.

Next: README screenshots, SQLite run history, and full comparison evaluation were completed later on 2026-06-12.

### Completed: Phase 2 Evaluation Metrics Expansion

Date: 2026-06-11

Summary: Expanded deterministic evaluation beyond artifact counts. The evaluator now measures keyword coverage after combining the original resume with generated bullets, keyword coverage delta, corrected application answer counts, custom application answer count, sensitive custom-question refusal count, application answer evidence rate, interview prep-notes rate, project follow-up coverage, role-specific interview coverage, and required-skill evidence question count. While testing this, token normalization was tightened so sentence punctuation like `Python.` no longer prevents keyword matches.

Files changed:

- `README.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/PROJECT_SPEC.md`
- `AGENTS.md`
- `src/services/evaluation.py`
- `src/utils/text_utils.py`
- `tests/test_evaluation.py`
- `tests/test_scoring.py`
- `outputs/evaluation_results.csv`

Verification:

- `.\.venv\Scripts\python.exe -m py_compile src\services\evaluation.py src\utils\text_utils.py tests\test_evaluation.py tests\test_scoring.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 20 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.
- `http://127.0.0.1:8501` returned HTTP 200 after starting Streamlit with the documented `PATH` workaround.

Note: README screenshot capture was still pending during this slice because the in-app browser failed at its sandbox boundary on 2026-06-11. It was completed later on 2026-06-12 using local Chrome headless.

Next: SQLite run history and full comparison evaluation were completed later on 2026-06-12.

### Completed: Phase 2 Parallel Application And Interview Execution

Date: 2026-06-11

Summary: Changed the normal-match Phase 2 workflow so application answer drafting and interview coaching run in parallel after reflection passes or reaches its limit. The fallback runner now uses `ThreadPoolExecutor` for the two Phase 2 nodes. The LangGraph path now fans out from `phase_two_parallel` to `application_answer` and `interview_coach`, then joins both branches before `final_report`. Low-match workflows still skip Phase 2 prep and go directly from low-match warning to final report.

Files changed:

- `src/workflow/careerpilot_graph.py`
- `tests/test_workflow.py`
- `README.md`
- `AGENTS.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/PROJECT_SPEC.md`
- `outputs/evaluation_results.csv`

Verification:

- `.\.venv\Scripts\python.exe -m py_compile src\workflow\careerpilot_graph.py tests\test_workflow.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest tests\test_workflow.py -q` passed with 9 tests.
- `.\.venv\Scripts\python.exe -c "from src.workflow.careerpilot_graph import graph; print(type(graph).__name__ if graph else 'fallback')"` returned `CompiledStateGraph`.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 22 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.
- A fallback workflow smoke test showed `PhaseTwoParallelNode`, `ApplicationAnswerNode`, `InterviewCoachNode`, and exactly one `FinalReportNode` trace entry.

Next: README screenshots, SQLite run history, and full comparison evaluation were completed later on 2026-06-12.

### Completed: RAG Chroma Dependency Cleanup

Date: 2026-06-11

Summary: Replaced the deprecated `langchain_community.vectorstores.Chroma` import with the standalone `langchain_chroma.Chroma` integration. The optional vectorstore path still falls back to local markdown retrieval if Chroma loading or construction fails, so deterministic offline behavior is preserved.

Files changed:

- `requirements.txt`
- `src/rag/build_vectorstore.py`
- `README.md`
- `AGENTS.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/PROJECT_SPEC.md`
- `outputs/evaluation_results.csv`

Verification:

- Installed `langchain-chroma` 1.1.0 in `.venv`.
- `.\.venv\Scripts\python.exe -m py_compile src\rag\build_vectorstore.py src\rag\retriever.py` passed.
- `.\.venv\Scripts\python.exe -c "from langchain_chroma import Chroma; print(Chroma.__name__)"` returned `Chroma`.
- `.\.venv\Scripts\python.exe -c "from src.rag.build_vectorstore import get_or_build_vectorstore; vs=get_or_build_vectorstore(); print(type(vs).__name__ if vs is not None else 'fallback')"` returned `Chroma`.
- `.\.venv\Scripts\python.exe -c "from src.rag.retriever import retrieve_context; ctx=retrieve_context({'job_title':'AI Intern','required_skills':['Python','PyTorch'],'tools_and_technologies':['PyTorch']}); print({k: len(v) for k, v in ctx.items()})"` returned snippets for all expected RAG collections.
- `.\.venv\Scripts\python.exe -c "import importlib.util; print(importlib.util.find_spec('langchain_community'))"` returned `None` after uninstalling the old local package.
- `.\.venv\Scripts\python.exe -m pip check` reported no broken requirements.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 20 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv` without the old Chroma deprecation warning.

Next: README screenshots, SQLite run history, and full comparison evaluation were completed later on 2026-06-12.

### Current User Action Checklist

Date: 2026-06-09

The Streamlit app can be started with:

```powershell
cd D:\CareerPilot_AI
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

If `http://localhost:8501` refuses the connection, restart Streamlit with an explicit loopback address and open `http://127.0.0.1:8501`:

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

The sample-data Streamlit UI flow has been manually verified, including optional application questions and the Application & Interview tab.

Current next work options:

- Do focused Streamlit UI polish based on manual testing.
- Add parser-specific tests and edge-case coverage for TXT, PDF, and DOCX uploads.
- Expand tests around real LLM parsing failures and end-to-end UI workflows.
- Add an optional demo GIF if a short walkthrough would help the README.

### Completed: README Screenshots

Date: 2026-06-12

Summary: Added README demo screenshots for the initial input screen and the sample-data-loaded Streamlit state. Because the Codex in-app browser still fails at its sandbox boundary on this machine, the capture path uses local Chrome headless through a small DevTools script instead of the in-app browser.

Files changed:

- `README.md`
- `docs/assets/careerpilot-home.png`
- `docs/assets/careerpilot-sample-input.png`
- `tools/capture_streamlit_screenshot.mjs`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/PROJECT_SPEC.md`
- `AGENTS.md`

Verification:

- `tools/capture_streamlit_screenshot.mjs` started Streamlit at `http://127.0.0.1:8501`.
- Local Chrome headless waited for real Streamlit text before capturing, avoiding the loading skeleton.
- Generated `docs/assets/careerpilot-home.png` at 1440x1200.
- Generated `docs/assets/careerpilot-sample-input.png` at 1440x1200.

Next: Full comparison evaluation was completed later on 2026-06-12; consider focused Streamlit UI polish or an optional demo GIF.

### Completed: SQLite Run History Summaries

Date: 2026-06-12

Summary: Added a local SQLite run history for Streamlit analyses. Each completed analysis records summary metadata only, including role, match score, output counts, warning/error counts, and matched/missing skills. Raw resume text and raw job-description text are intentionally not persisted.

Files changed:

- `app.py`
- `.gitignore`
- `src/services/run_history.py`
- `tests/test_run_history.py`
- `README.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/PROJECT_SPEC.md`
- `AGENTS.md`

Verification:

- `.\.venv\Scripts\python.exe -m py_compile app.py src\services\run_history.py tests\test_run_history.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest tests\test_run_history.py -q` passed with 2 tests.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 24 tests.
- `http://127.0.0.1:8501` returned HTTP 200 after starting Streamlit with the new Run History tab.

Next: Full comparison evaluation was completed later on 2026-06-12; consider focused Streamlit UI polish.

### Completed: Full Comparison Evaluation

Date: 2026-06-12

Summary: Expanded the evaluation script to compare three reproducible methods across every evaluation case: `Baseline`, `LLM-only`, and `CareerPilot Full`. Baseline runs parsing, JD analysis, and scoring only. LLM-only runs generation without RAG retrieval, low-match branching, reflection, or parallel workflow tracing. CareerPilot Full runs the existing graph/fallback workflow. The output now includes both per-case rows and method-level averages.

Files changed:

- `eval/run_eval.py`
- `src/services/comparison_evaluation.py`
- `src/services/evaluation.py`
- `tests/test_comparison_evaluation.py`
- `tests/test_evaluation.py`
- `outputs/evaluation_results.csv`
- `outputs/evaluation_comparison_summary.csv`
- `README.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/PROJECT_SPEC.md`
- `AGENTS.md`

Verification:

- `.\.venv\Scripts\python.exe -m py_compile src\services\evaluation.py src\services\comparison_evaluation.py eval\run_eval.py tests\test_evaluation.py tests\test_comparison_evaluation.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest tests\test_evaluation.py tests\test_comparison_evaluation.py -q` passed with 3 tests.
- `.\.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv` and `outputs\evaluation_comparison_summary.csv`.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .\.venv\Scripts\python.exe -m pytest -q` passed with 26 tests.
- The summary CSV shows Baseline with 0 generated bullets and 0 RAG snippets, LLM-only with generated bullets but 0 RAG/reflection/parallel workflow counts, and CareerPilot Full with RAG snippets, reflection review, and Phase 2 parallel execution counts.

Next: Do focused Streamlit UI polish based on manual testing, or add an optional demo GIF.

### Completed: Explainable Scoring And Calibration

Date: 2026-07-26

Summary: Replaced the inflated count-based fallback score with a five-component rubric. Fixed the project self-match bug, removed project double counting from experience, added skill aliases and empty-required-skill safeguards, extracted real project/education/work evidence in the offline parser, and routed on the stable deterministic score. Match reports now carry an optional backward-compatible breakdown and reliability flag. The UI and Markdown export show the breakdown, while multi-JD ranking uses the stable score.

Evaluation now reports bilingual action/result/STAR proxy coverage, score fields, 12 synthetic monotonicity checks across the bundled cases, and separate Full/Full-no-RAG/Full-no-reflection results. These tests establish deterministic invariants and component execution; human-labelled calibration remains future work.

Verification:

- Full pytest suite passed with `--basetemp=.pytest_tmp`.
- Ruff passed.
- Deterministic evaluation regenerated all CSV outputs.
- All 12 synthetic score-monotonicity checks passed.
