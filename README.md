[🇺🇸 English](README.md) | [🇪🇸 Español](README.es.md)

# 🚀 Autonomous Multimodal RAG Agent & Knowledge Engine

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-GenAI_SDK-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Langfuse](https://img.shields.io/badge/Langfuse-Observability-000000?style=for-the-badge&logo=langfuse&logoColor=white)](https://langfuse.com/)
[![Docker](https://img.shields.io/badge/Docker_Compose-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![CI](https://github.com/MattMattia/multimodal-rag-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MattMattia/multimodal-rag-agent/actions/workflows/ci.yml)

**Built by [Mattia Risso](https://github.com/MattMattia)**  
🔗 **Repository:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)

</div>

---

## 📌 1. Executive Overview

An end-to-end enterprise AI system that combines a **Multimodal Ingestion and Extraction** pipeline, **Advanced Hybrid Search (Dense Vector + Full-Text Search)**, **LLM-based Semantic Reranking**, and an **Autonomous ReAct AI Agent** with a dynamic tool catalog (Function Calling), persistent conversational memory, and **Enterprise-Grade Observability with Langfuse**.

The system processes complex, unstructured documents (PDFs with heterogeneous layouts, formatted tables, technical diagrams, and receipts/invoices), vectorizes the knowledge while preserving its contextual hierarchy through **Parent-Child Chunking**, and enables autonomous decision-making through multi-step reasoning, dynamic generation of executive PDF reports, event dispatch via webhooks, and real-time monitoring of tokens and latencies.

**You can try it in three modes** (see the [download and usage guide](#-4-download-and-usage-guide)): a cloud demo with nothing to install, a local Python-only run (SQLite, no Docker), and the full stack with Docker Compose (PostgreSQL + pgvector, Langfuse, Streamlit, and Next.js).

---

## 🏗️ 2. System Architecture

```mermaid
flowchart TB
    subgraph UI ["Presentation Layer"]
        Streamlit["🖥️ Streamlit Dashboard (:8501)\n• Multi-Turn Chat & SSE Streaming\n• Multimodal Drag & Drop\n• Binary Report Download"]
        NextJS["🌐 Next.js 15 BFF (web/, :3001)\n• /api/* proxy to FastAPI\n• Offline showcase with Golden Corpus"]
    end

    subgraph Gateway ["Application Layer (FastAPI Backend :8000)"]
        API["⚡ FastAPI API Gateway\n• REST Endpoints (/v1) & SSE Stream\n• Background Tasks Ingestion\n• Telemetry & Exception Handling"]
        Repo["📦 Repository Layer (Clean Architecture)\n• DocumentRepo • ChatRepo"]
    end

    subgraph Observability ["Observability & Telemetry (:3000)"]
        Langfuse["📊 Langfuse Dashboard\n• Traces & Turn Spans\n• RRF & Reranker Latencies\n• Token Cost & Usage Metrics"]
    end

    subgraph AgentEngine ["Autonomous Agent Core (ReAct)"]
        Agent["🧠 Autonomous Agent Service\n• Gemini model cascade\n• Thought-Action-Observation Loop\n• Citations Extractor & Validator"]
        
        subgraph ToolsCatalog ["Tool Catalog (Function Calling)"]
            T1["🔍 search_knowledge_base\n(Hybrid RAG + Reranking)"]
            T2["📄 generate_report_pdf\n(ReportLab Dynamic Engine)"]
            T3["🔔 dispatch_webhook\n(HTTPX Async Dispatcher)"]
        end
    end

    subgraph MultimodalPipeline ["Hierarchical Ingestion Pipeline"]
        PDFParser["📑 PDF Plumber & Fitz\n• Text Extraction\n• Table-to-Markdown"]
        Vision["👁️ Vision Service\n• Gemini Multimodal Image OCR\n• Technical Diagram Synthesis"]
        Chunker["🧩 Hierarchical Chunker\n• Parent Chunks (1200 chars, overlap 120)\n• Child Chunks (350 chars, overlap 40)"]
        Embedder["📐 Embedding Service\n• Google gemini-embedding-001 (768d)\n• Leaf chunks only"]
    end

    subgraph DataStore ["Persistence Layer (PostgreSQL 16 + pgvector :5432 · or SQLite zero-Docker)"]
        PGVector["🗄️ Vector Store\n• HNSW Cosine Index (document_chunks.embedding)\n• GIN Full-Text Search Index (Spanish & English tsvector)"]
        Relational["💾 Relational Tables\n• documents • chat_messages (JSONB) • langfuse_db"]
    end

    Streamlit <-->|HTTP REST & SSE Stream| API
    NextJS -->|BFF: HTTP & SSE| API
    API --> Repo
    API --> Agent
    API --> MultimodalPipeline
    API -.->|Traces & Spans| Langfuse
    
    MultimodalPipeline --> PDFParser
    MultimodalPipeline --> Vision
    MultimodalPipeline --> Chunker
    Chunker --> Embedder
    Embedder -->|Batch Insert + Vectors| PGVector

    Agent <-->|Dynamic Invocation| ToolsCatalog
    T1 <-->|RRF + Semantic Rerank| PGVector
    T2 -->|File Storage| DiskReports["📂 uploads/reports/*.pdf"]
    T3 -->|POST Event Payload| WebhookTarget["🌐 External Services / Slack"]

    Agent <-->|History & Session| Relational
    Langfuse -->|Metrics Persistence| Relational
```

---

## ⚙️ 3. Key Engineering Decisions

### 1. Hierarchical Parent-Child Chunking
* **Challenge:** Small chunks maximize semantic precision in vector retrieval, but lose the global context the LLM needs to produce coherent answers.
* **Solution:** A two-level strategy:
  * **Child Chunks (350 characters, 40 overlap):** Used as granular search vectors. Only leaf chunks are embedded; a parent that has children carries no vector.
  * **Parent Chunks (1200 characters, 120 overlap):** Each child chunk stores a `parent_id` pointer. When a relevant child is retrieved, the system automatically expands the text to its parent before synthesizing the final answer.
  * Tables are stored as Markdown parent chunks, and diagram descriptions (Gemini Vision) go through the same chunker.

### 2. Unified Hybrid Search with Reciprocal Rank Fusion (RRF)
* **Challenge:** Pure vector search fails on queries with serial numbers, specific technical acronyms, or tax identifiers; lexical search (BM25) ignores semantics.
* **Solution:** Bilingual fusion with two paths depending on the database engine:
  * **PostgreSQL (Enterprise mode):** pgvector cosine distance over 768-dimensional embeddings with an **HNSW** index (`m = 16`, `ef_construction = 64`, `vector_cosine_ops`), plus full-text search with **Spanish and English** dictionaries over **GIN** indexes (`to_tsvector`).
  * **SQLite (Zero-Docker mode):** exact cosine in Python and BM25 (`k1 = 1.5`, `b = 0.75`) with bilingual tokenization. With no vector index or FTS, each query scans every chunk: O(N) cost.
  * **Candidates per path:** `min(top_k × SEARCH_CANDIDATE_MULTIPLIER, 80)`; with the defaults and `top_k = 5`, that is 20 per path.
  * **RRF ($k = 60$):** An unsupervised normalization algorithm that merges the rankings without manual weight calibration:
    $$\text{Score}_{RRF}(d) = \sum_{m \in \{\text{vector}, \text{lexical}\}} \frac{1}{k + \text{rank}_m(d)}$$

### 3. Persistent Conversational Memory in the Database
* **Challenge:** Losing context in multi-turn chats without flooding the LLM context window with redundant tool calls.
* **Solution:** A relational `ChatMessage` model with structured `JSONB` (PostgreSQL) or JSON (SQLite) storage for `citations` and `executed_tools`. In follow-up turns (e.g. *"translate it into English"* or *"summarize the above"*), the agent reads the session memory and resolves the instruction without triggering redundant RAG queries.

### 4. Resilience Cascade and Automatic Model Promotion
* **Challenge:** Quota changes, latency spikes, and model deprecations in the Google API (`404 NOT_FOUND` or `429 RESOURCE_EXHAUSTED` errors).
* **Solution:** A transparent cascade module (`_call_gemini_with_fallback`):
  * Tries the configured model first (`GEMINI_AGENT_MODEL`).
  * When the API reports it as unavailable (`404`, `429`, `503`, `NOT_FOUND`, `RESOURCE_EXHAUSTED`), it promotes the call to `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-2.5-flash`, and `gemini-2.5-pro`, in that order.
  * It remembers the working model for the rest of the session; if every model fails, it logs the failure with `logger.error` and the agent answers with its deterministic fallback mode.

### 5. Dynamic PDF Reports with ReportLab
* **Challenge:** Generating reports without fixed, static templates.
* **Solution:** The `generate_report_pdf` tool receives dynamic arguments written by the LLM after analyzing the corpus: a contextual title, a structured executive summary, and concrete action items, and delivers the file ready for direct download.

### 6. Real-Time Streaming (SSE) in FastAPI and Streamlit
* **Challenge:** Perceived latency in complex generative answers that invoke several tools.
* **Solution:** The `POST /api/v1/agent/chat/stream` endpoint emits structured Server-Sent Events (`token` and `metadata`), consumed progressively by Streamlit with `st.write_stream` for a smooth interactive experience.

### 7. Semantic Reranking After RRF
* **Challenge:** Although RRF balances dense and sparse signals well, chunks that contain the keywords but do not semantically answer the user's intent can still rank high in the initial list.
* **Solution:** `RerankerService` adds a semantic scoring stage after RRF:
  * Retrieves an extended candidate window (`top_k * 3`).
  * Scores each chunk's semantic relevance (0.0 to 1.0) with Gemini, assigning `rerank_score`.
  * Narrows the selection to the best `top_k` and expands context to the parent chunk (`Parent-Document Retrieval`).
  * **Deterministic fallback:** On timeouts (`RERANK_TIMEOUT_SECONDS`), errors, or a missing Gemini client, it transparently keeps the original RRF order. In that case `rerank_score` repeats the RRF score; it orders results but does not measure relevance.

### 8. LLM Observability and Telemetry with Langfuse
* **Challenge:** Monitoring the autonomous behavior of the ReAct agent in production: auditing which tools it runs, which chunks it retrieves, each stage's latency, and the exact token and cost consumption, without hurting performance or blocking the user.
* **Solution:** A decoupled `TelemetryService` module (`app/core/telemetry.py`):
  * **Self-hosted container:** The Langfuse web service ships in `docker-compose.yml` (`:3000`) with PostgreSQL persistence (`langfuse_db`).
  * **Turn tracing:** Every user query creates a root `Trace` tied to the `session_id`.
  * **Execution spans:** Automatic contextual instrumentation of the tools (`search_knowledge_base`, `generate_report_pdf`, `dispatch_webhook`), the RRF vector search, and the semantic reranking stage.
  * **Generation metrics:** Fine-grained logging of the Gemini models invoked, prompts processed, input/output tokens, and latency in seconds.
  * **Full resilience (No-Op Fallback):** If Langfuse is disabled (`LANGFUSE_ENABLED=false`) or the server is temporarily unreachable, `DummyTrace` and `DummySpan` guarantee 0 ms overhead and never raise exceptions to the client.

### 9. Architecture Decision Records (ADR)

Each major decision has a record with its context, rejected alternatives, and known limitations:

| ADR | Decision | What it solves |
|-----|----------|----------------|
| [ADR 001](docs/adr/001-hierarchical-parent-child-chunking.md) | Hierarchical parent-child chunking | Vector precision without losing context; only leaves are embedded |
| [ADR 002](docs/adr/002-hybrid-rrf-and-semantic-reranking.md) | Hybrid search with RRF and semantic reranking | Exact identifiers and paraphrases; deterministic reranker fallback |
| [ADR 003](docs/adr/003-tri-modal-zero-dependency-architecture.md) | Tri-modal architecture with SQLite fallback | Runs without Docker, and the full stack runs with one command |
| [ADR 004](docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md) | Next.js BFF with a serverless showcase | Always-on demo without exposing the backend key |

---

## 🚀 4. Download and Usage Guide

### 4.1 Pick a mode

| Mode | How to start | Where to look | Data |
|------|--------------|---------------|------|
| **1. Cloud Showcase** (Vercel) | Import the repository into Vercel with **Root Directory = `web`** | Deployment URL | Golden Corpus embedded in the BFF, or the live backend when `FASTAPI_URL` responds |
| **2. Zero-Docker** (Python only) | `python run.py` | API at [http://localhost:8000/docs](http://localhost:8000/docs) | SQLite (`rag_standalone.db`) with the Golden Corpus seeded automatically |
| **3. Full Enterprise** (Docker Compose) | `docker compose up -d --build` | Streamlit :8501, API :8000, Next.js :3001, Langfuse :3000 | PostgreSQL 16 + pgvector |
| **3b. GitHub Codespaces** | *Code → Codespaces → Create codespace* | Forwarded ports 8000, 8501, and 3001 | SQLite inside the dev container |

> Modes 2 and 3 run the same code. The database is chosen at startup: if PostgreSQL does not respond and `AUTO_FALLBACK_SQLITE=true` (the default), the API carries on with SQLite. See [ADR 003](docs/adr/003-tri-modal-zero-dependency-architecture.md).

### 4.2 Prerequisites

| Tool | Mode 1 (Vercel) | Mode 2 (Zero-Docker) | Mode 3 (Docker) | Codespaces |
|---|---|---|---|---|
| [Git](https://git-scm.com/) (or ZIP download) | Only to fork | ✅ | ✅ | — |
| [Python 3.11+](https://www.python.org/downloads/) | — | ✅ | — (inside the image) | — (inside the container) |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | — | — | ✅ (running) | — |
| [Node.js](https://nodejs.org/) 20.9+ (CI uses 24) | Only for local web development | Only if you want the local web app | — (inside the image) | — (inside the container) |
| [GitHub](https://github.com/) account | To import into Vercel | — | — | ✅ |
| [Vercel](https://vercel.com/) account | ✅ | — | — | — |

### 4.3 Google Gemini key (optional)

Get a free `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/) (*Get API key*). **It is optional:** without it everything starts and works, but in degraded mode:

| Feature | With `GOOGLE_API_KEY` | Without a key |
|---|---|---|
| Embeddings | `gemini-embedding-001` (768 dimensions) | Deterministic mock vectors (SHA-256): dense search is not semantic |
| Lexical search (BM25 / full-text) | Same | Same: it is the only retrieval path with real meaning |
| Reranker | Gemini scores each chunk | Fallback: keeps the RRF order |
| Agent | ReAct reasoning with Gemini and Function Calling | Deterministic offline fallback agent |
| Descriptions of uploaded images and diagrams | Gemini Vision | Not available |
| Benchmark | `embedding_mode: "gemini"` | `embedding_mode: "mock"`; dense and hybrid flagged as non-semantic |

### 4.4 Download the project

```bash
git clone https://github.com/MattMattia/multimodal-rag-agent.git
cd multimodal-rag-agent
```

No Git? On the repository page, choose **Code → Download ZIP**, extract it, and open a terminal in the folder.

Create your environment file from the template. The backend reads `.env` (plus system environment variables); `.env` is listed in `.gitignore`.

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Minimal variables per mode:

| Mode | Variables | Where |
|---|---|---|
| 1. Cloud Showcase | None required. Optional: `FASTAPI_URL`, `API_KEY`, `FASTAPI_TIMEOUT_MS` | Vercel project environment variables |
| 2. Zero-Docker | None required. Optional: `GOOGLE_API_KEY`; `DATABASE_URL=sqlite+aiosqlite:///./rag_standalone.db` to skip the PostgreSQL attempt | `.env` |
| 3. Full Enterprise | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (Compose interpolates them). Optional: `GOOGLE_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `API_KEY` | `.env` (must exist: Compose mounts it into the `api` container) |

Example for mode 3:

```ini
GOOGLE_API_KEY=            # optional
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=rag_multimodal

# Observability (optional)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=

# Security (optional)
API_KEY=                   # when set, /api/v1/* and /uploads/reports/* require the X-API-Key header
```

The full table is in [Environment variables](#environment-variables).

### 4.5 Mode 1: Cloud Showcase on Vercel

1. In Vercel: **Add New → Project** and import the repository (or your fork) from GitHub.
2. Set **Root Directory = `web`**. Vercel detects the **Next.js** framework.
3. Environment variables (optional, server-only; never `NEXT_PUBLIC_*`):
   * `FASTAPI_URL`: public URL of a deployed FastAPI backend.
   * `API_KEY`: sent to the backend as `X-API-Key`; it never reaches the browser.
4. **Deploy** and open the URL.

How it behaves:

* **⚡ Vercel Serverless 24/7 Showcase Engine:** with no `FASTAPI_URL`, or when the backend is unreachable (network error, header timeout `FASTAPI_TIMEOUT_MS`, 3 s by default, or a 502/504 response), the BFF answers with the built-in showcase engine and the embedded Golden Corpus.
* **🟢 Live FastAPI + pgvector Cluster:** with a reachable backend, the BFF forwards requests to FastAPI. The `x-rag-source` header tells you who answered.
* The showcase is **stateless**: document uploads only work against a live backend.

See [ADR 004](docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md).

**Run the web app locally:**

```bash
cd web
npm install
npm run dev        # http://localhost:3001
```

To connect it to a local backend, set `FASTAPI_URL=http://localhost:8000` in `web/.env.local` (or in your shell) before `npm run dev`.

> **Windows and paths containing `&`:** npm's `.cmd` shims break when the folder path contains `&`. The scripts in `web/package.json` call `node node_modules/...` directly, so `npm run dev`, `npm run build`, and `npm test` work; `npx` may not. The folder created by `git clone` (`multimodal-rag-agent`) does not have this problem.

### 4.6 Mode 2: Zero-Docker (Python + SQLite)

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   | Shell | Activation |
   |---|---|
   | Windows PowerShell | `.venv\Scripts\Activate.ps1` |
   | Git Bash (Windows) | `source .venv/Scripts/activate` |
   | macOS / Linux | `source .venv/bin/activate` |

   With [uv](https://docs.astral.sh/uv/): `uv venv --python 3.11`, activate it the same way, and use `uv pip install` in step 2.

2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   pip install -r frontend/requirements.txt   # only if you will use Streamlit
   ```

3. Start the API:

   ```bash
   python run.py                       # 127.0.0.1:8000
   python run.py --host 0.0.0.0 --port 8080   # optional: another interface or port
   ```

   Once ready, the console prints a banner like this:

   ```
     Ready  (database: SQLite Zero-Docker, Golden Corpus auto-seeded)
     API        http://localhost:8000
     Swagger    http://localhost:8000/docs
     OpenAPI    http://localhost:8000/openapi.json
     Streamlit  streamlit run frontend/app.py   (http://localhost:8501)
     Web        cd web && npm run dev            (http://localhost:3001)
   ```

   * By default `DATABASE_URL` points to PostgreSQL; if it does not respond, the API uses `sqlite+aiosqlite:///./rag_standalone.db` (the `rag_standalone.db` file in the repository root). To skip the attempt, set that `DATABASE_URL` in `.env`.
   * If the `documents` table is empty, the Golden Corpus (3 PDFs + 3 locally generated PNGs) is seeded automatically (`AUTO_SEED_DEMO_CORPUS=true`).
   * Search: exact cosine in Python and BM25, with no pgvector.

4. Optional interfaces, each in its own terminal:

   ```bash
   streamlit run frontend/app.py          # http://localhost:8501
   cd web && npm install && npm run dev   # http://localhost:3001, with FASTAPI_URL=http://localhost:8000
   ```

5. Export the OpenAPI contract without starting the server: `python run.py --export-openapi` (writes `docs/openapi.json`).

### 4.7 Mode 3: Full Enterprise (Docker Compose)

1. With Docker Desktop running and `.env` created (see [4.4](#44-download-the-project)):

   ```bash
   docker compose up -d --build
   ```

2. Services:

   | Service | URL / port | Contents |
   |---|---|---|
   | `api` | [http://localhost:8000/docs](http://localhost:8000/docs) | FastAPI + Swagger UI (with `--reload` for development) |
   | `frontend` | [http://localhost:8501](http://localhost:8501) | Streamlit dashboard |
   | `web` | [http://localhost:3001](http://localhost:3001) | Next.js BFF + showcase (`3001` avoids clashing with Langfuse) |
   | `langfuse` | [http://localhost:3000](http://localhost:3000) | Observability dashboard |
   | `db` | `localhost:5432` (or `POSTGRES_PORT`) | PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16`) |

3. Health check: [http://localhost:8000/health](http://localhost:8000/health) and `docker compose ps`.

4. **First Langfuse run (optional):** Compose sets `LANGFUSE_ENABLED=true`, but without keys telemetry stays in no-op mode and does not affect the API. For real traces, create an account and a project at [http://localhost:3000](http://localhost:3000), copy `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` into `.env`, and recreate the API with `docker compose up -d api`.

5. Tests inside the container:

   ```bash
   docker compose exec api pytest -v
   ```

6. Stop and clean up:

   ```bash
   docker compose down        # stops the containers and keeps the data
   docker compose down -v     # ⚠️ also deletes the postgres_data volume (documents, chats, and Langfuse data)
   ```

> **Unprivileged containers:** the `api` and `frontend` images run as the non-root user `appuser` (uid 1000) and include a `HEALTHCHECK`. The base API image starts without `--reload`; `docker-compose.yml` adds it for development only.

#### GitHub Codespaces

1. On the repository: **Code → Codespaces → Create codespace** (or [https://codespaces.new/MattMattia/multimodal-rag-agent](https://codespaces.new/MattMattia/multimodal-rag-agent)).
2. The devcontainer (`.devcontainer/devcontainer.json`) uses Python 3.11 and Node 24, and on creation runs `pip install -r requirements.txt`, `pip install -r frontend/requirements.txt`, and `npm ci` in `web/`.
3. It runs in **SQLite mode** (`DATABASE_URL=sqlite+aiosqlite:///./rag_standalone.db`, no Docker Compose) and already sets `FASTAPI_URL=http://localhost:8000`.
4. Start the services in separate terminals:

   ```bash
   python run.py                    # port 8000
   streamlit run frontend/app.py    # port 8501
   cd web && npm run dev            # port 3001
   ```

5. Open the forwarded ports from the **Ports** tab. Add `GOOGLE_API_KEY` as a Codespaces secret if you want real embeddings.

### 4.8 Your first 5 minutes

1. Open the web app (your Vercel URL or [http://localhost:3001](http://localhost:3001)) and check the status badge: ⚡ showcase or 🟢 Live.
2. **📚 Knowledge Base → 🚀 Restore Golden Demo Corpus** to (re)seed the 3 demo documents.
3. **💬 Agent Studio:** click one of the quick prompts, for example *"What HNSW parameters does the vector index use (m, ef_construction)?"*, and review the citations and the tool timeline.
4. **📊 Benchmark Lab → ▶ Run live benchmark** to compare dense, sparse, and hybrid.
5. **PDF report:** click the quick prompt *"Generate a PDF report on GlobalTech's EBITDA and inference costs."*; with a live backend, the agent runs `generate_report_pdf` (📄) and returns the download link. You can also export the conversation with **⬇️ PDF** in the sessions sidebar.

### 4.9 Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `address already in use` / port taken | Another process holds the port. API: `python run.py --port 8010`. Streamlit: `streamlit run frontend/app.py --server.port 8502`. Docker: change the mapping in `docker-compose.yml`, or `POSTGRES_PORT` for the database. |
| `404` with `text-embedding-004` | That model is no longer available. The project uses `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`; fix or remove that line in an older `.env`. |
| `404 NOT_FOUND` with `gemini-1.5-*` models | Retired models. The cascade promotes to an available model, but it is better to set `GEMINI_AGENT_MODEL` and `GEMINI_VISION_MODEL` in `.env` to a current model (for example `gemini-3.8-flash`). The code and `docker-compose.yml` now default to `gemini-3.8-flash`, so this only happens with an older `.env`. |
| `Cannot connect to the Docker daemon` / `docker compose` fails | Docker Desktop is not running. Open it, wait for the engine to start, and run the command again. |
| `npx` or npm shims fail on Windows | The path contains `&`. Use `npm run dev/build/test`, or clone into a folder without `&`. |
| `LF will be replaced by CRLF` warnings | Git line-ending conversion on Windows. Harmless. |
| The web app shows ⚡ with a local backend | `FASTAPI_URL` is not set for the Next.js process, or the backend took longer than `FASTAPI_TIMEOUT_MS`. |

### Environment variables

Defaults taken from `app/core/config.py`. Variables are read from the environment or from `.env`.

| Variable | Default | Effect |
|---|---|---|
| **General** | | |
| `PROJECT_NAME` | `Sistema RAG Multimodal & Agente IA Autónomo` | Name shown by the API |
| `API_V1_STR` | `/api/v1` | Versioned API prefix |
| `ENVIRONMENT` | `development` | Environment label (returned by `/health`) |
| `DEBUG` | `true` | With `true`, exception details are shown; set `false` in production |
| **Database** | | |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/rag_multimodal` | Engine. Accepts `sqlite+aiosqlite:///./rag.db` for Zero-Docker mode |
| `AUTO_FALLBACK_SQLITE` | `true` | If PostgreSQL does not respond at startup, uses `sqlite+aiosqlite:///./rag_standalone.db` (no pgvector; exact cosine and BM25 in Python) |
| `AUTO_SEED_DEMO_CORPUS` | `true` | After `init_db()`, seeds the Golden Corpus (3 PDFs + 3 locally generated PNGs) if `documents` is empty |
| **Google / Gemini** | | |
| `GOOGLE_API_KEY` | empty | Without a key: mock embeddings (SHA-256), reranker in fallback mode, and the fallback agent |
| `GEMINI_AGENT_MODEL` | `gemini-3.8-flash` | Preferred model for the agent and the reranker; the cascade takes over if it is unavailable |
| `GEMINI_VISION_MODEL` | `gemini-3.8-flash` | Model for image and diagram descriptions |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model (the current API no longer exposes `text-embedding-004`) |
| `EMBEDDING_DIMENSION` | `768` | Dimension of the embeddings and of the `vector(N)` column. Changing it requires recreating the column |
| `EMBEDDING_BATCH_SIZE` | `50` | Texts per embedding API call |
| **Ingestion** | | |
| `PARENT_CHUNK_SIZE` / `PARENT_CHUNK_OVERLAP` | `1200` / `120` | Size and overlap of parent chunks |
| `CHILD_CHUNK_SIZE` / `CHILD_CHUNK_OVERLAP` | `350` / `40` | Size and overlap of child chunks (the embedded ones) |
| `PDF_IMAGE_DPI` | `150` | Resolution of images extracted from PDFs |
| `PDF_MIN_IMAGE_DIM` | `40` | Minimum side (pt) so icons are not treated as images |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum size per uploaded file; above it the API returns `413` and deletes the partial file |
| **Search** | | |
| `SEARCH_CANDIDATE_MULTIPLIER` | `4` | Candidates per path before fusion: `min(top_k × multiplier, 80)` |
| `RRF_K` | `60` | Reciprocal Rank Fusion smoothing constant |
| `RERANK_TIMEOUT_SECONDS` | `8.0` | Reranker time limit; beyond it the RRF fallback applies |
| `RERANK_MAX_SNIPPET_CHARS` | `800` | Characters of each chunk sent to the reranker |
| **Agent** | | |
| `AGENT_MAX_HISTORY_MESSAGES` | `20` | Previous messages sent to the LLM |
| `AGENT_MAX_TURNS` | `4` | Maximum ReAct iterations per turn |
| `AGENT_TEMPERATURE` | `0.2` | Agent temperature |
| **Observability** | | |
| `LANGFUSE_ENABLED` | `false` | Enables telemetry. `docker-compose.yml` enables it by default (`true`) |
| `LANGFUSE_HOST` | `http://langfuse:3000` | Langfuse host |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | empty | Langfuse credentials |
| **Security and access** | | |
| `API_KEY` | empty (open access) | When set, `/api/v1/*` and report downloads require `X-API-Key`. `/health` stays open |
| `ALLOWED_WEBHOOK_HOSTS` | empty | Hosts allowed for `http://` webhooks. Private IPs, loopback, and internal names are always blocked (anti-SSRF) |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8000,http://localhost:8501` | CORS origins (comma-separated). The Next.js BFF calls the backend server-side and needs no CORS |
| `ALLOWED_ORIGIN_REGEX` | empty | Optional regular expression for extra CORS origins (e.g. `https://.*\.vercel\.app`) |
| `RATE_LIMIT_ENABLED` | `true` | Per-IP request limit (in-memory sliding window, single process). Disabled under `pytest` |
| `RATE_LIMIT_PER_MINUTE` | `60` | Maximum requests per IP per minute; above it the API returns `429` with `Retry-After`. `/health` and `/api/v1/health` are exempt |

**Next.js BFF variables** (`web/`, server-only; never `NEXT_PUBLIC_*`):

| Variable | Default | Effect |
|---|---|---|
| `FASTAPI_URL` | empty | Backend base URL. Without it, the showcase answers every route |
| `API_KEY` | empty | Sent to the backend as `X-API-Key` |
| `FASTAPI_TIMEOUT_MS` | `3000` | How long to wait for backend headers before using the showcase |

**Streamlit variables** (`frontend/api_client.py`):

| Variable | Default | Effect |
|---|---|---|
| `API_URL` | `http://localhost:8000` | Backend URL as seen from the Streamlit container or process |
| `PUBLIC_API_URL` | `http://localhost:8000` | Backend URL as seen from the browser |
| `API_KEY` | empty | Key sent as `X-API-Key` |

Docker Compose variables: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` (5432), `LANGFUSE_DB`. The Langfuse secrets (`NEXTAUTH_SECRET`, `SALT`) have development defaults: set your own outside local use.

---

## 📡 5. API Endpoint Catalog

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Backend health check and database status |
| `POST` | `/api/v1/documents/upload` | PDF/image ingestion (asynchronous processing) |
| `GET` | `/api/v1/documents` | Indexed documents with status and chunk count |
| `GET` | `/api/v1/documents/{id}` | Document detail and generated chunks |
| `POST` | `/api/v1/search` | Hybrid search (`query`, `top_k`, `mode`, `filter_document_id`, `rerank`); the response includes `diagnostics` (per-stage latency: `embedding_ms`, `dense_ms`, `sparse_ms`, `rrf_fusion_ms`, `rerank_ms`, `total_ms`, candidates, and unique blocks) |
| `POST` | `/api/v1/agent/chat` | Multi-turn interaction with the autonomous ReAct agent |
| `POST` | `/api/v1/agent/chat/stream` | Real-time streamed answers (Server-Sent Events: `token`, `tool_end` with `duration_ms` and `diagnostics`, and a final `metadata` with `diagnostics` and `duration_ms`). Both chat endpoints accept `filter_document_id`, `search_mode`, `top_k`, `enable_rerank`, `temperature`, `max_turns`, and `language` (`es` \| `en` \| `auto`, default `auto`: detected from the message) |
| `GET` | `/api/v1/agent/sessions/{session_id}/history` | Persisted history of a conversation |
| `GET` | `/uploads/reports/{filename}` | Download of agent-generated PDF reports (requires `X-API-Key` when `API_KEY` is set; only serves files inside `uploads/reports/`) |
| `GET` | `/api/v1/reports/{filename}` | Agent-generated PDF report (`Content-Disposition: inline`); same containment check as the legacy route |
| `GET` | `/api/v1/documents/{id}/file` | Original uploaded file (authenticated, contained in `uploads/documents/`) |
| `GET` | `/api/v1/documents/{id}/images/{image_id}/file` | Extracted or uploaded image (`image/png`, `image/jpeg`, `image/webp`); checks that it belongs to the document |
| `GET` | `/api/v1/agent/sessions` | Chat sessions (`session_id`, `title`, `created_at`, `updated_at`, `message_count`) by `updated_at` descending |
| `DELETE` | `/api/v1/agent/sessions/{session_id}` | Deletes a session's messages (`204`, or `404` if it does not exist) |
| `GET` | `/api/v1/agent/sessions/{session_id}/export?format=markdown\|pdf&lang=es\|en` | Exports the conversation with citations and executed tools; `lang` (default `es`) localizes the labels |
| `POST` | `/api/v1/agent/feedback` | Feedback `{session_id, message_id, rating: 1\|-1, comment}`; stored in `message_metadata` and sent to Langfuse when enabled |
| `POST` | `/api/v1/demo/seed` | Idempotent re-seed of the Golden Corpus (generates any missing PDFs/PNGs; makes no Gemini calls without an API key) |
| `GET` | `/api/v1/demo/status` | `db_dialect`, `demo_seeded`, document/chunk/image totals, `gemini_configured`, `langfuse_enabled`, and `active_models` |
| `POST` | `/api/v1/demo/evaluate?lang=es\|en` | RAG evaluation of `dense` vs `sparse` vs `hybrid` (RRF + reranker); see the benchmark section |

### OpenAPI

The backend's OpenAPI 3.1 schema can be exported without starting the server:
```bash
python run.py --export-openapi   # writes docs/openapi.json
```
The versioned contract lives in [docs/openapi.json](docs/openapi.json). Swagger UI is available at `/docs` while the API runs.

### RAG Evaluation Benchmark

`POST /api/v1/demo/evaluate` (optional body `{"top_k": 5}`; `409` if the corpus is not seeded) runs **8 golden queries** against the Golden Corpus in `dense`, `sparse`, and `hybrid` modes. For each mode it returns `hit_rate_at_k`, `mrr`, `ndcg_at_k`, `avg_latency_ms`, and a per-query breakdown.

**Real results** measured on 2026-11-09 with `gemini-embedding-001` (768 dimensions, L2-normalized), the Golden Demo Corpus (3 documents), 8 golden queries (5 paraphrased or cross-lingual), the SQLite engine (exact cosine in Python + BM25), and the Gemini reranker in hybrid mode:

| Mode | Hit@1 | Hit@5 | MRR@5 | NDCG@5 | Avg latency |
|---|---|---|---|---|---|
| Dense (gemini-embedding-001) | 0.875 | 1.000 | 0.938 | 0.884 | ~460 ms |
| Sparse (BM25) | 0.750 | 0.875 | 0.813 | 0.758 | ~3 ms |
| Hybrid (RRF k=60 + Gemini reranker) | 1.000 | 1.000 | 1.000 | 1.000 | ~5.9 s |

How to read these numbers:

* **Tiny corpus:** with 3 documents, scores sit near the ceiling; they mostly show relative behavior between modes, not absolute quality.
* **Hybrid latency:** dominated by the LLM reranker call. The evaluator always reranks `hybrid` mode; in chat, turn it off with `enable_rerank=false`, and in `/api/v1/search` with `rerank: false`.
* **NDCG is recall-aware:** it penalizes relevant chunks missing from the top-k, not just the position of the first hit.
* **Run-to-run variation:** with the reranker active, results change slightly between runs.
* **Without `GOOGLE_API_KEY`:** `dense` and `hybrid` use deterministic SHA-256 vectors. The response carries `embedding_mode: "mock"`, a `warning`, and `semantic: false` for those modes; only `sparse` is meaningful.

**How to reproduce:**

1. Set `GOOGLE_API_KEY` and start the backend (mode 2 or 3).
2. Make sure the corpus is there: it seeds itself at startup, or call `POST /api/v1/demo/seed`.
3. Run `POST /api/v1/demo/evaluate` from Swagger (`/docs`) or:

   ```bash
   curl -X POST http://localhost:8000/api/v1/demo/evaluate -H "Content-Type: application/json" -d '{"top_k": 5}'
   ```

   Or open **📊 Benchmark Lab → ▶ Run live benchmark** in the web app, which renders the report and its `warnings` list whether FastAPI or the showcase answered.

---

## 🧪 6. Running the Test Suite

The system ships an automated test suite covering multimodal ingestion, hierarchical chunking, hybrid search with RRF, semantic reranking, SSE streaming, resilient telemetry, database persistence, the agent's ReAct loop, RAG evaluation, and security hardening (SSRF, uploads, authentication, rate limiting). For reference: 244 backend tests on PostgreSQL, 243 + 1 skipped on SQLite, and 47 web tests.

**Inside Docker:**
```bash
docker compose exec api pytest -v
```

**Locally against PostgreSQL** (start the `db` service with `docker compose up -d db`; the agent tests call Gemini and need `GOOGLE_API_KEY`), with the virtual environment activated:
```bash
python -m pytest -q -p no:cacheprovider
```

**Locally against SQLite** (no Docker; the whole suite runs against a temporary file):
```bash
TEST_DATABASE_URL=sqlite+aiosqlite:///./test_rag.db python -m pytest -q -p no:cacheprovider
# PowerShell: $env:TEST_DATABASE_URL="sqlite+aiosqlite:///./test_rag.db"; python -m pytest -q -p no:cacheprovider
```
Tests marked `@pytest.mark.postgres_only` (asyncpg pool introspection) are skipped in this mode.

**Next.js frontend (`web/`):**
```bash
cd web
npm install
npm test          # Vitest: BFF, showcase engine, and components
npm run build     # production build; also checks the views and the ADRs
```
The scripts in `web/package.json` call `node node_modules/...` directly, because npm's `.cmd` shims fail on paths containing `&` (like the original Windows folder of this project).

`tests/conftest.py` removes, at the end of the session, the PDFs generated in `uploads/reports/` during the tests, keeping any that already existed.

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs ruff, mypy, pytest on PostgreSQL and SQLite, a check that `docs/openapi.json` is up to date, and, in `web/`, `npm run typecheck`, `npm test`, and `npm run build`.

---

## 📂 7. Code Structure

Tree of `app/`, `frontend/`, `web/src/`, and `tests/` (without `node_modules` or `.next`):

```
├── app/
│   ├── api/v1/
│   │   ├── endpoints/
│   │   │   ├── agent.py           # Sync chat, SSE streaming, sessions, export, and feedback
│   │   │   ├── demo.py            # Golden Corpus: seed, status, and evaluate
│   │   │   ├── documents.py       # Ingestion, upload, and document queries
│   │   │   ├── files.py           # Authenticated download of files, images, and reports
│   │   │   ├── health.py          # Monitoring and readiness checks
│   │   │   └── search.py          # Hybrid vector + text search + rerank
│   │   └── router.py              # Central v1 router
│   ├── core/
│   │   ├── config.py              # Pydantic BaseSettings (environment variables)
│   │   ├── database.py            # PostgreSQL/SQLite engines, active dialect, and DDL setup
│   │   ├── rate_limit.py          # Per-IP request limit (in-memory sliding window)
│   │   ├── security.py            # Optional X-API-Key header authentication
│   │   └── telemetry.py           # Singleton Langfuse observability service
│   ├── models/                    # SQLAlchemy ORM models (JSON/JSONB, vector or JSON per dialect)
│   ├── schemas/                   # Pydantic v2 validation and serialization schemas
│   ├── services/                  # Core business logic
│   │   ├── agent.py               # ReAct agent orchestrator & Gemini cascade
│   │   ├── demo_corpus.py         # Golden Corpus definition (3 documents and their images)
│   │   ├── demo_seeder.py         # PDF/PNG generation and idempotent seeding
│   │   ├── embedding.py           # Vectorization service (gemini-embedding-001, 768d)
│   │   ├── evaluation.py          # RAGEvaluationService: 8 golden queries and IR metrics
│   │   ├── ingestion.py           # Extraction, OCR, and hierarchical chunking pipeline
│   │   ├── lexical.py             # Bilingual tokenizer and BM25 (SQLite mode)
│   │   ├── rag_search.py          # RRF hybrid search (pgvector + full-text, or Python on SQLite)
│   │   ├── reranker.py            # Gemini semantic reranking service
│   │   └── vision.py              # Visual extraction of diagrams and invoices
│   ├── tools/                     # Tools the agent can execute
│   │   ├── pdf_generator.py       # ReportLab PDF report generator
│   │   ├── rag_tool.py            # Knowledge-base search tool
│   │   └── webhook_tool.py        # Async HTTP webhook dispatcher
│   └── main.py                    # FastAPI application entry point
├── docs/
│   ├── adr/                       # Architecture Decision Records (001-004)
│   └── openapi.json               # Exported OpenAPI 3.1 contract (python run.py --export-openapi)
├── docker/
│   └── init.sql                   # PostgreSQL extensions and the langfuse database
├── frontend/                      # Streamlit dashboard (port 8501)
│   ├── app.py                     # Streamlit app entry point
│   ├── api_client.py              # HTTP client for the API
│   ├── views/                     # Chat, diagnostics, benchmark, and sidebar
│   ├── Dockerfile
│   └── requirements.txt           # Frontend dependencies
├── web/                           # Next.js 15 (Vercel Root Directory)
│   ├── src/app/                   # App Router: views (/, knowledge, benchmark, architecture) and BFF route handlers (api/*)
│   ├── src/components/            # Agent, knowledge, benchmark, architecture, and shell components
│   ├── src/content/adr/           # Copy of docs/adr/ read by the Architecture view
│   ├── src/lib/server/            # BFF: FastAPI client with fallback and validation
│   ├── src/lib/showcase/          # Serverless showcase engine (corpus, dense, BM25, RRF, agent, evaluation)
│   └── src/lib/contracts.ts       # Types shared by the BFF, FastAPI, and the UI
├── tests/                         # Test suite (PostgreSQL and SQLite)
│   ├── conftest.py                # Shared fixtures (cleanup of generated PDF reports)
│   ├── test_agent.py              # ReAct agent, Function Calling, memory, and streaming
│   ├── test_documents.py          # Multimodal extraction, tables, and chunking
│   ├── test_demo.py               # Golden Corpus: seed, status, and evaluation
│   ├── test_evaluation.py         # IR metrics and benchmark
│   ├── test_sqlite_mode.py        # Zero-Docker mode on SQLite
│   ├── test_rate_limit.py         # Per-IP request limit
│   ├── test_search.py             # Embeddings, RRF, and hybrid search
│   ├── test_security.py           # SSRF, uploads, XML escaping, X-API-Key, and 500 errors
│   └── test_telemetry.py          # DummySpan, DummyTrace, and the Langfuse client
├── .devcontainer/                 # GitHub Codespaces environment (devcontainer.json)
├── .github/workflows/ci.yml       # CI: ruff, mypy, pytest (PostgreSQL + SQLite), and npm run build
├── docker-compose.yml             # Multi-container orchestration (db, api, frontend, langfuse, and web)
├── Dockerfile                     # Backend image (non-root user + HEALTHCHECK)
├── run.py                         # Launcher: Zero-Docker startup and --export-openapi
├── pyproject.toml                 # ruff and mypy configuration
├── pytest.ini                     # pytest configuration (asyncio_mode = auto)
├── requirements.txt               # Python dependencies
├── README.md                      # English documentation
└── README.es.md                   # Spanish documentation
```

---

## 👨‍💻 Author and Contact

* **Author:** [Mattia Risso](https://github.com/MattMattia)
* **Project:** Sistema RAG Multimodal & Agente IA Autónomo
* **Repository:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)
* **License:** MIT License
