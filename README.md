# 🚀 Autonomous Multimodal RAG Agent & Knowledge Engine

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-GenAI_SDK-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker_Compose-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

**Desarrollado por [Mattia Risso](https://github.com/MattMattia)**  
🔗 **Repositorio:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)

</div>

---

## 📌 1. Visión Ejecutiva

Sistema de Inteligencia Artificial empresarial de extremo a extremo que combina un pipeline de **Ingesta y Extracción Multimodal**, **Búsqueda Híbrida Avanzada (Dense Vector + Full-Text Search)** y un **Agente IA Autónomo ReAct** con catálogo de herramientas dinámicas (Function Calling) y memoria conversacional persistente.

El sistema procesa documentos no estructurados y de alta complejidad (PDFs con maquetación heterogénea, tablas formateadas, diagramas técnicos y recibos/facturas), vectoriza el conocimiento preservando la jerarquía contextual mediante **Parent-Child Chunking**, y habilita la toma de decisiones autónoma mediante razonamiento multi-paso, generación dinámica de reportes ejecutivos en PDF y despacho de eventos vía webhooks.

---

## 🏗️ 2. Arquitectura del Sistema

```mermaid
flowchart TB
    subgraph UI ["Capa de Presentación (Frontend)"]
        Streamlit["🖥️ Streamlit Dashboard (:8501)\n• Chat Multi-Turno & Citas\n• Drag & Drop Multimodal\n• Descarga Binaria de Reportes"]
    end

    subgraph Gateway ["Capa de Aplicación (FastAPI Backend :8000)"]
        API["⚡ FastAPI API Gateway\n• REST Endpoints (/v1)\n• Background Tasks Ingestion\n• Exception Handling & Logging"]
        Repo["📦 Repository Layer (Clean Architecture)\n• DocumentRepo • ChatRepo"]
    end

    subgraph AgentEngine ["Core del Agente Autónomo (ReAct)"]
        Agent["🧠 Autonomous Agent Service\n• Gemini 1.5 Pro / 3.6 Flash Cascade\n• Thought-Action-Observation Loop\n• Citations Extractor & Validator"]
        
        subgraph ToolsCatalog ["Catálogo de Herramientas (Function Calling)"]
            T1["🔍 search_knowledge_base\n(Hybrid RAG pgvector)"]
            T2["📄 generate_report_pdf\n(ReportLab Dynamic Engine)"]
            T3["🔔 dispatch_webhook\n(HTTPX Async Dispatcher)"]
        end
    end

    subgraph MultimodalPipeline ["Pipeline de Ingesta Jerárquico"]
        PDFParser["📑 PDF Plumber & Fitz\n• Text Extraction\n• Table-to-Markdown"]
        Vision["👁️ Vision Service\n• Gemini Multimodal Image OCR\n• Technical Diagram Synthesis"]
        Chunker["🧩 Hierarchical Chunker\n• Parent Chunks (1200 chars)\n• Child Chunks (300 chars, overlap)"]
        Embedder["📐 Embedding Service\n• Google text-embedding-004 (768d)"]
    end

    subgraph DataStore ["Capa de Persistencia (PostgreSQL 16 + pgvector :5432)"]
        PGVector["🗄️ Vector Store\n• HNSW Cosine Index (document_chunks.embedding)\n• GIN Full-Text Search Index (Spanish tsvector)"]
        Relational["💾 Tablas Relacionales\n• documents • chat_messages (JSONB)"]
    end

    Streamlit <-->|HTTP REST / JSON| API
    API --> Repo
    API --> Agent
    API --> MultimodalPipeline
    
    MultimodalPipeline --> PDFParser
    MultimodalPipeline --> Vision
    MultimodalPipeline --> Chunker
    Chunker --> Embedder
    Embedder -->|Batch Insert + Vectors| PGVector

    Agent <-->|Invocación Dinámica| ToolsCatalog
    T1 <-->|Reciprocal Rank Fusion (RRF)| PGVector
    T2 -->|Almacenamiento Físico| DiskReports["📂 uploads/reports/*.pdf"]
    T3 -->|POST Event Payload| WebhookTarget["🌐 External Services / Slack"]

    Agent <-->|Historial & Sesión| Relational
```

---

## ⚙️ 3. Decisiones Clave de Ingeniería

### 1. Chunking Jerárquico Parent-Child
* **Desafío:** Los fragmentos pequeños maximizan la precisión semántica en la recuperación vectorial, pero pierden el contexto global necesario para que el LLM genere respuestas coherentes.
* **Solución:** Se implementó una estrategia en dos niveles:
  * **Child Chunks (250–300 caracteres, solapamiento de 50):** Utilizados como vectores de búsqueda granular en el índice vectorial.
  * **Parent Chunks (1000–1500 caracteres):** Cada fragmento hijo almacena un puntero `parent_id`. Al recuperarse un fragmento hijo relevante, el sistema expande automáticamente el texto al fragmento padre antes de sintetizar la respuesta final.

