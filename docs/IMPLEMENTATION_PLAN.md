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
DEEPSEEK_MODEL=your_selected_model
EMBEDDING_PROVIDER=local_hash
```

Acceptance criteria:

- Model name is configurable.
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

Verified:

- `python -m py_compile ...` passed for the main modules.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed with 8 tests.
- `python eval/run_eval.py` generated `outputs/evaluation_results.csv` with MVP and Phase 2 first-slice metrics.

Not yet verified because of local environment limits:

- `streamlit run app.py` has not been run successfully because `streamlit` is not installed in the current Python environment.
- `pip install -r requirements.txt` was blocked or timed out in this environment.
- Real DeepSeek API calls have not been tested yet because `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` are not configured.
- ChromaDB vectorstore build has not been tested because `chromadb` is not installed; the app currently falls back to markdown retrieval.

## Remaining Work

Immediate execution plan:

- [ ] Create a clean Python 3.11+ virtual environment.
- [ ] Install dependencies with `python -m pip install -r requirements.txt`.
- [ ] Copy `.env.example` to `.env`.
- [ ] Fill `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`.
- [ ] Run `streamlit run app.py`.
- [ ] Use the sample data loader and run one AI Intern analysis in the UI.
- [ ] Confirm all tabs render: Input, Match Report, Resume Tips, Application & Interview, Workflow Trace.
- [ ] Run one real DeepSeek-backed workflow and inspect whether JSON parsing is stable.
- [ ] If parsing is unstable, tighten prompts or structured parsing in `src/services/structured_output.py`.
- [ ] Run `python eval/run_eval.py` after the real workflow path is verified.
- [ ] Optionally install `chromadb` and verify vectorstore creation under `data/vectorstore/`.

Near-term MVP follow-up:

- Install dependencies in a clean Python 3.11+ environment.
- Configure `.env` with `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`.
- Start the Streamlit app with `streamlit run app.py`.
- Run one sample-data analysis through the UI and verify all tabs render correctly.
- Test one real DeepSeek-backed run and adjust prompts if output JSON is unstable.
- Optionally install `chromadb` and verify persistent vectorstore creation under `data/vectorstore/`.
- Improve evaluation so STAR coverage, keyword coverage, application answer quality, and interview prep quality reflect the generated output more accurately.
- Add screenshots or a demo GIF after the UI is verified.

Phase 2 follow-up:

- Expand ApplicationAnswerNode to support user-selected application questions while still refusing sensitive eligibility, visa, sponsorship, and compensation answers.
- Expand InterviewCoachNode with role-specific technical question sets and project deep-dive follow-ups.
- Add full application/interview parallel execution.
- Add SQLite run history if persistent local history is still desired.
- Add full Baseline vs LLM-only vs CareerPilot Full comparison.
- Expand tests around real LLM parsing failures and UI workflows.

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
- [ ] Environment: Install full dependencies
- [ ] Verification: Run Streamlit UI locally
- [ ] Verification: Run real DeepSeek-backed analysis
- [ ] Verification: Build ChromaDB vectorstore
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
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed with 8 tests.
- `python eval\run_eval.py` regenerated `outputs\evaluation_results.csv`.

Next: Verify Streamlit in a clean Python 3.11+ environment, then run one real DeepSeek-backed workflow to confirm structured JSON stability for the new Phase 2 nodes.
