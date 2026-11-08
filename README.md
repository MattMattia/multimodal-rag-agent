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
<!-- CI badge placeholder: replace the workflow status once .github/workflows/ci.yml runs on the default branch. -->
[![CI](https://github.com/MattMattia/multimodal-rag-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MattMattia/multimodal-rag-agent/actions/workflows/ci.yml)

**Desarrollado por [Mattia Risso](https://github.com/MattMattia)**  
🔗 **Repositorio:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)

</div>

---

## 📌 1. Visión Ejecutiva

Sistema de Inteligencia Artificial empresarial de extremo a extremo que combina un pipeline de **Ingesta y Extracción Multimodal**, **Búsqueda Híbrida Avanzada (Dense Vector + Full-Text Search)**, **Reranking Semántico con LLM** y un **Agente IA Autónomo ReAct** con catálogo de herramientas dinámicas (Function Calling), memoria conversacional persistente y **Observabilidad de Nivel Empresarial con Langfuse**.

El sistema procesa documentos no estructurados y de alta complejidad (PDFs con maquetación heterogénea, tablas formateadas, diagramas técnicos y recibos/facturas), vectoriza el conocimiento preservando la jerarquía contextual mediante **Parent-Child Chunking**, y habilita la toma de decisiones autónoma mediante razonamiento multi-paso, generación dinámica de reportes ejecutivos en PDF, despacho de eventos vía webhooks y monitoreo en tiempo real de tokens y latencias.

**Puedes probarlo en tres modos** (ver [sección 4](#-4-guía-de-inicio-rápido)): demo en la nube sin instalar nada, ejecución local solo con Python (SQLite, sin Docker) y el stack completo con Docker Compose (PostgreSQL + pgvector, Langfuse, Streamlit y Next.js).

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
        Agent["🧠 Autonomous Agent Service\n• Gemini 1.5 Pro / 3.6 Flash Cascade\n• Thought-Action-Observation Loop\n• Citations Extractor & Validator"]
        
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
  * Prioriza el modelo configurado (`gemini-1.5-pro` / `gemini-1.5-flash`).
  * Si la API notifica indisponibilidad, promueve la ejecución a variantes de alta velocidad con cuota estable (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`).
  * Recuerda el modelo operativo para el resto de la sesión y cuenta con respaldo de contingencia con trazabilidad explícita (`logger.error`).

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

#### 8. Observabilidad y Telemetría de LLM con Langfuse
* **Desafío:** Monitorear el comportamiento autónomo del agente ReAct en entornos de producción: auditar qué herramientas ejecuta, qué fragmentos recupera, la latencia de cada etapa y el consumo exacto de tokens y costos sin penalizar el rendimiento ni bloquear el flujo del usuario.
* **Solución:** Módulo desacoplado `TelemetryService` (`app/core/telemetry.py`):
  * **Contenedor auto-hospedado:** Servicio web de Langfuse integrado en `docker-compose.yml` (`:3000`) con persistencia en PostgreSQL (`langfuse_db`).
  * **Trazabilidad de Turnos:** Cada consulta del usuario genera un `Trace` raíz asociando el `session_id`.
  * **Spans de Ejecución:** Instrumentación contextual automática de herramientas (`search_knowledge_base`, `generate_report_pdf`, `dispatch_webhook`), búsqueda vectorial RRF y la fase de reranking semántico.
  * **Métricas de Generación:** Registro granular de modelos Gemini invocados, prompts procesados, tokens de entrada/salida y latencia en segundos.
  * **Resiliencia Total (No-Op Fallback):** Si Langfuse está deshabilitado (`LANGFUSE_ENABLED=false`) o el servidor está temporalmente inaccesible, `DummyTrace` y `DummySpan` garantizan latencia 0 ms sin arrojar excepciones al cliente.

### 9. Decisiones de Arquitectura (ADR)

Cada decisión grande tiene un registro con contexto, alternativas descartadas y limitaciones conocidas:

| ADR | Decisión | Qué resuelve |
|-----|----------|--------------|
| [001](docs/adr/001-hierarchical-parent-child-chunking.md) | Chunking jerárquico parent-child | Precisión del vector sin perder contexto; solo las hojas se vectorizan |
| [002](docs/adr/002-hybrid-rrf-and-semantic-reranking.md) | Búsqueda híbrida con RRF y reranking semántico | Identificadores exactos y paráfrasis; fallback determinístico del reranker |
| [003](docs/adr/003-tri-modal-zero-dependency-architecture.md) | Arquitectura tri-modal con fallback a SQLite | Ejecución sin Docker y stack completo con un comando |
| [004](docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md) | BFF de Next.js con showcase serverless | Demo siempre disponible sin exponer la clave del backend |

---

## 🚀 4. Guía de Inicio Rápido

### Modos de ejecución

| Modo | Cómo arrancar | Requisitos | Dónde se ve | Datos |
|------|---------------|------------|-------------|-------|
| **1. Cloud Showcase** (Vercel) | Importa el repositorio en Vercel con **Root Directory = `web`** | Cuenta de Vercel | URL del despliegue | Golden Corpus embebido en el BFF; si `FASTAPI_URL` no está definida o el backend no responde, el showcase sirve la demo |
| **2. Zero-Docker Local** | `python run.py` | Python 3.11+ | [http://localhost:8000/docs](http://localhost:8000/docs) | SQLite (`rag_standalone.db`) con el Golden Corpus sembrado automáticamente |
| **3. Full Enterprise** | `docker compose up -d --build` | Docker Desktop | Streamlit :8501, API :8000, Next.js :3001, Langfuse :3000 | PostgreSQL 16 + pgvector |
| **GitHub Codespaces** | *Code → Codespaces → Create codespace* con el devcontainer del repositorio | Cuenta de GitHub | Puertos reenviados por Codespaces | Igual que el modo 3 dentro del contenedor de desarrollo |

> El modo 2 y el modo 3 usan el mismo código. La selección de base de datos se decide al arrancar: si PostgreSQL no responde y `AUTO_FALLBACK_SQLITE=true` (por defecto), la API continúa sobre SQLite. Ver [ADR 003](docs/adr/003-tri-modal-zero-dependency-architecture.md).

#### Modo 1: Cloud Showcase
1. Importa el repositorio en Vercel y define **Root Directory = `web`**.
2. Opcional: define `FASTAPI_URL` (URL pública del backend) y `API_KEY` si el backend la exige. Sin `FASTAPI_URL`, el showcase responde todas las rutas.
3. Para probarlo en local: `cd web`, `npm install`, `npm run dev` y abre [http://localhost:3001](http://localhost:3001).

El BFF responde desde FastAPI cuando está disponible y solo cae al showcase ante un backend inalcanzable (sin URL, error de red, timeout de cabeceras de `FASTAPI_TIMEOUT_MS`, por defecto 3 s, o respuesta 502/504). La cabecera `x-rag-source` indica quién respondió. Ver [ADR 004](docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md).

#### Modo 2: Zero-Docker Local (solo Python)
```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python run.py                     # Linux/macOS: .venv/bin/python
```
* Por defecto `DATABASE_URL` apunta a PostgreSQL. Si no responde, la API usa `sqlite+aiosqlite:///./rag_standalone.db`.
* Para evitar el intento de conexión a PostgreSQL, define `DATABASE_URL=sqlite+aiosqlite:///./rag.db` en `.env`.
* Búsqueda vectorial exacta en Python y BM25 para la parte léxica, sin pgvector. Sin `GOOGLE_API_KEY`, los embeddings son simulados y el Golden Corpus se siembra con esos vectores.

#### Modo 3: Full Enterprise (Docker Compose)

##### Requisitos Previos
* [Docker Desktop](https://www.docker.com/) instalado y en ejecución.
* Clave de API de [Google AI Studio](https://aistudio.google.com/) (`GOOGLE_API_KEY`). Sin ella, los embeddings son simulados y el reranker usa el fallback RRF.

##### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/MattMattia/multimodal-rag-agent.git
cd multimodal-rag-agent
```

##### Paso 2: Configurar las Variables de Entorno
Copia la plantilla de entorno y edita tu `GOOGLE_API_KEY` (en PowerShell: `copy .env.example .env`):
```bash
cp .env.example .env
```
Edita `.env`:
```ini
GOOGLE_API_KEY="AIzaSy..."
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=rag_multimodal

# Observabilidad (Opcional - Langfuse)
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://langfuse:3000

# Seguridad (Opcional)
API_KEY=                        # Si se define, /api/v1/* y /uploads/reports/* exigen el header X-API-Key
ALLOWED_WEBHOOK_HOSTS=          # Hosts permitidos para webhooks http:// (https:// no lo requiere)
MAX_UPLOAD_SIZE_MB=25           # Tamaño máximo de subida; por encima responde HTTP 413
```

La tabla completa de variables está en [Variables de entorno](#variables-de-entorno).

##### Paso 3: Desplegar la Infraestructura con Docker Compose
```bash
docker compose up -d --build
```
Una vez levantado:
* **Frontend Interactivo (Streamlit):** [http://localhost:8501](http://localhost:8501)
* **API REST & Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Next.js (BFF + showcase):** [http://localhost:3001](http://localhost:3001) (servicio `web`; el puerto `3001` evita el choque con Langfuse en `:3000`)
* **Dashboard de Observabilidad (Langfuse):** [http://localhost:3000](http://localhost:3000)
* **Base de Datos PostgreSQL + pgvector:** `localhost:5432` (o `POSTGRES_PORT`)

> **Contenedores sin privilegios:** las imágenes de `api` y `frontend` se ejecutan con el usuario no-root `appuser` (uid 1000) e incluyen `HEALTHCHECK`. La imagen base de la API arranca sin `--reload`; `docker-compose.yml` lo añade solo para desarrollo.

#### GitHub Codespaces (1-Click)
El repositorio incluye `.devcontainer/devcontainer.json` para abrir un entorno de desarrollo preconfigurado en GitHub Codespaces: [https://codespaces.new/MattMattia/multimodal-rag-agent](https://codespaces.new/MattMattia/multimodal-rag-agent). Define `GOOGLE_API_KEY` como secreto de Codespaces si quieres embeddings reales.

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
| `GOOGLE_API_KEY` | vacío | Sin clave, embeddings simulados (SHA-256) y reranker en modo fallback |
| `GEMINI_AGENT_MODEL` | `gemini-1.5-pro` | Modelo del agente y del reranker |
| `GEMINI_VISION_MODEL` | `gemini-1.5-flash` | Modelo de descripción de imágenes y diagramas |
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
| `POST` | `/api/v1/agent/chat/stream` | Respuestas en Streaming en tiempo real (Server-Sent Events: `token`, `tool_end` con `duration_ms` y `diagnostics`, y `metadata` final con `diagnostics` y `duration_ms`). Ambos endpoints de chat aceptan `filter_document_id`, `search_mode`, `top_k`, `enable_rerank`, `temperature` y `max_turns` |
| `GET` | `/api/v1/agent/sessions/{session_id}/history` | Historial persistido de una conversación |
| `GET` | `/uploads/reports/{filename}` | Descarga de reportes PDF generados por el agente (exige `X-API-Key` si `API_KEY` está definida; solo sirve archivos dentro de `uploads/reports/`) |
| `GET` | `/api/v1/reports/{filename}` | Reporte PDF generado por el agente (`Content-Disposition: inline`); mismo control de contención que la ruta legada |
| `GET` | `/api/v1/documents/{id}/file` | Archivo original subido (autenticado, contenido en `uploads/documents/`) |
| `GET` | `/api/v1/documents/{id}/images/{image_id}/file` | Imagen extraída o subida (`image/png`, `image/jpeg`, `image/webp`); verifica que pertenezca al documento |
| `GET` | `/api/v1/agent/sessions` | Sesiones de chat (`session_id`, `title`, `created_at`, `updated_at`, `message_count`) por `updated_at` descendente |
| `DELETE` | `/api/v1/agent/sessions/{session_id}` | Elimina los mensajes de una sesión (`204`, o `404` si no existe) |
| `GET` | `/api/v1/agent/sessions/{session_id}/export?format=markdown\|pdf` | Exporta la conversación con citas y herramientas ejecutadas |
| `POST` | `/api/v1/agent/feedback` | Feedback `{session_id, message_id, rating: 1\|-1, comment}`; se guarda en `message_metadata` y se envía a Langfuse si está activo |
| `POST` | `/api/v1/demo/seed` | Re-siembra idempotente del Golden Corpus (genera los PDFs/PNGs que falten; sin API key no llama a Gemini) |
| `GET` | `/api/v1/demo/status` | `db_dialect`, `demo_seeded`, totales de documentos/chunks/imágenes, `gemini_configured`, `langfuse_enabled` y `active_models` |
| `POST` | `/api/v1/demo/evaluate` | Evaluación RAG `dense` vs `sparse` vs `hybrid` (RRF + reranker); ver la sección de benchmark |

### OpenAPI

El esquema OpenAPI 3.1 del backend se exporta sin arrancar el servidor:
```bash
python run.py --export-openapi   # escribe docs/openapi.json
```
El contrato versionado está en [docs/openapi.json](docs/openapi.json). Swagger UI está en `/docs` mientras la API corre.

### Benchmark de evaluación RAG

`POST /api/v1/demo/evaluate` (cuerpo opcional `{"top_k": 5}`; `409` si el corpus no está sembrado) ejecuta **8 consultas golden** contra el Golden Corpus en los modos `dense`, `sparse` e `hybrid`. Para cada modo devuelve `hit_rate_at_k`, `mrr`, `ndcg_at_k`, `avg_latency_ms` y el desglose por consulta.

> **Caveat de embeddings simulados.** Sin `GOOGLE_API_KEY`, `dense` e `hybrid` usan vectores SHA-256 deterministas. La respuesta trae `embedding_mode: "mock"`, un `warning` y `semantic: false` en esos modos. Solo `sparse` (BM25 / full-text) es significativo sin clave. Para medir calidad semántica, ejecuta el benchmark con `GOOGLE_API_KEY` definida.

Resultado offline registrado en la verificación de la fase de datos (sin `GOOGLE_API_KEY`, `top_k = 5`; medidas de hit rate y MRR, no semánticas para dense/hybrid):

| Modo | Hit rate@5 | MRR | Semántico |
|------|-----------:|----:|-----------|
| dense | 0.75 | 0.39 | No (mock) |
| sparse | 0.875 | 0.81 | Sí (BM25) |
| hybrid | 0.875 | 0.73 | No (dense mock) |

La vista **Benchmark** del web (`web/`) renderiza el informe de evaluación y su lista `warnings`, tanto si responde FastAPI como el showcase.

---

## 🧪 6. Ejecución de la Suite de Pruebas

El sistema incluye una batería de pruebas automatizadas que validan la ingesta multimodal, el chunking jerárquico, la búsqueda híbrida con RRF, el reranking semántico, el streaming SSE, la telemetría resiliente, la persistencia en base de datos, el bucle ReAct del agente, la evaluación RAG y el endurecimiento de seguridad (SSRF, subidas, autenticación, rate limit).

**Dentro de Docker:**
```bash
docker compose exec api pytest -v
```

**En local con PostgreSQL** (levanta el servicio `db` con `docker compose up -d db`; las pruebas del agente llaman a Gemini y necesitan `GOOGLE_API_KEY`):
```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest -q -p no:cacheprovider   # Linux/macOS: .venv/bin/python
```

**En local con SQLite** (sin Docker; toda la suite corre contra un archivo temporal):
```bash
TEST_DATABASE_URL=sqlite+aiosqlite:///./test_rag.db .venv/Scripts/python -m pytest -q -p no:cacheprovider   # PowerShell: $env:TEST_DATABASE_URL="sqlite+aiosqlite:///./test_rag.db"
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
└── README.md                      # Documentación ejecutiva del proyecto
```

---

## 👨‍💻 Autor y Contacto

* **Autor:** [Mattia Risso](https://github.com/MattMattia)
* **Proyecto:** Sistema RAG Multimodal & Agente IA Autónomo
* **Repositorio:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)
* **Licencia:** MIT License