### 2. Búsqueda Híbrida Unificada con Reciprocal Rank Fusion (RRF)
* **Desafío:** La búsqueda puramente vectorial falla ante consultas con números de serie, acrónimos técnicos específicos o identificadores fiscales; la búsqueda léxica (BM25) ignora la semántica.
* **Solución:** Fusión bilingüe ejecutada en PostgreSQL:
  * **Búsqueda Vectorial Densa:** Distancia coseno sobre embeddings de 768 dimensiones optimizada con índices **HNSW** (`vector_cosine_ops`).
  * **Búsqueda Léxica Esparsa:** Motor de texto completo PostgreSQL con diccionarios en español e índices **GIN** (`to_tsvector`).
  * **RRF ($k = 60$):** Algoritmo de normalización no supervisado que combina los rankings sin requerir calibración manual de pesos:
    $$\text{Score}_{RRF}(d) = \sum_{m \in \{\text{vector}, \text{lexical}\}} \frac{1}{k + \text{rank}_m(d)}$$

### 3. Memoria Conversacional Persistente en Base de Datos
* **Desafío:** Pérdida de contexto en chats multi-turno sin saturar la ventana de contexto del LLM con llamadas redundantes a herramientas.
* **Solución:** Modelo relacional `ChatMessage` en PostgreSQL con almacenamiento estructurado en `JSONB` para `citations` y `executed_tools`. En turnos posteriores (ej. *"tradúcelo al inglés"* o *"resume lo anterior"*), el agente analiza la memoria de la sesión y resuelve la instrucción sin disparar consultas RAG redundantes.

