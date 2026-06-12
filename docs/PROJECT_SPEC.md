# CareerPilot AI Project Specification

## Purpose

CareerPilot AI is a local AI-assisted internship preparation tool for students applying to AI, Data Science, Data Analyst, Software Engineering, Machine Learning, and Research internship roles.

The user provides a resume and a job description. The system runs a LangGraph-based workflow to parse the resume, analyze the JD, retrieve local RAG knowledge, score the match, branch on low-match cases, generate resume improvement suggestions, review those suggestions with a reflection loop, and produce a final report for the Streamlit UI.

This file consolidates the original project prompt with the revised implementation decisions made during development. It is intended as the durable context file for future agents and future conversation windows.

## Product Positioning

CareerPilot AI is not a simple prompt wrapper. Its core differentiators are:

- Real LangGraph conditional routing.
- A low-match branch when score is below 45.
- A reflection loop that can send generated bullets back to the optimizer.
- Local RAG knowledge injection from resume templates, STAR examples, and skill taxonomy.
- Structured Pydantic outputs.
- Evaluation metrics that quantify the workflow output.

## Explicit Non-Goals

- Do not automatically submit applications.
- Do not operate company application websites.
- Do not invent resume facts, skills, achievements, metrics, visa status, work authorization, or compensation expectations.
- Do not build a login system.
- Do not deploy to cloud for the MVP.
- Do not persist uploaded resume files to disk.

## Phases

The original prompt defines two product phases.

### Phase 1: MVP

Goal: local runnable demo with the core workflow.

Included:

- ResumeParserNode.
- JDAnalyzerNode.
- RAGRetrieverNode.
- MatchScoringNode.
- LowMatchWarningNode.
- ResumeOptimizerNode.
- ReflectionNode.
- FinalReportNode.
- TXT input support.
- PDF parser module.
- Streamlit UI source.
- Sample resume and three sample JDs.
- MVP evaluation metrics.
- Deterministic fallback logic so development can continue without an API key.

Current status: Phase 1 is complete enough for local demo use, dependencies are installed in `.venv`, Streamlit can start locally, a direct DeepSeek thinking-mode API smoke test has succeeded, and a full default DeepSeek-backed sample workflow has run with `errors=0`.

### Phase 2: Expansion

Goal: richer application preparation workflow after the MVP is verified.

Planned:

- ApplicationAnswerNode. First conservative drafting slice is implemented.
- InterviewCoachNode. First interview practice slice is implemented.
- Optional user-provided application questions with sensitive-question refusal are implemented.
- Role-specific fallback interview questions and project follow-ups are implemented.
- Parallel application and interview nodes are implemented.
- Full DOCX polish.
- SQLite local run history summaries are implemented.
- Full comparison evaluation is implemented: Baseline vs LLM-only vs CareerPilot Full.
- Demo GIF and screenshots.
- More complete UI verification and README assets.

## Implementation Decisions

### Schedule

The original Day 1 to Day 14 schedule was removed. Development now follows milestones and immediate verification steps. The project should move at the actual pace of the environment and available dependencies.

### Model And Provider

Do not hard-code a specific model into the project plan. The user will choose the model through `.env` or the Streamlit UI.

The default provider design is DeepSeek through an OpenAI-compatible API endpoint.

Environment variables:

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=low
EMBEDDING_PROVIDER=local_hash
```

The code keeps deterministic fallback paths for offline tests and demos.

### RAG

MVP RAG uses:

- `resume_bullets`
- `star_examples`
- `skill_taxonomy`

Phase 2 knowledge files exist but are not fully wired into the workflow yet:

- `application_question_examples`
- `interview_bank`

ChromaDB is optional for runtime and is accessed through `langchain-chroma`. In the current local environment `langchain-chroma` 1.1.0 and ChromaDB 1.5.9 are installed, and `data/vectorstore/` has been created. If ChromaDB is unavailable or loading fails, the app falls back to local markdown retrieval.

### Pydantic

All list defaults must use `Field(default_factory=list)` rather than mutable list defaults.

LLM outputs should be validated with Pydantic. JSON parse failures should be recorded in `state["errors"]`, not crash the app.

### LangGraph State

Important list fields should preserve previous entries:

- `workflow_trace`
- `warnings`
- `errors`

The implementation uses reducer annotations in `CareerPilotState` and a fallback merge helper for non-LangGraph local execution.

## Core Workflow

```text
START
  -> resume_parser_node
  -> jd_analyzer_node
  -> rag_retriever_node
  -> match_scoring_node
  -> route_after_match_scoring
       -> score < 45: low_match_warning_node -> final_report_node -> END
       -> score >= 45: resume_optimizer_node
             -> reflection_node
             -> route_after_reflection
                  -> has_exaggeration and iteration < 2: resume_optimizer_node
                  -> otherwise: phase_two_parallel_node
                         -> application_answer_node
                         -> interview_coach_node
                         -> join -> final_report_node -> END
