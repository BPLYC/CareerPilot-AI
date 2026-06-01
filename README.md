# CareerPilot AI

> A LangGraph-based Multi-Agent RAG System for Resume-JD Matching and Internship Application Preparation.

## What Makes This Different from a Prompt Wrapper

CareerPilot AI uses a real workflow rather than one long prompt:

- Conditional routing sends low-fit jobs to a warning path and skips resume optimization.
- A reflection node checks generated bullets for unsupported claims and can loop back to the optimizer.
- A local RAG knowledge base supplies resume bullet templates, STAR examples, and skill taxonomy snippets.
- Evaluation metrics make the output measurable.

## Problem Statement

Students applying for AI, data, and software internships need help understanding how well their resume fits a JD and how to rewrite existing experience without fabricating claims.

## Key Features

- Resume parsing from pasted text, TXT, PDF, and DOCX.
- JD analysis for required skills, preferred skills, responsibilities, and keywords.
- Match scoring with low-match branching.
- Resume bullet suggestions grounded in the existing resume.
- Reflection review for factual consistency.
- Conservative application answer starters and interview practice questions.
- Local Streamlit UI and workflow trace.

## Tech Stack

- Python 3.11+ recommended
- Streamlit
- LangGraph
- Pydantic
- DeepSeek OpenAI-compatible API
- ChromaDB optional local vector store

## Architecture Diagram

```mermaid
flowchart TD
    A["Resume Parser"] --> B["JD Analyzer"]
    B --> C["RAG Retriever"]
    C --> D["Match Scoring"]
    D -->|"score < 45"| E["Low Match Warning"]
    D -->|"score >= 45"| F["Resume Optimizer"]
    F --> G["Reflection"]
    G -->|"issues and iteration < 2"| F
    G -->|"passed or max iterations"| H["Final Report"]
    E --> H
```

## Setup Instructions

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=your_selected_model
EMBEDDING_PROVIDER=local_hash
```

The project can still run deterministic fallback logic without an API key.

## How To Run

```powershell
streamlit run app.py
```

## Evaluation

```powershell
python eval/run_eval.py
```

The script writes `outputs/evaluation_results.csv`.

## Safety And Privacy

- This tool assists but never automates job applications.
- Uploaded files are processed in memory and are not saved.
- API keys are loaded from `.env`.
- AI-generated content must be reviewed and personalized before submitting.
- Visa, work authorization, and compensation answers must be filled by the user.

## Limitations

- Fallback parsing is simple and intended for offline demos.
- RAG uses deterministic local retrieval unless optional vector-store dependencies are installed.
- Model quality depends on the configured DeepSeek model.

## Future Work

- User-selected application question drafting.
- Role-specific interview coaching expansion.
- Full baseline vs LLM-only vs CareerPilot evaluation.
- SQLite run history.
- Demo GIF and richer README screenshots.

## Resume Bullet For This Project

Built CareerPilot AI, a LangGraph-based multi-agent system with conditional routing, a reflection loop for factual resume optimization, local RAG knowledge retrieval, and evaluation metrics, delivered as a Streamlit application.