### 4. Cascada de Resiliencia y Auto-Promoción de Modelos
* **Desafío:** Variaciones de cuota, spikes de latencia y deprecaciones en modelos de la API de Google (errores `404 NOT_FOUND` o `429 RESOURCE_EXHAUSTED`).
* **Solución:** Módulo con cascada transparente (`_call_gemini_with_fallback`):
  * Prioriza el modelo configurado (`gemini-1.5-pro` / `gemini-1.5-flash`).
  * Si la API notifica indisponibilidad, promueve la ejecución a variantes de alta velocidad con cuota estable (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`).
  * Recuerda el modelo operativo para el resto de la sesión y cuenta con respaldo de contingencia con trazabilidad explícita (`logger.error`).

### 5. Reportes PDF Dinámicos con ReportLab
* **Desafío:** Generación de informes sin recurrir a plantillas fijas estáticas.
* **Solución:** La herramienta `generate_report_pdf` recibe argumentos dinámicos formulados por el LLM tras analizar el corpus: título contextualizado, síntesis ejecutiva estructurada y puntos de acción concretos, entregando el archivo listo para descarga directa.

---

## 🚀 4. Guía de Inicio Rápido (3 Pasos)

### Requisitos Previos
* [Docker Desktop](https://www.docker.com/) instalado y en ejecución.
* Clave de API de [Google AI Studio](https://aistudio.google.com/) (`GOOGLE_API_KEY`).

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/MattMattia/multimodal-rag-agent.git
cd multimodal-rag-agent
```

### Paso 2: Configurar las Variables de Entorno
Copia la plantilla de entorno y edita tu `GOOGLE_API_KEY`:
```bash
cp .env.example .env
```
Edita `.env`:
```ini
GOOGLE_API_KEY="AIzaSy..."
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=rag_multimodal
```

### Paso 3: Desplegar la Infraestructura con Docker Compose
```bash
docker compose up -d --build
```
Una vez levantado:
* **Frontend Interactivo (Streamlit):** [http://localhost:8501](http://localhost:8501)
* **API REST & Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Base de Datos PostgreSQL + pgvector:** `localhost:5432`

---

## 📡 5. Catálogo de Endpoints de la API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Healthcheck del backend y estado de la base de datos |
| `POST` | `/api/v1/documents/upload` | Ingesta de archivos PDF/Imágenes (procesamiento asíncrono) |
| `GET` | `/api/v1/documents` | Listado de documentos indexados con estado y recuento de chunks |
| `GET` | `/api/v1/documents/{id}` | Detalle de un documento y fragmentos generados |
| `POST` | `/api/v1/search` | Búsqueda Híbrida (`query`, `limit`, filtros de metadata) |
| `POST` | `/api/v1/agent/chat` | Interacción multi-turno con el Agente Autónomo ReAct |
| `POST` | `/api/v1/agent/chat/stream` | Respuestas en Streaming en tiempo real (Server-Sent Events) |
| `GET` | `/api/v1/agent/sessions/{session_id}/history` | Historial persistido de una conversación |
| `GET` | `/uploads/reports/{filename}` | Descarga de reportes PDF generados por el agente |

---

## 🧪 6. Ejecución de la Suite de Pruebas

El sistema incluye una batería exhaustiva de **19 pruebas automatizadas** que validan la ingesta multimodal, el chunking jerárquico, la búsqueda híbrida con RRF, el streaming SSE, la persistencia en base de datos y el bucle ReAct del agente:

```bash
docker compose exec api pytest -v
```

**Resultado de Ejecución:**
```
tests/test_agent.py::test_generate_report_pdf PASSED                     [  5%]
tests/test_agent.py::test_dispatch_webhook PASSED                        [ 10%]
tests/test_agent.py::test_agent_execution_turn PASSED                    [ 15%]
tests/test_agent.py::test_agent_chat_endpoint PASSED                     [ 21%]
tests/test_agent.py::test_agent_chat_stream_endpoint PASSED              [ 26%]
tests/test_agent.py::test_gemini_model_configuration PASSED              [ 31%]
tests/test_agent.py::test_chat_session_memory_persistence PASSED         [ 36%]
tests/test_documents.py::test_table_to_markdown PASSED                   [ 42%]
tests/test_documents.py::test_table_to_markdown_empty PASSED             [ 47%]
tests/test_documents.py::test_hierarchical_chunker PASSED                [ 52%]
tests/test_documents.py::test_upload_unsupported_format PASSED           [ 57%]
tests/test_documents.py::test_vision_placeholder_without_key PASSED      [ 63%]
tests/test_health.py::test_root_endpoint PASSED                          [ 68%]
tests/test_health.py::test_root_health_endpoint PASSED                   [ 73%]
tests/test_search.py::test_embedding_dimensions PASSED                   [ 78%]
tests/test_search.py::test_embedding_batch_generation PASSED             [ 84%]
tests/test_search.py::test_reciprocal_rank_fusion_logic PASSED           [ 89%]
tests/test_search.py::test_search_endpoint_validation PASSED             [ 94%]
tests/test_search.py::test_search_endpoint_hybrid PASSED                 [100%]

============================= 19 passed in 57.59s ==============================
```

---

## 📂 7. Estructura del Código

```
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── agent.py       # Endpoints de chat y consulta de historial
│   │       │   ├── documents.py   # Ingesta, subida y consulta documental
│   │       │   ├── health.py      # Monitoreo y readiness checks
│   │       │   └── search.py      # Búsqueda híbrida vectorial + texto
│   │       └── router.py          # Enrutador centralizado v1
│   ├── core/
│   │   ├── config.py              # Pydantic BaseSettings (variables de entorno)
│   │   └── database.py            # Engine asyncpg, SessionMaker e inicialización DDL
│   ├── models/                    # Modelos ORM SQLAlchemy
│   │   ├── chat.py                # ChatMessage (memoria relacional JSONB)
│   │   └── document.py            # Document, DocumentChunk (pgvector), DocumentImage
│   ├── repositories/              # Abstracción de acceso a datos
│   │   ├── chat_repository.py
│   │   └── document_repository.py
│   ├── schemas/                   # Esquemas de validación y serialización Pydantic v2
│   │   ├── agent.py
│   │   ├── document.py
│   │   └── search.py
│   ├── services/                  # Lógica de negocio nuclear
│   │   ├── agent.py               # Orquestador del Agente ReAct & Gemini Cascade
│   │   ├── embedding.py           # Servicio de vectorización (text-embedding-004)
│   │   ├── hybrid_search.py       # Algoritmo RRF sobre HNSW + GIN Full-Text
│   │   ├── ingestion.py           # Pipeline de extracción, OCR y chunking jerárquico
│   │   └── vision.py              # Extracción visual de diagramas y facturas
│   ├── tools/                     # Herramientas ejecutables por el Agente
│   │   ├── pdf_generator.py       # Generador de informes PDF con ReportLab
│   │   ├── search_tool.py         # Interfaz a la base de datos vectorial
│   │   └── webhook_tool.py        # Disparador asíncrono de webhooks HTTP
│   └── main.py                    # Punto de entrada de la aplicación FastAPI
├── docker/
│   └── init.sql                   # Extensiones PostgreSQL (uuid-ossp, vector)
├── frontend/
│   ├── app.py                     # Dashboard de usuario en Streamlit
│   ├── Dockerfile
│   └── requirements.txt
├── tests/                         # Batería de pruebas unitarias y de integración
├── docker-compose.yml             # Orquestación multicontenedor
├── Dockerfile                     # Imagen de backend optimizada
├── requirements.txt               # Dependencias Python
└── README.md                      # Documentación ejecutiva del proyecto
```

---

## 👨‍💻 Autor y Contacto

* **Autor:** [Mattia Risso](https://github.com/MattMattia)
* **Proyecto:** Sistema RAG Multimodal & Agente IA Autónomo
* **Repositorio:** [https://github.com/MattMattia/multimodal-rag-agent](https://github.com/MattMattia/multimodal-rag-agent)
* **Licencia:** MIT License