```

Route rules:

- `route_after_match_scoring`: score below 45 goes to low-match warning.
- `route_after_reflection`: exaggeration plus iteration below 2 loops back to optimizer; otherwise it enters parallel Phase 2 preparation.

## Data Models

Main file:

- `src/models/schemas.py`

Models:

- `Education`
- `ProjectExperience`
- `WorkExperience`
- `ResumeProfile`
- `JobDescriptionAnalysis`
- `MatchReport`
- `BulletSuggestion`

## State

Main file:

- `src/workflow/state.py`

Important fields:

- Inputs: `raw_resume_text`, `raw_jd_text`
- Structured outputs: `resume_profile`, `jd_analysis`, `retrieved_context`, `match_report`
- Optimization: `optimized_bullets`, `has_exaggeration`, `reflection_feedback`, `reflection_iteration`
- Phase 2 inputs and outputs: `application_questions`, `application_answers`, `interview_questions`
- Logs: `workflow_trace`, `errors`, `warnings`

## Node Responsibilities

### ResumeParserNode

Parses resume text into `ResumeProfile`. It must not infer missing information. Missing information should remain `"unknown"` or empty lists.

### JDAnalyzerNode

Parses JD text into `JobDescriptionAnalysis`. Required and preferred skills are separated using JD wording. Fallback logic uses sentence-level checks to reduce accidental preferred/required mixing.

### RAGRetrieverNode

Does not call the LLM. It builds a query from job title, required skills, and tools, then retrieves local snippets.

### MatchScoringNode

Produces `MatchReport` with score from 0 to 100. Current fallback scoring uses skill overlap, relevant project count, education evidence, and experience evidence.

### LowMatchWarningNode

Runs when match score is below 45. It does not generate optimized bullets. It explains missing skills and next learning directions.

### ResumeOptimizerNode

Generates resume bullet suggestions from existing resume evidence. It must not add unsupported metrics or new experiences.

### ReflectionNode

Checks generated bullets for unsupported metrics or unsupported claims. It can request regeneration up to two iterations.

### FinalReportNode

Does not call the LLM. It appends the final workflow trace message.

### ApplicationAnswerNode

Drafts conservative application answer starters for the fixed Phase 2 prompts and optional user-provided application questions. It must keep visa, work authorization, sponsorship, salary, compensation, legal eligibility, and similar sensitive questions assigned to the applicant.

### InterviewCoachNode

Generates practice questions grounded in the resume, JD, and local interview bank. Deterministic fallback output includes project deep dives, project follow-ups, role-specific technical questions, and required-skill evidence questions.

## Streamlit UI

Main file:

- `app.py`

Tabs:

- Input.
- Match Report.
- Resume Tips.
- Application & Interview.
- Workflow Trace.
- Run History.

Sidebar:

- DeepSeek API key status.
- Model input.
- Base URL display.
- Sample JD selector.
- Sample data loader.

## Evaluation

Main files:

- `src/services/evaluation.py`
- `eval/run_eval.py`
- `eval/evaluation_cases.json`

MVP metrics:

- Keyword Coverage Before.
- Keyword Coverage After.
- Keyword Coverage Delta.
- Required Skills Match Rate.
- Missing Skills Count.
- Bullet Count Generated.
- Reflection Revision Rate.
- STAR Coverage Rate.
- Application Answer Count.
- Custom Application Answer Count.
- Sensitive Application Refusal Count.
- Application Answer Evidence Rate.
- Interview Question Count.
- Interview Prep Notes Rate.
- Interview Project Follow-up Count.
- Interview Role-specific Count.
- Interview Required Skill Evidence Count.

Current output:

- `outputs/evaluation_results.csv`
- `outputs/evaluation_comparison_summary.csv`

## Current Implementation Status

Completed in source code:

- Project plan and consolidated documentation.
- Pydantic schemas.
- LangGraph state.
- DeepSeek-compatible provider configuration.
- LLM client wrapper.
- Deterministic fallback agents.
- Workflow graph and fallback runner.
- RAG markdown fallback and optional ChromaDB path.
- ChromaDB integration through `langchain-chroma`.
- Parallel Phase 2 application answer and interview prep execution with a final-report join.
- Sample data.
- Knowledge base markdown files.
- TXT/PDF/DOCX parser modules.
- Streamlit UI source.
- Cache.
- Evaluation script.
- Conservative application answer starters and interview practice questions for normal-match workflows.
- Optional custom application questions with sensitive-question refusal.
- Role-specific deterministic interview questions and project follow-ups.
- Expanded evaluation metrics for keyword coverage delta, application answer evidence coverage, sensitive-question refusal count, and interview prep coverage.
- Full comparison evaluation across Baseline, LLM-only, and CareerPilot Full, with method-level summary output.
- Local Python 3.12 `.venv` with Streamlit, LangGraph, ChromaDB, parser, test, and evaluation dependencies installed.
- DeepSeek V4 thinking-mode configuration through `.env`.
- Streamlit sidebar controls for DeepSeek thinking mode and reasoning effort.
- SQLite-backed run history summaries that do not persist raw resumes or raw job descriptions.
- Structured-output normalization for common real DeepSeek schema drift.
- Cache key versioning to prevent stale pre-fix workflow states from reappearing in the UI.
- README.
- Basic tests.

Verified:

- Main modules compile.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed with 26 tests.
- `python eval/run_eval.py` generated `outputs/evaluation_results.csv` and `outputs/evaluation_comparison_summary.csv` with MVP, Phase 2, and comparison metrics.
- Streamlit 1.58.0 is installed and `streamlit run app.py --server.port 8501 --server.headless true` returned HTTP 200.
- Direct DeepSeek API smoke test succeeded with `deepseek-v4-pro`, thinking enabled, `reasoning_effort=high`, and returned `reasoning_content`.
- Full DeepSeek-backed sample workflow succeeded with default `deepseek-v4-pro`, thinking disabled, low effort configuration and `errors=0`.
- ChromaDB vectorstore files exist under `data/vectorstore/`.
- `get_or_build_vectorstore()` returned a `Chroma` object with the standalone `langchain-chroma` integration.

Not yet fully verified:

- DeepSeek thinking enabled with high reasoning effort is verified for a direct smoke test, but full multi-node workflow is slow and should be used selectively.
- README screenshots were captured on 2026-06-12 with local Chrome headless and stored under `docs/assets/`.

## Near-Term Priorities

1. Improve Streamlit polish based on manual UI testing.
2. Optionally add a short demo GIF.

## Manual UI Verification

Recommended local demo settings:

- `Thinking Mode`: `disabled`
- `Reasoning Effort`: `low`

User checklist:

- Click `Load Sample Data`.
- Click `Run CareerPilot Analysis`.
- Review Input, Match Report, Resume Tips, Application & Interview, and Workflow Trace.
- Check that generated text does not invent resume facts, unsupported metrics, visa status, work authorization, sponsorship details, or compensation expectations.
- If the trace shows `Fallback scoring completed` after recent code changes, rerun the analysis. The app now versions cache keys so old pre-fix cached states are not reused.

## Known Technical Debt

- DeepSeek thinking mode with high reasoning effort is verified only for a direct smoke test; full multi-node workflow use should remain selective because it is slow.

## Safety And Privacy

- API keys are loaded from environment variables only.
- `.env` is ignored by git.
- Uploaded files are processed in memory.
- Run history stores local summary metadata only and does not persist raw resumes or raw job descriptions.
- Generated content includes a review warning.
- Visa, authorization, and compensation questions must be answered by the user.
