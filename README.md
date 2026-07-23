# CareerPilot AI

> A LangGraph-based Multi-Agent RAG System for Resume-JD Matching and Internship Application Preparation.

## What Makes This Different from a Prompt Wrapper

CareerPilot AI uses a real workflow rather than one long prompt:

- Conditional routing sends low-fit jobs to a warning path and skips resume optimization.
- A reflection node checks generated bullets for unsupported claims and can loop back to the optimizer.
- A local RAG knowledge base supplies resume bullet templates, STAR examples, and skill taxonomy snippets, chunked per section so an AI role and a backend role retrieve different material.
- Evaluation metrics make the output measurable.

## Problem Statement

Students applying for AI, data, and software internships need help understanding how well their resume fits a JD and how to rewrite existing experience without fabricating claims.

## Key Features

- Resume parsing from pasted text, TXT, PDF, and DOCX.
- JD analysis for required skills, preferred skills, responsibilities, and keywords.
- Match scoring with low-match branching.
- Resume bullet suggestions grounded in the existing resume.
- Reflection review for factual consistency.
- Conservative application answer starters, optional application questions, and interview practice questions.
- Parallel execution where the workflow allows it: resume parsing and JD analysis at intake, application answers and interview coaching after reflection.
- Compare one resume against several job descriptions at once, ranked by fit, with the skills missing from every role.
- Export the full report as Markdown.
- Local Streamlit UI, workflow trace, and SQLite-backed run history summaries.
- Comparison evaluation across Baseline, LLM-only, and CareerPilot Full methods.

## Tech Stack

- Python 3.11+ recommended
- Streamlit
- LangGraph
- Pydantic
- DeepSeek OpenAI-compatible API
- ChromaDB optional local vector store through `langchain-chroma`, used when `EMBEDDING_PROVIDER=openai` supplies real embeddings; with the default hash embeddings the deterministic term-overlap retriever ranks better and is used instead

## Architecture Diagram

```mermaid
flowchart TD
    S["Start"] --> A["Resume Parser"]
    S --> B["JD Analyzer"]
    A --> C["RAG Retriever"]
    B --> C
    C --> D["Match Scoring"]
    D -->|"score < 45"| E["Low Match Warning"]
    D -->|"score >= 45"| F["Resume Optimizer"]
    F --> G["Reflection"]
    G -->|"issues and iteration < 2"| F
    G -->|"passed or max iterations"| H["Phase 2 Parallel Prep"]
    H --> I["Application Answers"]
    H --> J["Interview Coach"]
    I --> K["Final Report"]
    J --> K
    E --> K
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
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=low
EMBEDDING_PROVIDER=local_hash
DEEPSEEK_REQUEST_TIMEOUT=60
DEEPSEEK_MAX_RETRIES=2
```

`DEEPSEEK_REQUEST_TIMEOUT` and `DEEPSEEK_MAX_RETRIES` are optional. Raise the timeout when using thinking mode with high reasoning effort, which is considerably slower than the defaults.

The project can still run deterministic fallback logic without an API key. For deeper but slower analysis, switch `DEEPSEEK_THINKING=enabled` and choose `DEEPSEEK_REASONING_EFFORT=low`, `medium`, or `high`.
The Streamlit sidebar also exposes thinking mode and reasoning effort controls for local demos.

## How To Run

```powershell
streamlit run app.py
```

For the local project virtual environment:

```powershell
cd D:\CareerPilot_AI
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

Open `http://localhost:8501`, click `Load Sample Data`, optionally add application questions, then click `Run CareerPilot Analysis`. For the fastest demo, keep `Thinking Mode` set to `disabled` and `Reasoning Effort` set to `low`.
If an old result still shows fallback traces, rerun the analysis; the app now versions cache keys so pre-fix cached workflow states are not reused.

If the browser says the site refused to connect, restart Streamlit and try `http://127.0.0.1:8501`:

```powershell
cd D:\CareerPilot_AI
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## Demo Screenshots

Input screen with the provider settings and all seven tabs:

![CareerPilot AI input screen](docs/assets/careerpilot-home.png)

Sample resume and AI Intern job description loaded through the sidebar:

![CareerPilot AI sample data loaded](docs/assets/careerpilot-sample-input.png)

Match report, with the Markdown export button:

![CareerPilot AI match report](docs/assets/careerpilot-match-report.png)

One resume compared against three roles, ranked by fit:

![CareerPilot AI job comparison](docs/assets/careerpilot-compare-jobs.png)

These are captured on the deterministic path, so anyone can regenerate the identical images and no API credit is spent. That is why the sidebar shows the fallback notice rather than a configured key.

```powershell
node tools\capture_streamlit_screenshot.mjs
```

Add `--live` to capture real model output instead. Note that the live match score is not stable: the sample resume and AI Intern JD have scored anywhere from 3 to 65 across runs, so a live capture freezes one draw from that spread.

## Tests And Linting

```powershell
python -m pytest -q
ruff check .
```

Tests run against the deterministic fallback path and never require an API key. GitHub Actions runs both on Python 3.11 and 3.12.

## Evaluation

```powershell
python eval/run_eval.py
```

Evaluation runs deterministically by default: it clears the DeepSeek credentials and forces markdown retrieval, so repeated runs produce byte-identical CSVs and cost nothing. Pass `--live` to call the real model instead, which costs money and returns different numbers each run.

```powershell
python eval/run_eval.py --live
```

The script writes `outputs/evaluation_results.csv` with one row per case and method, plus `outputs/evaluation_comparison_summary.csv` with method-level averages. Metrics include keyword coverage before and after generated bullets, required skill match rate, reflection revision rate, STAR-ready bullet coverage, application answer evidence coverage, sensitive-question refusal count, interview prep-notes coverage, project follow-up count, role-specific question count, required-skill evidence question count, RAG snippet count, workflow trace count, reflection review count, and Phase 2 parallel execution count.

## Safety And Privacy

- This tool assists but never automates job applications.
- Uploaded files are processed in memory and are not saved.
- Run history stores summary metadata only; raw resumes and job descriptions are not persisted.
- API keys are loaded from `.env`.
- AI-generated content must be reviewed and personalized before submitting.
- Visa, work authorization, sponsorship, salary, legal eligibility, and compensation answers must be filled by the user.

## Limitations

- The LLM scores lower than the deterministic scorer, consistently. Measured over four runs per role on the bundled samples: AI Intern 40-55 against 68, Data Analyst 60-65 against 79, SWE Intern 50 every time against 72. Run-to-run variation is small (0-15 points); the gap between the two scorers is the systematic part. Read the score as a rough signal and rely on the matched and missing skills, which are stable.
- Fallback parsing is simple and intended for offline demos.
- RAG uses deterministic local retrieval unless optional vector-store dependencies are installed.
- Model quality depends on the configured DeepSeek model.

## Future Work

- Refresh the README screenshots, which predate the Compare Jobs tab and the report export button.
- Optional demo GIF.
- Synonym-aware retrieval needs a real embedding model. DeepSeek exposes no embeddings endpoint, so this requires either an OpenAI key (`EMBEDDING_PROVIDER=openai`, which enables the Chroma path automatically) or a local sentence-transformer.

## Resume Bullet For This Project

Built CareerPilot AI, a LangGraph-based multi-agent system with conditional routing, a reflection loop for factual resume optimization, local RAG knowledge retrieval, parallel application/interview preparation, and evaluation metrics, delivered as a Streamlit application.
