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

- ApplicationAnswerNode. First deterministic/LLM-compatible slice implemented.
- InterviewCoachNode. First deterministic/LLM-compatible slice implemented.
- Full DOCX polish.
- Parallel application and interview nodes.
- SQLite result persistence.
- Baseline vs LLM-only vs CareerPilot Full evaluation.
- Demo GIF and screenshots.

## Current Status

The initial MVP code scaffold is implemented, but the project is not fully production-ready yet.

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

Verified:

- `python -m py_compile ...` passed for the main modules.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed with 16 tests.
- `python eval/run_eval.py` generated `outputs/evaluation_results.csv` with MVP and Phase 2 first-slice metrics.
- `streamlit` 1.58.0 is installed in `.venv`.
- `streamlit run app.py --server.port 8501 --server.headless true` returned HTTP 200 on `http://localhost:8501`.
- Direct DeepSeek API smoke test succeeded with `deepseek-v4-pro`, thinking enabled, `reasoning_effort=high`, and returned `reasoning_content`.
- Full DeepSeek-backed CareerPilot sample workflow succeeded with the default `deepseek-v4-pro`, thinking disabled, low effort configuration: score 55, 8 optimized bullets, 4 application answer fields, 5 interview questions, and `errors=0`.
- ChromaDB is installed and `data/vectorstore/` was created.

Not yet fully verified because of current environment limits:

- Full manual browser interaction with all Streamlit tabs still needs to be checked by opening `http://localhost:8501`.
- DeepSeek thinking enabled with high reasoning effort is verified for a direct smoke test, but full multi-node workflow is slow and should be used selectively.

## Remaining Work

Manual UI verification for the user:

- Open `http://localhost:8501` while Streamlit is running.
- In the sidebar, keep `Thinking Mode` as `disabled` and `Reasoning Effort` as `low` for a faster local demo.
- Click `Load Sample Data`.
- Click `Run CareerPilot Analysis`.
- Check all five tabs: Input, Match Report, Resume Tips, Application & Interview, Workflow Trace.
- Confirm the generated bullets, application answers, and interview questions do not invent resume facts.
- If the workflow trace shows `Fallback scoring completed` for the sample data, rerun after the cache key version update or clear `outputs/cache/`; stale pre-fix cache entries can show old fallback traces.

Immediate execution plan:

- [x] Create a clean Python 3.11+ virtual environment.
- [x] Install dependencies with `python -m pip install -r requirements.txt`.
- [x] Copy `.env.example` to `.env`.
- [x] Fill `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`.
- [x] Run `streamlit run app.py`.
- [ ] Use the sample data loader and run one AI Intern analysis in the UI.
- [ ] Confirm all tabs render: Input, Match Report, Resume Tips, Application & Interview, Workflow Trace.
- [x] Rerun one real DeepSeek-backed workflow after schema normalization and inspect whether JSON parsing is stable.
- [x] If parsing is unstable, tighten prompts or structured parsing in `src/services/structured_output.py`.
- [x] Run `python eval/run_eval.py` after the real workflow path is verified.
- [x] Optionally install `chromadb` and verify vectorstore creation under `data/vectorstore/`.

Near-term MVP follow-up:

- Use the existing `.venv` Python 3.12 environment.
- Keep `.env` configured with `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_THINKING`, and `DEEPSEEK_REASONING_EFFORT`.
- Start the Streamlit app with `.venv\Scripts\python.exe -m streamlit run app.py`.
- Run one sample-data analysis through the UI and verify all tabs render correctly.
- Use non-thinking mode for the local demo path unless the user specifically wants slower reasoning output.
- Address the LangChain Chroma deprecation warning later by moving to `langchain-chroma` if persistent vectorstore work continues.
- Improve evaluation so STAR coverage, keyword coverage, application answer quality, and interview prep quality reflect the generated output more accurately.
- Add screenshots or a demo GIF after the UI is verified.

Phase 2 follow-up:

- Expand ApplicationAnswerNode to support user-selected application questions while still refusing sensitive eligibility, visa, sponsorship, and compensation answers.
- Expand InterviewCoachNode with role-specific technical question sets and project deep-dive follow-ups.
- Add full application/interview parallel execution.
- Add SQLite run history if persistent local history is still desired.
- Add full Baseline vs LLM-only vs CareerPilot Full comparison.
- Expand tests around real LLM parsing failures and UI workflows.

Known technical debt:

- `src/rag/build_vectorstore.py` still imports `Chroma` from `langchain_community.vectorstores`.
- LangChain now warns that this import path is deprecated and recommends the standalone `langchain-chroma` package.
- This does not block the current MVP because ChromaDB currently builds and local fallback retrieval still works.
- When RAG persistence becomes a priority, install `langchain-chroma`, update the import to `from langchain_chroma import Chroma`, and rerun vectorstore/evaluation checks.

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
- [ ] Phase 2: Parallel Application And Interview Expansion

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

- `.venv\Scripts\python.exe -m pytest -q` passed with 16 tests.
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

- `.venv\Scripts\python.exe -m pytest -q` passed with 16 tests.
- `.venv\Scripts\python.exe eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.

Note: A post-fix real DeepSeek rerun was not possible in this step because Codex network/usage approval was temporarily unavailable. The behavior is covered by unit tests and the previous default DeepSeek workflow had already reached `errors=0` before this cache-version follow-up.

### Current User Action Checklist

Date: 2026-06-02

The Streamlit app can be started with:

```powershell
cd D:\CareerPilot_AI
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

If `http://localhost:8501` refuses the connection, restart Streamlit with an explicit loopback address and open `http://127.0.0.1:8501`:

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

After opening `http://localhost:8501`, the user should load sample data, run the analysis, and inspect each tab for correctness. The most important review is factual safety: optimized bullets, application answers, and interview prep should stay grounded in the resume and job description.
