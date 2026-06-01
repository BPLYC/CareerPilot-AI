# Agent Guide For CareerPilot AI

This file is for future coding agents working in this repository. Read it before changing code.

## Project Summary

CareerPilot AI is a local Streamlit app for resume and job-description matching. It uses a LangGraph workflow with conditional routing, a reflection loop, and local RAG knowledge to help students prepare internship applications.

Read these files first:

- `docs/PROJECT_SPEC.md`: full consolidated product and implementation spec.
- `docs/IMPLEMENTATION_PLAN.md`: current status, near-term plan, and progress tracking.
- `README.md`: user-facing setup and run instructions.

## Current Status

The MVP source code scaffold is implemented. It has not yet been fully verified with Streamlit, real DeepSeek API calls, or ChromaDB persistence in the current local environment.

Verified so far:

- Main modules compile.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` passed with 7 tests.
- `python eval/run_eval.py` generated `outputs/evaluation_results.csv`.

Known environment limitation:

- Current Python observed during development was 3.9.7.
- `streamlit` was not installed.
- `pip install -r requirements.txt` was blocked or timed out.
- `chromadb` was not installed.

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

## Repository Structure

```text
D:\CareerPilot_AI
├── AGENTS.md
├── README.md
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   ├── sample_resume.txt
│   ├── sample_jd_ai_intern.txt
│   ├── sample_jd_data_analyst.txt
│   ├── sample_jd_swe_intern.txt
│   └── knowledge_base/
│       ├── resume_bullet_templates.md
│       ├── star_method_examples.md
│       ├── ai_ds_swe_internship_skill_taxonomy.md
│       ├── application_question_examples.md
│       └── interview_question_bank.md
├── docs/
│   ├── PROJECT_SPEC.md
│   └── IMPLEMENTATION_PLAN.md
├── eval/
│   ├── evaluation_cases.json
│   └── run_eval.py
├── outputs/
│   ├── .gitkeep
│   └── evaluation_results.csv
├── src/
│   ├── agents/
│   │   ├── common.py
│   │   ├── resume_parser_agent.py
│   │   ├── jd_analyzer_agent.py
│   │   ├── rag_retriever_agent.py
│   │   ├── match_scoring_agent.py
│   │   ├── low_match_warning_agent.py
│   │   ├── resume_optimizer_agent.py
│   │   ├── reflection_agent.py
│   │   └── final_report_agent.py
│   ├── models/
│   │   └── schemas.py
│   ├── parsers/
│   │   ├── file_parser.py
│   │   ├── pdf_parser.py
│   │   └── docx_parser.py
│   ├── rag/
│   │   ├── knowledge_loader.py
│   │   ├── build_vectorstore.py
│   │   └── retriever.py
│   ├── services/
│   │   ├── cache.py
│   │   ├── evaluation.py
│   │   ├── llm_client.py
│   │   ├── prompts.py
│   │   ├── provider_config.py
│   │   ├── scoring.py
│   │   └── structured_output.py
│   ├── utils/
│   │   └── text_utils.py
│   └── workflow/
│       ├── careerpilot_graph.py
│       └── state.py
└── tests/
    ├── test_schemas_state.py
    ├── test_scoring.py
    └── test_workflow.py
```

## Important Entry Points

- UI: `app.py`
- Workflow: `src/workflow/careerpilot_graph.py`
- State: `src/workflow/state.py`
- Schemas: `src/models/schemas.py`
- Provider config: `src/services/provider_config.py`
- LLM client: `src/services/llm_client.py`
- Prompts: `src/services/prompts.py`
- RAG retrieval: `src/rag/retriever.py`
- Evaluation: `eval/run_eval.py`

## Commands

Run tests in this environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -q
```

Run evaluation:

```powershell
python eval\run_eval.py
```

Run the app after dependencies are installed:

```powershell
streamlit run app.py
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=your_selected_model
EMBEDDING_PROVIDER=local_hash
```

## Near-Term Next Work

1. Install dependencies in a clean Python 3.11+ environment.
2. Verify `streamlit run app.py`.
3. Configure DeepSeek and run one real API-backed sample analysis.
4. Verify optional ChromaDB vectorstore build.
5. Improve evaluation metrics after UI and real LLM runs.
6. Add screenshots or GIF for README.
7. Then begin Phase 2 nodes.

