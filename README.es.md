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

**Desarrollado por [Mattia Risso](https://github.com/MattMattia)**  
🔗 **Repositorio:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)

</div>

---

## 📌 1. Visión Ejecutiva

Sistema de Inteligencia Artificial empresarial de extremo a extremo que combina un pipeline de **Ingesta y Extracción Multimodal**, **Búsqueda Híbrida Avanzada (Dense Vector + Full-Text Search)**, **Reranking Semántico con LLM** y un **Agente IA Autónomo ReAct** con catálogo de herramientas dinámicas (Function Calling), memoria conversacional persistente y **Observabilidad de Nivel Empresarial con Langfuse**.

El sistema procesa documentos no estructurados y de alta complejidad (PDFs con maquetación heterogénea, tablas formateadas, diagramas técnicos y recibos/facturas), vectoriza el conocimiento preservando la jerarquía contextual mediante **Parent-Child Chunking**, y habilita la toma de decisiones autónoma mediante razonamiento multi-paso, generación dinámica de reportes ejecutivos en PDF, despacho de eventos vía webhooks y monitoreo en tiempo real de tokens y latencias.

**Puedes probarlo en tres modos** (ver la [guía de descarga y uso](#-4-guía-de-descarga-y-uso)): demo en la nube sin instalar nada, ejecución local solo con Python (SQLite, sin Docker) y el stack completo con Docker Compose (PostgreSQL + pgvector, Langfuse, Streamlit y Next.js).

---

## 🏗️ 2. Arquitectura del Sistema

```mermaid
flowchart TB
    subgraph UI ["Capa de Presentación"]
        Streamlit["🖥️ Streamlit Dashboard (:8501)\n• Chat Multi-Turno & Streaming SSE\n• Drag & Drop Multimodal\n• Descarga Binaria de Reportes"]
        NextJS["🌐 Next.js 15 BFF (web/, :3001)\n• Proxy /api/* hacia FastAPI\n• Showcase offline con Golden Corpus"]
    end

    subgraph Gateway ["Capa de Aplicación (FastAPI Backend :8000)"]
        API["⚡ FastAPI API Gateway\n• REST Endpoints (/v1) & SSE Stream\n• Background Tasks Ingestion\n• Telemetry & Exception Handling"]
        Repo["📦 Repository Layer (Clean Architecture)\n• DocumentRepo • ChatRepo"]
    end

    subgraph Observability ["Observabilidad & Telemetría (:3000)"]
        Langfuse["📊 Langfuse Dashboard\n• Traces & Turn Spans\n• RRF & Reranker Latencies\n• Token Cost & Usage Metrics"]
    end

    subgraph AgentEngine ["Core del Agente Autónomo (ReAct)"]
        Agent["🧠 Autonomous Agent Service\n• Cascada de modelos Gemini\n• Thought-Action-Observation Loop\n• Citations Extractor & Validator"]
        
        subgraph ToolsCatalog ["Catálogo de Herramientas (Function Calling)"]
            T1["🔍 search_knowledge_base\n(Hybrid RAG + Reranking)"]
            T2["📄 generate_report_pdf\n(ReportLab Dynamic Engine)"]
            T3["🔔 dispatch_webhook\n(HTTPX Async Dispatcher)"]
        end
    end

    subgraph MultimodalPipeline ["Pipeline de Ingesta Jerárquico"]
        PDFParser["📑 PDF Plumber & Fitz\n• Text Extraction\n• Table-to-Markdown"]
        Vision["👁️ Vision Service\n• Gemini Multimodal Image OCR\n• Technical Diagram Synthesis"]
        Chunker["🧩 Hierarchical Chunker\n• Parent Chunks (1200 chars, overlap 120)\n• Child Chunks (350 chars, overlap 40)"]
        Embedder["📐 Embedding Service\n• Google gemini-embedding-001 (768d)\n• Solo chunks hoja"]
    end

    subgraph DataStore ["Capa de Persistencia (PostgreSQL 16 + pgvector :5432 · o SQLite zero-Docker)"]
        PGVector["🗄️ Vector Store\n• HNSW Cosine Index (document_chunks.embedding)\n• GIN Full-Text Search Index (Spanish & English tsvector)"]
        Relational["💾 Tablas Relacionales\n• documents • chat_messages (JSONB) • langfuse_db"]
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

    Agent <-->|Invocación Dinámica| ToolsCatalog
    T1 <-->|RRF + Semantic Rerank| PGVector
    T2 -->|Almacenamiento Físico| DiskReports["📂 uploads/reports/*.pdf"]
    T3 -->|POST Event Payload| WebhookTarget["🌐 External Services / Slack"]

    Agent <-->|Historial & Sesión| Relational
    Langfuse -->|Persistencia de Métricas| Relational
```

---

## ⚙️ 3. Decisiones Clave de Ingeniería

### 1. Chunking Jerárquico Parent-Child
* **Desafío:** Los fragmentos pequeños maximizan la precisión semántica en la recuperación vectorial, pero pierden el contexto global necesario para que el LLM genere respuestas coherentes.
* **Solución:** Se implementó una estrategia en dos niveles:
  * **Child Chunks (350 caracteres, solapamiento de 40):** Utilizados como vectores de búsqueda granular. Solo los fragmentos hoja reciben embedding; un padre que tiene hijos queda sin vector.
  * **Parent Chunks (1200 caracteres, solapamiento de 120):** Cada fragmento hijo almacena un puntero `parent_id`. Al recuperarse un fragmento hijo relevante, el sistema expande automáticamente el texto al fragmento padre antes de sintetizar la respuesta final.
  * Las tablas se almacenan como fragmentos padre en Markdown, y las descripciones de diagramas (Gemini Vision) usan el mismo chunker.

### 2. Búsqueda Híbrida Unificada con Reciprocal Rank Fusion (RRF)
* **Desafío:** La búsqueda puramente vectorial falla ante consultas con números de serie, acrónimos técnicos específicos o identificadores fiscales; la búsqueda léxica (BM25) ignora la semántica.
* **Solución:** Fusión bilingüe con dos rutas según el motor de base de datos:
  * **PostgreSQL (modo Enterprise):** distancia coseno de pgvector sobre embeddings de 768 dimensiones con índice **HNSW** (`m = 16`, `ef_construction = 64`, `vector_cosine_ops`), y full-text con diccionarios **español e inglés** sobre índices **GIN** (`to_tsvector`).
  * **SQLite (modo Zero-Docker):** coseno exacto en Python y BM25 (`k1 = 1.5`, `b = 0.75`) con tokenización bilingüe. Sin índice vectorial ni FTS, cada consulta recorre todos los fragmentos: coste O(N).
  * **Candidatos por ruta:** `min(top_k × SEARCH_CANDIDATE_MULTIPLIER, 80)`; con los valores por defecto y `top_k = 5`, son 20 por ruta.
  * **RRF ($k = 60$):** Algoritmo de normalización no supervisado que combina los rankings sin requerir calibración manual de pesos:
    $$\text{Score}_{RRF}(d) = \sum_{m \in \{\text{vector}, \text{lexical}\}} \frac{1}{k + \text{rank}_m(d)}$$

### 3. Memoria Conversacional Persistente en Base de Datos
* **Desafío:** Pérdida de contexto en chats multi-turno sin saturar la ventana de contexto del LLM con llamadas redundantes a herramientas.
* **Solución:** Modelo relacional `ChatMessage` con almacenamiento estructurado en `JSONB` (PostgreSQL) o JSON (SQLite) para `citations` y `executed_tools`. En turnos posteriores (ej. *"tradúcelo al inglés"* o *"resume lo anterior"*), el agente analiza la memoria de la sesión y resuelve la instrucción sin disparar consultas RAG redundantes.

### 4. Cascada de Resiliencia y Auto-Promoción de Modelos
* **Desafío:** Variaciones de cuota, spikes de latencia y deprecaciones en modelos de la API de Google (errores `404 NOT_FOUND` o `429 RESOURCE_EXHAUSTED`).
* **Solución:** Módulo con cascada transparente (`_call_gemini_with_fallback`):
  * Prioriza el modelo configurado (`GEMINI_AGENT_MODEL`).
  * Si la API notifica indisponibilidad (`404`, `429`, `503`, `NOT_FOUND`, `RESOURCE_EXHAUSTED`), promueve la ejecución a `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-2.5-flash` y `gemini-2.5-pro`, en ese orden.
  * Recuerda el modelo operativo para el resto de la sesión; si todos fallan, lo registra con `logger.error` y el agente responde con su modo determinístico de respaldo.

### 5. Reportes PDF Dinámicos con ReportLab
* **Desafío:** Generación de informes sin recurrir a plantillas fijas estáticas.
* **Solución:** La herramienta `generate_report_pdf` recibe argumentos dinámicos formulados por el LLM tras analizar el corpus: título contextualizado, síntesis ejecutiva estructurada y puntos de acción concretos, entregando el archivo listo para descarga directa.

### 6. Streaming en Tiempo Real (SSE) en FastAPI y Streamlit
* **Desafío:** La latencia percibida en respuestas generativas complejas con invocación multi-herramienta.
* **Solución:** Endpoint `POST /api/v1/agent/chat/stream` que emite Server-Sent Events (SSE) estructurados (`token` y `metadata`), consumido progresivamente por Streamlit con `st.write_stream` para una experiencia interactiva sin fricciones.

### 7. Reranking Semántico Posterior a RRF
* **Desafío:** Aunque RRF combina de manera equilibrada señales densas y esparsas, fragmentos que contienen palabras clave pero no responden semánticamente a la intención del usuario pueden posicionarse alto en el ranking inicial.
* **Solución:** `RerankerService` implementa una etapa de scoring semántico posterior a RRF:
  * Recupera una ventana extendida de candidatos (`top_k * 3`).
  * Califica la relevancia semántica de cada fragmento (escala 0.0 a 1.0) mediante Gemini, asignando `rerank_score`.
  * Reduce la selección a los mejores `top_k` y expande el contexto al fragmento padre (`Parent-Document Retrieval`).
  * **Fallback determinístico:** Ante timeouts (`RERANK_TIMEOUT_SECONDS`), errores o ausencia de cliente Gemini, preserva de forma transparente el orden RRF original. En ese caso `rerank_score` repite la puntuación RRF; ordena, pero no mide relevancia.

### 8. Observabilidad y Telemetría de LLM con Langfuse
* **Desafío:** Monitorear el comportamiento autónomo del agente ReAct en entornos de producción: auditar qué herramientas ejecuta, qué fragmentos recupera, la latencia de cada etapa y el consumo exacto de tokens y costos sin penalizar el rendimiento ni bloquear el flujo del usuario.
* **Solución:** Módulo desacoplado `TelemetryService` (`app/core/telemetry.py`):
  * **Contenedor auto-hospedado:** Servicio web de Langfuse integrado en `docker-compose.yml` (`:3000`) con persistencia en PostgreSQL (`langfuse_db`).
  * **Trazabilidad de Turnos:** Cada consulta del usuario genera un `Trace` raíz asociando el `session_id`.
  * **Spans de Ejecución:** Instrumentación contextual automática de herramientas (`search_knowledge_base`, `generate_report_pdf`, `dispatch_webhook`), búsqueda vectorial RRF y la fase de reranking semántico.
  * **Métricas de Generación:** Registro granular de modelos Gemini invocados, prompts procesados, tokens de entrada/salida y latencia en segundos.
  * **Resiliencia Total (No-Op Fallback):** Si Langfuse está deshabilitado (`LANGFUSE_ENABLED=false`) o el servidor está temporalmente inaccesible, `DummyTrace` y `DummySpan` garantizan latencia 0 ms sin arrojar excepciones al cliente.

### 9. Decisiones de Arquitectura (ADR)

Cada decisión grande tiene un registro con contexto, alternativas descartadas y limitaciones conocidas (los ADR están en inglés):

| ADR | Decisión | Qué resuelve |
|-----|----------|--------------|
| [ADR 001](docs/adr/001-hierarchical-parent-child-chunking.md) | Chunking jerárquico parent-child | Precisión del vector sin perder contexto; solo las hojas se vectorizan |
| [ADR 002](docs/adr/002-hybrid-rrf-and-semantic-reranking.md) | Búsqueda híbrida con RRF y reranking semántico | Identificadores exactos y paráfrasis; fallback determinístico del reranker |
| [ADR 003](docs/adr/003-tri-modal-zero-dependency-architecture.md) | Arquitectura tri-modal con fallback a SQLite | Ejecución sin Docker y stack completo con un comando |
| [ADR 004](docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md) | BFF de Next.js con showcase serverless | Demo siempre disponible sin exponer la clave del backend |

---

## 🚀 4. Guía de Descarga y Uso

### 4.1 Elige un modo

| Modo | Cómo arrancar | Dónde se ve | Datos |
|------|---------------|-------------|-------|
| **1. Cloud Showcase** (Vercel) | Importa el repositorio en Vercel con **Root Directory = `web`** | URL del despliegue | Golden Corpus embebido en el BFF, o el backend en vivo si `FASTAPI_URL` responde |
| **2. Zero-Docker** (solo Python) | `python run.py` | API en [http://localhost:8000/docs](http://localhost:8000/docs) | SQLite (`rag_standalone.db`) con el Golden Corpus sembrado automáticamente |
| **3. Full Enterprise** (Docker Compose) | `docker compose up -d --build` | Streamlit :8501, API :8000, Next.js :3001, Langfuse :3000 | PostgreSQL 16 + pgvector |
| **3b. GitHub Codespaces** | *Code → Codespaces → Create codespace* | Puertos reenviados 8000, 8501 y 3001 | SQLite dentro del contenedor de desarrollo |

> Los modos 2 y 3 ejecutan el mismo código. La base de datos se decide al arrancar: si PostgreSQL no responde y `AUTO_FALLBACK_SQLITE=true` (valor por defecto), la API continúa sobre SQLite. Ver [ADR 003](docs/adr/003-tri-modal-zero-dependency-architecture.md).

### 4.2 Requisitos previos

| Herramienta | Modo 1 (Vercel) | Modo 2 (Zero-Docker) | Modo 3 (Docker) | Codespaces |
|---|---|---|---|---|
| [Git](https://git-scm.com/) (o descarga ZIP) | Solo para hacer fork | ✅ | ✅ | — |
| [Python 3.11+](https://www.python.org/downloads/) | — | ✅ | — (va en la imagen) | — (va en el contenedor) |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | — | — | ✅ (en ejecución) | — |
| [Node.js](https://nodejs.org/) 20.9+ (CI usa 24) | Solo para desarrollo web local | Solo si quieres la web local | — (va en la imagen) | — (va en el contenedor) |
| Cuenta de [GitHub](https://github.com/) | Para importar en Vercel | — | — | ✅ |
| Cuenta de [Vercel](https://vercel.com/) | ✅ | — | — | — |

### 4.3 Clave de Google Gemini (opcional)

Consigue una `GOOGLE_API_KEY` gratuita en [Google AI Studio](https://aistudio.google.com/) (*Get API key*). **Es opcional:** sin ella todo arranca y funciona, pero en modo degradado:

| Función | Con `GOOGLE_API_KEY` | Sin clave |
|---|---|---|
| Embeddings | `gemini-embedding-001` (768 dimensiones) | Vectores simulados deterministas (SHA-256): la búsqueda densa no es semántica |
| Búsqueda léxica (BM25 / full-text) | Igual | Igual: es la única ruta de recuperación con significado real |
| Reranker | Gemini puntúa cada fragmento | Fallback: conserva el orden RRF |
| Agente | Razonamiento ReAct con Gemini y Function Calling | Agente de respaldo determinístico y offline |
| Descripción de imágenes y diagramas subidos | Gemini Vision | No disponible |
| Benchmark | `embedding_mode: "gemini"` | `embedding_mode: "mock"`; dense e hybrid marcados como no semánticos |

### 4.4 Descargar el proyecto

```bash
git clone https://github.com/MattMattia/multimodal-rag-agent.git
cd multimodal-rag-agent
```

Alternativa sin Git: en la página del repositorio, **Code → Download ZIP**, descomprime y abre una terminal en la carpeta.

Crea tu archivo de entorno a partir de la plantilla. El backend lee `.env` (y las variables del sistema); `.env` está en `.gitignore`.

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Variables mínimas por modo:

| Modo | Variables | Dónde |
|---|---|---|
| 1. Cloud Showcase | Ninguna obligatoria. Opcionales: `FASTAPI_URL`, `API_KEY`, `FASTAPI_TIMEOUT_MS` | Variables de entorno del proyecto en Vercel |
| 2. Zero-Docker | Ninguna obligatoria. Opcionales: `GOOGLE_API_KEY`; `DATABASE_URL=sqlite+aiosqlite:///./rag_standalone.db` para no intentar PostgreSQL | `.env` |
| 3. Full Enterprise | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (Compose las interpola). Opcionales: `GOOGLE_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `API_KEY` | `.env` (debe existir: Compose lo monta en el contenedor `api`) |

Ejemplo para el modo 3:

```ini
GOOGLE_API_KEY=            # opcional
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=rag_multimodal

# Observabilidad (opcional)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=

# Seguridad (opcional)
API_KEY=                   # si se define, /api/v1/* y /uploads/reports/* exigen el header X-API-Key
```

La tabla completa está en [Variables de entorno](#variables-de-entorno).

### 4.5 Modo 1: Cloud Showcase en Vercel

1. En Vercel: **Add New → Project** e importa el repositorio (o tu fork) de GitHub.
2. **Root Directory = `web`**. Vercel detecta el framework **Next.js**.
3. Variables de entorno (opcionales, solo de servidor; nunca `NEXT_PUBLIC_*`):
   * `FASTAPI_URL`: URL pública de un backend FastAPI desplegado.
   * `API_KEY`: se envía al backend como `X-API-Key`; nunca llega al navegador.
4. **Deploy** y abre la URL.

Cómo se comporta:

* **⚡ Vercel Serverless 24/7 Showcase Engine:** sin `FASTAPI_URL` o con el backend inalcanzable (error de red, timeout de cabeceras `FASTAPI_TIMEOUT_MS`, por defecto 3 s, o respuesta 502/504), el BFF responde con el motor showcase integrado y el Golden Corpus embebido.
* **🟢 Live FastAPI + pgvector Cluster:** con un backend accesible, el BFF reenvía las peticiones a FastAPI. La cabecera `x-rag-source` indica quién respondió.
* El showcase es **sin estado**: las subidas de documentos solo funcionan contra un backend en vivo.

Ver [ADR 004](docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md).

**Ejecutar la web en local:**

```bash
cd web
npm install
npm run dev        # http://localhost:3001
```

Para conectarla a un backend local, define `FASTAPI_URL=http://localhost:8000` en `web/.env.local` (o en la terminal) antes de `npm run dev`.

> **Windows y rutas con `&`:** los shims `.cmd` de npm fallan si la ruta de la carpeta contiene `&`. Los scripts de `web/package.json` llaman a `node node_modules/...` directamente, así que `npm run dev`, `npm run build` y `npm test` funcionan; `npx` puede fallar. La carpeta que crea `git clone` (`multimodal-rag-agent`) no tiene ese problema.

### 4.6 Modo 2: Zero-Docker (Python + SQLite)

1. Crea y activa un entorno virtual:

   ```bash
   python -m venv .venv
   ```

   | Terminal | Activación |
   |---|---|
   | Windows PowerShell | `.venv\Scripts\Activate.ps1` |
   | Git Bash (Windows) | `source .venv/Scripts/activate` |
   | macOS / Linux | `source .venv/bin/activate` |

   Con [uv](https://docs.astral.sh/uv/): `uv venv --python 3.11`, activa igual y usa `uv pip install` en el paso 2.

2. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   pip install -r frontend/requirements.txt   # solo si vas a usar Streamlit
   ```

3. Arranca la API:

   ```bash
   python run.py                       # 127.0.0.1:8000
   python run.py --host 0.0.0.0 --port 8080   # opcional: otra interfaz o puerto
   ```

   Al quedar lista, la consola muestra un banner como este:

   ```
     Ready  (database: SQLite Zero-Docker, Golden Corpus auto-seeded)
     API        http://localhost:8000
     Swagger    http://localhost:8000/docs
     OpenAPI    http://localhost:8000/openapi.json
     Streamlit  streamlit run frontend/app.py   (http://localhost:8501)
     Web        cd web && npm run dev            (http://localhost:3001)
   ```

   * Por defecto `DATABASE_URL` apunta a PostgreSQL; si no responde, la API usa `sqlite+aiosqlite:///./rag_standalone.db` (el archivo `rag_standalone.db` en la raíz). Para saltarte el intento, define esa `DATABASE_URL` en `.env`.
   * Si la tabla `documents` está vacía, el Golden Corpus (3 PDFs + 3 PNGs generados localmente) se siembra automáticamente (`AUTO_SEED_DEMO_CORPUS=true`).
   * Búsqueda: coseno exacto en Python y BM25, sin pgvector.

4. Interfaces opcionales, cada una en otra terminal:

   ```bash
   streamlit run frontend/app.py          # http://localhost:8501
   cd web && npm install && npm run dev   # http://localhost:3001, con FASTAPI_URL=http://localhost:8000
   ```

5. Exportar el contrato OpenAPI sin arrancar el servidor: `python run.py --export-openapi` (escribe `docs/openapi.json`).

### 4.7 Modo 3: Full Enterprise (Docker Compose)

1. Con Docker Desktop en ejecución y `.env` creado (ver [4.4](#44-descargar-el-proyecto)):

   ```bash
   docker compose up -d --build
   ```

2. Servicios:

   | Servicio | URL / puerto | Contenido |
   |---|---|---|
   | `api` | [http://localhost:8000/docs](http://localhost:8000/docs) | FastAPI + Swagger UI (con `--reload` para desarrollo) |
   | `frontend` | [http://localhost:8501](http://localhost:8501) | Dashboard Streamlit |
   | `web` | [http://localhost:3001](http://localhost:3001) | Next.js BFF + showcase (`3001` evita el choque con Langfuse) |
   | `langfuse` | [http://localhost:3000](http://localhost:3000) | Dashboard de observabilidad |
   | `db` | `localhost:5432` (o `POSTGRES_PORT`) | PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16`) |

3. Comprobación de salud: [http://localhost:8000/health](http://localhost:8000/health) y `docker compose ps`.

4. **Primera ejecución de Langfuse (opcional):** Compose activa `LANGFUSE_ENABLED=true`, pero sin claves la telemetría queda en modo no-op sin afectar a la API. Para trazas reales, crea una cuenta y un proyecto en [http://localhost:3000](http://localhost:3000), copia `LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY` a `.env` y recrea la API con `docker compose up -d api`.

5. Pruebas dentro del contenedor:

   ```bash
   docker compose exec api pytest -v
   ```

6. Parar y limpiar:

   ```bash
   docker compose down        # para los contenedores y conserva los datos
   docker compose down -v     # ⚠️ borra también el volumen postgres_data (documentos, chats y datos de Langfuse)
   ```

> **Contenedores sin privilegios:** las imágenes de `api` y `frontend` se ejecutan con el usuario no-root `appuser` (uid 1000) e incluyen `HEALTHCHECK`. La imagen base de la API arranca sin `--reload`; `docker-compose.yml` lo añade solo para desarrollo.

#### GitHub Codespaces

1. En el repositorio: **Code → Codespaces → Create codespace** (o [https://codespaces.new/MattMattia/multimodal-rag-agent](https://codespaces.new/MattMattia/multimodal-rag-agent)).
2. El devcontainer (`.devcontainer/devcontainer.json`) usa Python 3.11 y Node 24, y al crearse ejecuta `pip install -r requirements.txt`, `pip install -r frontend/requirements.txt` y `npm ci` en `web/`.
3. Corre en **modo SQLite** (`DATABASE_URL=sqlite+aiosqlite:///./rag_standalone.db`, sin Docker Compose) y ya define `FASTAPI_URL=http://localhost:8000`.
4. Arranca los servicios en terminales separadas:

   ```bash
   python run.py                    # puerto 8000
   streamlit run frontend/app.py    # puerto 8501
   cd web && npm run dev            # puerto 3001
   ```

5. Abre los puertos reenviados desde la pestaña **Ports**. Define `GOOGLE_API_KEY` como secreto de Codespaces si quieres embeddings reales.

### 4.8 Los primeros 5 minutos

1. Abre la web (URL de Vercel o [http://localhost:3001](http://localhost:3001)) y mira la insignia de estado: ⚡ showcase o 🟢 Live.
2. **📚 Knowledge Base → 🚀 Restore Golden Demo Corpus** para (re)sembrar los 3 documentos de demo.
3. **💬 Agent Studio:** pulsa una de las preguntas rápidas, por ejemplo *"What HNSW parameters does the vector index use (m, ef_construction)?"*, y revisa las citas y la línea de tiempo de herramientas.
4. **📊 Benchmark Lab → ▶ Run live benchmark** para comparar dense, sparse e hybrid.
5. **Reporte PDF:** pulsa la pregunta rápida *"Generate a PDF report on GlobalTech's EBITDA and inference costs."*; con un backend en vivo, el agente ejecuta `generate_report_pdf` (📄) y devuelve el enlace de descarga. También puedes exportar la conversación con **⬇️ PDF** en la barra de sesiones.

### 4.9 Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `address already in use` / puerto ocupado | Otro proceso usa el puerto. API: `python run.py --port 8010`. Streamlit: `streamlit run frontend/app.py --server.port 8502`. Docker: cambia el mapeo en `docker-compose.yml` o `POSTGRES_PORT` para la base de datos. |
| `404` con `text-embedding-004` | Ese modelo ya no está disponible. El proyecto usa `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`; corrige o elimina esa línea en un `.env` antiguo. |
| `404 NOT_FOUND` con modelos `gemini-1.5-*` | Modelos retirados. La cascada promueve a un modelo disponible, pero conviene definir `GEMINI_AGENT_MODEL` y `GEMINI_VISION_MODEL` en `.env` con un modelo vigente (por ejemplo `gemini-3.8-flash`). El código y `docker-compose.yml` ya usan `gemini-3.8-flash` por defecto, así que solo ocurre con un `.env` antiguo. |
| `Cannot connect to the Docker daemon` / `docker compose` falla | Docker Desktop no está en ejecución. Ábrelo, espera a que el motor arranque y repite el comando. |
| `npx` o los shims de npm fallan en Windows | La ruta contiene `&`. Usa `npm run dev/build/test` o clona en una carpeta sin `&`. |
| Avisos `LF will be replaced by CRLF` | Conversión de finales de línea de Git en Windows. Son inofensivos. |
| La web muestra ⚡ con un backend local | `FASTAPI_URL` no está definida para el proceso de Next.js, o el backend tardó más de `FASTAPI_TIMEOUT_MS`. |

### Variables de entorno

Valores por defecto tomados de `app/core/config.py`. Las variables se leen desde el entorno o desde `.env`.

| Variable | Valor por defecto | Efecto |
|---|---|---|
| **General** | | |
| `PROJECT_NAME` | `Sistema RAG Multimodal & Agente IA Autónomo` | Nombre mostrado en la API |
| `API_V1_STR` | `/api/v1` | Prefijo de la API versionada |
| `ENVIRONMENT` | `development` | Etiqueta de entorno (la devuelve `/health`) |
| `DEBUG` | `true` | Con `true` se muestra el detalle de las excepciones; en producción define `false` |
| **Base de datos** | | |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/rag_multimodal` | Motor. Admite `sqlite+aiosqlite:///./rag.db` para el modo Zero-Docker |
| `AUTO_FALLBACK_SQLITE` | `true` | Si PostgreSQL no responde al arrancar, usa `sqlite+aiosqlite:///./rag_standalone.db` (sin pgvector, coseno exacto y BM25 en Python) |
| `AUTO_SEED_DEMO_CORPUS` | `true` | Al terminar `init_db()`, si `documents` está vacía se siembra el Golden Corpus (3 PDFs + 3 PNGs generados localmente) |
| **Google / Gemini** | | |
| `GOOGLE_API_KEY` | vacío | Sin clave, embeddings simulados (SHA-256), reranker en modo fallback y agente de respaldo |
| `GEMINI_AGENT_MODEL` | `gemini-3.8-flash` | Modelo preferido del agente y del reranker; si no está disponible, entra la cascada |
| `GEMINI_VISION_MODEL` | `gemini-3.8-flash` | Modelo de descripción de imágenes y diagramas |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Modelo de embeddings (la API actual no expone `text-embedding-004`) |
| `EMBEDDING_DIMENSION` | `768` | Dimensión de embeddings y de la columna `vector(N)`. Cambiarla exige recrear la columna |
| `EMBEDDING_BATCH_SIZE` | `50` | Textos por llamada a la API de embeddings |
| **Ingesta** | | |
| `PARENT_CHUNK_SIZE` / `PARENT_CHUNK_OVERLAP` | `1200` / `120` | Tamaño y solape de los fragmentos padre |
| `CHILD_CHUNK_SIZE` / `CHILD_CHUNK_OVERLAP` | `350` / `40` | Tamaño y solape de los fragmentos hijo (los vectorizados) |
| `PDF_IMAGE_DPI` | `150` | Resolución de las imágenes extraídas de PDFs |
| `PDF_MIN_IMAGE_DIM` | `40` | Lado mínimo (pt) para no tratar un icono como imagen |
| `MAX_UPLOAD_SIZE_MB` | `25` | Tamaño máximo por archivo subido; por encima responde `413` y elimina el archivo parcial |
| **Búsqueda** | | |
| `SEARCH_CANDIDATE_MULTIPLIER` | `4` | Candidatos por ruta antes de la fusión: `min(top_k × multiplicador, 80)` |
| `RRF_K` | `60` | Constante de suavizado de Reciprocal Rank Fusion |
| `RERANK_TIMEOUT_SECONDS` | `8.0` | Tiempo máximo del reranker; al superarlo se aplica el fallback RRF |
| `RERANK_MAX_SNIPPET_CHARS` | `800` | Caracteres de cada fragmento enviados al reranker |
| **Agente** | | |
| `AGENT_MAX_HISTORY_MESSAGES` | `20` | Mensajes previos enviados al LLM |
| `AGENT_MAX_TURNS` | `4` | Iteraciones ReAct máximas por turno |
| `AGENT_TEMPERATURE` | `0.2` | Temperatura del agente |
| **Observabilidad** | | |
| `LANGFUSE_ENABLED` | `false` | Activa la telemetría. El `docker-compose.yml` la activa por defecto (`true`) |
| `LANGFUSE_HOST` | `http://langfuse:3000` | Host de Langfuse |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | vacío | Credenciales de Langfuse |
| **Seguridad y acceso** | | |
| `API_KEY` | vacío (acceso abierto) | Si se define, `/api/v1/*` y la descarga de reportes exigen `X-API-Key`. `/health` permanece abierto |
| `ALLOWED_WEBHOOK_HOSTS` | vacío | Hosts permitidos para webhooks por `http://`. Las IPs privadas, loopback y nombres internos siempre se bloquean (anti-SSRF) |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8000,http://localhost:8501` | Orígenes CORS (lista separada por comas). El BFF de Next.js llama al backend desde el servidor y no necesita CORS |
| `ALLOWED_ORIGIN_REGEX` | vacío | Expresión regular opcional de orígenes CORS adicionales (p. ej. `https://.*\.vercel\.app`) |
| `RATE_LIMIT_ENABLED` | `true` | Límite de peticiones por IP (ventana deslizante en memoria de un solo proceso). Se desactiva bajo `pytest` |
| `RATE_LIMIT_PER_MINUTE` | `60` | Peticiones máximas por IP y minuto; al superarlo responde `429` con `Retry-After`. `/health` y `/api/v1/health` están exentos |

**Variables del BFF de Next.js** (`web/`, solo en el servidor; nunca `NEXT_PUBLIC_*`):

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `FASTAPI_URL` | vacío | URL base del backend. Sin ella, el showcase responde todas las rutas |
| `API_KEY` | vacío | Se envía al backend como `X-API-Key` |
| `FASTAPI_TIMEOUT_MS` | `3000` | Tiempo de espera de las cabeceras del backend antes de usar el showcase |

**Variables de Streamlit** (`frontend/api_client.py`):

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `API_URL` | `http://localhost:8000` | URL del backend desde el contenedor o proceso de Streamlit |
| `PUBLIC_API_URL` | `http://localhost:8000` | URL del backend visible desde el navegador |
| `API_KEY` | vacío | Clave enviada como `X-API-Key` |

Variables de Docker Compose: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` (5432), `LANGFUSE_DB`. Las credenciales de Langfuse (`NEXTAUTH_SECRET`, `SALT`) tienen valores de desarrollo: define los tuyos fuera de local.

---

## 📡 5. Catálogo de Endpoints de la API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Healthcheck del backend y estado de la base de datos |
| `POST` | `/api/v1/documents/upload` | Ingesta de archivos PDF/Imágenes (procesamiento asíncrono) |
| `GET` | `/api/v1/documents` | Listado de documentos indexados con estado y recuento de chunks |
| `GET` | `/api/v1/documents/{id}` | Detalle de un documento y fragmentos generados |
| `POST` | `/api/v1/search` | Búsqueda Híbrida (`query`, `top_k`, `mode`, `filter_document_id`, `rerank`); la respuesta incluye `diagnostics` (latencia por etapa: `embedding_ms`, `dense_ms`, `sparse_ms`, `rrf_fusion_ms`, `rerank_ms`, `total_ms`, candidatos y bloques únicos) |
| `POST` | `/api/v1/agent/chat` | Interacción multi-turno con el Agente Autónomo ReAct |
| `POST` | `/api/v1/agent/chat/stream` | Respuestas en Streaming en tiempo real (Server-Sent Events: `token`, `tool_end` con `duration_ms` y `diagnostics`, y `metadata` final con `diagnostics` y `duration_ms`). Ambos endpoints de chat aceptan `filter_document_id`, `search_mode`, `top_k`, `enable_rerank`, `temperature`, `max_turns` y `language` (`es` \| `en` \| `auto`, por defecto `auto`: se detecta del mensaje) |
| `GET` | `/api/v1/agent/sessions/{session_id}/history` | Historial persistido de una conversación |
| `GET` | `/uploads/reports/{filename}` | Descarga de reportes PDF generados por el agente (exige `X-API-Key` si `API_KEY` está definida; solo sirve archivos dentro de `uploads/reports/`) |
| `GET` | `/api/v1/reports/{filename}` | Reporte PDF generado por el agente (`Content-Disposition: inline`); mismo control de contención que la ruta legada |
| `GET` | `/api/v1/documents/{id}/file` | Archivo original subido (autenticado, contenido en `uploads/documents/`) |
| `GET` | `/api/v1/documents/{id}/images/{image_id}/file` | Imagen extraída o subida (`image/png`, `image/jpeg`, `image/webp`); verifica que pertenezca al documento |
| `GET` | `/api/v1/agent/sessions` | Sesiones de chat (`session_id`, `title`, `created_at`, `updated_at`, `message_count`) por `updated_at` descendente |
| `DELETE` | `/api/v1/agent/sessions/{session_id}` | Elimina los mensajes de una sesión (`204`, o `404` si no existe) |
| `GET` | `/api/v1/agent/sessions/{session_id}/export?format=markdown\|pdf&lang=es\|en` | Exporta la conversación con citas y herramientas ejecutadas; `lang` (por defecto `es`) localiza las etiquetas |
| `POST` | `/api/v1/agent/feedback` | Feedback `{session_id, message_id, rating: 1\|-1, comment}`; se guarda en `message_metadata` y se envía a Langfuse si está activo |
| `POST` | `/api/v1/demo/seed` | Re-siembra idempotente del Golden Corpus (genera los PDFs/PNGs que falten; sin API key no llama a Gemini) |
| `GET` | `/api/v1/demo/status` | `db_dialect`, `demo_seeded`, totales de documentos/chunks/imágenes, `gemini_configured`, `langfuse_enabled` y `active_models` |
| `POST` | `/api/v1/demo/evaluate?lang=es\|en` | Evaluación RAG `dense` vs `sparse` vs `hybrid` (RRF + reranker); ver la sección de benchmark |

### OpenAPI

El esquema OpenAPI 3.1 del backend se exporta sin arrancar el servidor:
```bash
python run.py --export-openapi   # escribe docs/openapi.json
```
El contrato versionado está en [docs/openapi.json](docs/openapi.json). Swagger UI está en `/docs` mientras la API corre.

### Benchmark de evaluación RAG

`POST /api/v1/demo/evaluate` (cuerpo opcional `{"top_k": 5}`; `409` si el corpus no está sembrado) ejecuta **8 consultas golden** contra el Golden Corpus en los modos `dense`, `sparse` e `hybrid`. Para cada modo devuelve `hit_rate_at_k`, `mrr`, `ndcg_at_k`, `avg_latency_ms` y el desglose por consulta.

**Resultados reales** medidos el 2026-11-09 con `gemini-embedding-001` (768 dimensiones, normalizados L2), Golden Demo Corpus (3 documentos), 8 consultas golden (5 parafraseadas o entre idiomas), motor SQLite (coseno exacto en Python + BM25) y reranker Gemini en modo híbrido:

| Modo | Hit@1 | Hit@5 | MRR@5 | NDCG@5 | Latencia media |
|---|---|---|---|---|---|
| Dense (gemini-embedding-001) | 0.875 | 1.000 | 0.938 | 0.884 | ~460 ms |
| Sparse (BM25) | 0.750 | 0.875 | 0.813 | 0.758 | ~3 ms |
| Hybrid (RRF k=60 + reranker Gemini) | 1.000 | 1.000 | 1.000 | 1.000 | ~5.9 s |

Cómo leer estos números:

* **Corpus diminuto:** con 3 documentos las puntuaciones quedan cerca del techo; muestran sobre todo el comportamiento relativo entre modos, no la calidad absoluta.
* **Latencia híbrida:** la domina la llamada al reranker LLM. El evaluador siempre reranquea el modo `hybrid`; en el chat se desactiva con `enable_rerank=false` y en `/api/v1/search` con `rerank: false`.
* **NDCG es sensible al recall:** penaliza que falten fragmentos relevantes en el top-k, no solo la posición del primero.
* **Variabilidad:** con el reranker activo, los resultados cambian ligeramente entre ejecuciones.
* **Sin `GOOGLE_API_KEY`:** `dense` e `hybrid` usan vectores SHA-256 deterministas. La respuesta trae `embedding_mode: "mock"`, un `warning` y `semantic: false` en esos modos; solo `sparse` es significativo.

**Cómo reproducirlo:**

1. Define `GOOGLE_API_KEY` y arranca el backend (modo 2 o 3).
2. Asegura el corpus: se siembra solo al arrancar, o con `POST /api/v1/demo/seed`.
3. Ejecuta `POST /api/v1/demo/evaluate` desde Swagger (`/docs`) o:

   ```bash
   curl -X POST http://localhost:8000/api/v1/demo/evaluate -H "Content-Type: application/json" -d '{"top_k": 5}'
   ```

   O abre **📊 Benchmark Lab → ▶ Run live benchmark** en la web, que renderiza el informe y su lista `warnings`, tanto si responde FastAPI como el showcase.

---

## 🧪 6. Ejecución de la Suite de Pruebas

El sistema incluye una batería de pruebas automatizadas que validan la ingesta multimodal, el chunking jerárquico, la búsqueda híbrida con RRF, el reranking semántico, el streaming SSE, la telemetría resiliente, la persistencia en base de datos, el bucle ReAct del agente, la evaluación RAG y el endurecimiento de seguridad (SSRF, subidas, autenticación, rate limit). Referencia: 244 pruebas de backend en PostgreSQL, 243 + 1 omitida en SQLite y 47 pruebas de la web.

**Dentro de Docker:**
```bash
docker compose exec api pytest -v
```

**En local con PostgreSQL** (levanta el servicio `db` con `docker compose up -d db`; las pruebas del agente llaman a Gemini y necesitan `GOOGLE_API_KEY`), con el entorno virtual activado:
```bash
python -m pytest -q -p no:cacheprovider
```

**En local con SQLite** (sin Docker; toda la suite corre contra un archivo temporal):
```bash
TEST_DATABASE_URL=sqlite+aiosqlite:///./test_rag.db python -m pytest -q -p no:cacheprovider
# PowerShell: $env:TEST_DATABASE_URL="sqlite+aiosqlite:///./test_rag.db"; python -m pytest -q -p no:cacheprovider
```
Las pruebas marcadas con `@pytest.mark.postgres_only` (introspección del pool de asyncpg) se omiten en ese modo.

**Frontend Next.js (`web/`):**
```bash
cd web
npm install
npm test          # Vitest: BFF, showcase engine y componentes
npm run build     # build de producción; comprueba también las vistas y las ADR
```
Los scripts de `web/package.json` llaman a `node node_modules/...` directamente, porque en rutas con `&` (como esta carpeta de Windows) los shims `.cmd` de npm fallan.

`tests/conftest.py` elimina al final de la sesión los PDF generados en `uploads/reports/` durante las pruebas, conservando los existentes.

La CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) ejecuta ruff, mypy, pytest sobre PostgreSQL y SQLite, la comprobación de que `docs/openapi.json` está al día y, en `web/`, `npm run typecheck`, `npm test` y `npm run build`.

---

## 📂 7. Estructura del Código

Árbol de `app/`, `frontend/`, `web/src/` y `tests/` (sin `node_modules` ni `.next`):

```
├── app/
│   ├── api/v1/
│   │   ├── endpoints/
│   │   │   ├── agent.py           # Chat síncrono, streaming SSE, sesiones, export y feedback
│   │   │   ├── demo.py            # Golden Corpus: seed, status y evaluate
│   │   │   ├── documents.py       # Ingesta, subida y consulta documental
│   │   │   ├── files.py           # Descarga autenticada de archivos, imágenes y reportes
│   │   │   ├── health.py          # Monitoreo y readiness checks
│   │   │   └── search.py          # Búsqueda híbrida vectorial + texto + rerank
│   │   └── router.py              # Enrutador centralizado v1
│   ├── core/
│   │   ├── config.py              # Pydantic BaseSettings (variables de entorno)
│   │   ├── database.py            # Engines PostgreSQL/SQLite, dialecto activo e inicialización DDL
│   │   ├── rate_limit.py          # Límite de peticiones por IP (ventana deslizante en memoria)
│   │   ├── security.py            # Autenticación opcional por header X-API-Key
│   │   └── telemetry.py           # Servicio Singleton de Observabilidad con Langfuse
│   ├── models/                    # Modelos ORM SQLAlchemy (JSON/JSONB, vector o JSON según dialecto)
│   ├── schemas/                   # Esquemas de validación y serialización Pydantic v2
│   ├── services/                  # Lógica de negocio nuclear
│   │   ├── agent.py               # Orquestador del Agente ReAct & Gemini Cascade
│   │   ├── demo_corpus.py         # Definición del Golden Corpus (3 documentos y sus imágenes)
│   │   ├── demo_seeder.py         # Generación de PDFs/PNGs y siembra idempotente
│   │   ├── embedding.py           # Servicio de vectorización (gemini-embedding-001, 768d)
│   │   ├── evaluation.py          # RAGEvaluationService: 8 consultas golden y métricas IR
│   │   ├── ingestion.py           # Pipeline de extracción, OCR y chunking jerárquico
│   │   ├── lexical.py             # Tokenizador bilingüe y BM25 (modo SQLite)
│   │   ├── rag_search.py          # Búsqueda híbrida RRF (pgvector + full-text, o Python en SQLite)
│   │   ├── reranker.py            # Servicio de Reranking Semántico con Gemini
│   │   └── vision.py              # Extracción visual de diagramas y facturas
│   ├── tools/                     # Herramientas ejecutables por el Agente
│   │   ├── pdf_generator.py       # Generador de informes PDF con ReportLab
│   │   ├── rag_tool.py            # Herramienta de búsqueda en la base de conocimiento
│   │   └── webhook_tool.py        # Disparador asíncrono de webhooks HTTP
│   └── main.py                    # Punto de entrada de la aplicación FastAPI
├── docs/
│   ├── adr/                       # Architecture Decision Records (001-004)
│   └── openapi.json               # Contrato OpenAPI 3.1 exportado (python run.py --export-openapi)
├── docker/
│   └── init.sql                   # Extensiones PostgreSQL y base de datos langfuse
├── frontend/                      # Dashboard Streamlit (puerto 8501)
│   ├── app.py                     # Entrada de la aplicación Streamlit
│   ├── api_client.py              # Cliente HTTP hacia la API
│   ├── views/                     # Chat, diagnostics, benchmark y sidebar
│   ├── Dockerfile
│   └── requirements.txt           # Dependencias del frontend
├── web/                           # Next.js 15 (Root Directory de Vercel)
│   ├── src/app/                   # App Router: vistas (/, knowledge, benchmark, architecture) y route handlers BFF (api/*)
│   ├── src/components/            # Componentes de agente, conocimiento, benchmark, arquitectura y shell
│   ├── src/content/adr/           # Copia de docs/adr/ que lee la vista Architecture
│   ├── src/lib/server/            # BFF: cliente FastAPI con fallback y validación
│   ├── src/lib/showcase/          # Motor showcase serverless (corpus, dense, BM25, RRF, agente, evaluación)
│   └── src/lib/contracts.ts       # Tipos compartidos entre BFF, FastAPI y UI
├── tests/                         # Batería de pruebas (PostgreSQL y SQLite)
│   ├── conftest.py                # Fixtures compartidas (limpieza de reportes PDF generados)
│   ├── test_agent.py              # Agente ReAct, Function Calling, memoria y streaming
│   ├── test_documents.py          # Extracción multimodal, tablas y chunking
│   ├── test_demo.py               # Golden Corpus: seed, status y evaluación
│   ├── test_evaluation.py         # Métricas IR y benchmark
│   ├── test_sqlite_mode.py        # Modo Zero-Docker sobre SQLite
│   ├── test_rate_limit.py         # Límite de peticiones por IP
│   ├── test_search.py             # Embeddings, RRF y búsqueda híbrida
│   ├── test_security.py           # SSRF, subidas, escape XML, X-API-Key y errores 500
│   └── test_telemetry.py          # DummySpan, DummyTrace y cliente Langfuse
├── .devcontainer/                 # Entorno GitHub Codespaces (devcontainer.json)
├── .github/workflows/ci.yml       # CI: ruff, mypy, pytest (PostgreSQL + SQLite) y npm run build
├── docker-compose.yml             # Orquestación multicontenedor (db, api, frontend, langfuse y web)
├── Dockerfile                     # Imagen de backend (usuario no-root + HEALTHCHECK)
├── run.py                         # Launcher: arranque Zero-Docker y --export-openapi
├── pyproject.toml                 # Configuración de ruff y mypy
├── pytest.ini                     # Configuración de pytest (asyncio_mode = auto)
├── requirements.txt               # Dependencias Python
├── README.md                      # Documentación en inglés
└── README.es.md                   # Documentación en español
```

---

## 👨‍💻 Autor y Contacto

* **Autor:** [Mattia Risso](https://github.com/MattMattia)
* **Proyecto:** Sistema RAG Multimodal & Agente IA Autónomo
* **Repositorio:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)
* **Licencia:** MIT License
