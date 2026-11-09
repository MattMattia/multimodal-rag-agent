"""Spanish/English UI strings for the Streamlit dashboard.

`t(key, **kwargs)` resolves `key` in the active language (`st.session_state["lang"]`,
Spanish by default), falls back to Spanish and then to the key itself, and formats
interpolated values with `str.format` when keyword arguments are given.
"""

from typing import Any

import streamlit as st

DEFAULT_LANG = "es"
LANG_KEY = "lang"
LANGUAGES = {"es": "🇪🇸 Español", "en": "🇺🇸 English"}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {
        # ------------------------------------------------------------------ app shell
        "page_title": "RAG Multimodal & Agente IA Autónomo",
        "lang_label": "🌐 Idioma / Language",
        "sidebar_title": "⚙️ Panel de Control",
        "sidebar_caption": "Sistema RAG Multimodal & Agente IA",
        "api_ok": "🟢 **API Conectada** ({environment})",
        "api_down": "🔴 **API No Disponible** (Verifica contenedor `rag_api`)",
        "main_title": "🤖 Agente IA Autónomo & RAG Multimodal",
        "main_subtitle": (
            "Motor con razonamiento ReAct, búsqueda híbrida (pgvector / SQLite), "
            "generación de informes ejecutivos en PDF y memoria conversacional persistente."
        ),
        "view_label": "Vista",
        "view_chat": "Chat",
        "view_search": "Búsqueda RAG",
        "view_benchmark": "Benchmark Lab",
        "examples_title": "💡 Ejemplos de instrucciones para interactuar con el agente",
        "example_data": "🔍 **Consulta de Datos / CVs:**\n\n'¿Quién es Mattia Risso y qué experiencia técnica tiene?'",
        "example_report": (
            "📄 **Generación de Reportes:**\n\n"
            "'Genera un reporte PDF con el resumen ejecutivo de la auditoría y sus conclusiones.'"
        ),
        "example_webhook": (
            "🔔 **Notificación / Webhook:**\n\n'Notifica por webhook que se aprobó la factura INV-1002 por $1500.'"
        ),
        "chat_placeholder": "Escribe tu consulta o instrucción para el Agente IA...",
        # ------------------------------------------------------------------ sidebar: sessions
        "session_deleted": "Sesión eliminada.",
        "session_delete_failed": "No se pudo eliminar la sesión: {error}",
        "session_new": "Nueva sesión (sin mensajes)",
        "session_untitled": "Sin título",
        "session_label": "{title} · {count} msgs",
        "sessions_header": "Sesiones",
        "sessions_unavailable": "El listado de sesiones no está disponible en esta API.",
        "session_active": "Sesión activa",
        "session_btn_new": "Nueva",
        "session_btn_delete": "Eliminar",
        "session_id": "ID: `{session_id}`",
        # ------------------------------------------------------------------ sidebar: hyperparameters
        "hp_title": "Hiperparámetros del agente",
        "hp_search_mode": "Modo de búsqueda",
        "hp_top_k": "Fragmentos (top_k)",
        "hp_rerank": "Reranking semántico",
        "hp_override": "Personalizar temperatura y turnos",
        "hp_temperature": "Temperatura",
        "hp_max_turns": "Máx. iteraciones ReAct",
        "hp_doc_filter": "Restringir a documento",
        "hp_all_docs": "Todos los documentos",
        # ------------------------------------------------------------------ sidebar: golden corpus
        "corpus_header": "Golden Corpus",
        "corpus_restored": (
            "Golden Corpus restaurado: {created} documentos nuevos, {skipped} existentes ({duration} ms)."
        ),
        "corpus_restore_failed": "No se pudo restaurar el Golden Corpus: {error}",
        "corpus_seeded": "Sembrado",
        "corpus_unseeded": "Sin sembrar",
        "corpus_status": "**{seeded}** · BD `{db}` · embeddings `{embeddings}`",
        "corpus_counts": "{documents} documentos · {chunks} chunks · {images} imágenes",
        "corpus_status_unavailable": "Estado del demo no disponible ({error}).",
        "corpus_restore_btn": "Restaurar Golden Corpus",
        # ------------------------------------------------------------------ sidebar: ingestion / catalog
        "ingest_header": "Ingesta de documentos",
        "ingest_caption": "Sube PDFs o imágenes (facturas, diagramas, CVs).",
        "ingest_uploader": "Selecciona un archivo",
        "ingest_btn": "Subir e indexar",
        "ingest_spinner": "Ingestando '{name}'...",
        "ingest_ok": "Archivo subido y encolado para procesamiento.",
        "ingest_failed": "Error al subir: {error}",
        "catalog_header": "Documentos en base de datos",
        "catalog_refresh": "Actualizar documentos",
        "catalog_empty": "No hay documentos indexados aún.",
        "catalog_total": "Total indexados: {count}",
        "doc_type": "**Tipo:** {value}",
        "doc_status": "**Estado:** `{value}`",
        "doc_chunks": "**Fragmentos (Chunks):** {value}",
        "doc_date": "**Fecha:** {value}",
        # ------------------------------------------------------------------ chat
        "citations_title": "📚 Fuentes y Citas ({count})",
        "citation_document": "Documento",
        "citation_page": "Pág. {page}",
        "citation_page_na": "Pág. N/D",
        "citation_type": "Tipo",
        "tools_title": "🛠️ Herramientas Ejecutadas ({count})",
        "tool_input": "Entrada",
        "tool_output": "Salida",
        "report_filename": "reporte.pdf",
        "report_download": "📥 Descargar {filename}",
        "feedback_thanks": "Gracias por tu valoración.",
        "feedback_failed": "No se pudo registrar la valoración: {error}",
        "xray_title": "🩻 Rayos X de latencia",
        "xray_last_turn": "🩻 Rayos X del último turno",
        "agent_error": "Error al comunicar con el agente: {error}",
        # ------------------------------------------------------------------ search lab
        "search_header": "Búsqueda RAG directa",
        "search_caption": "Ejecuta la búsqueda híbrida sin el agente, con los hiperparámetros del panel lateral.",
        "search_query": "Consulta",
        "search_btn": "Buscar",
        "search_spinner": "Buscando...",
        "search_error": "Error en la búsqueda: {error}",
        "search_empty": "Sin resultados.",
        "col_document": "Documento",
        "col_page": "Pág.",
        "col_type": "Tipo",
        "col_content": "Contenido",
        "search_alt": "Fragmentos recuperados",
        # ------------------------------------------------------------------ benchmark lab
        "bench_header": "Benchmark Lab",
        "bench_caption": "Compara las modalidades dense, sparse e hybrid sobre las consultas doradas del Golden Corpus.",
        "bench_k": "Ventana k",
        "bench_run": "Ejecutar benchmark",
        "bench_spinner": "Evaluando las tres modalidades...",
        "bench_hint_unseeded": " Restaura el Golden Corpus desde el panel lateral.",
        "bench_error": "No se pudo ejecutar el benchmark: {error}.{hint}",
        "bench_empty": "Ejecuta el benchmark para ver las métricas.",
        "bench_meta": "k = {k} · {queries} consultas",
        "bench_no_modes": "La evaluación no devolvió modalidades.",
        "bench_summary_alt": "Resumen de métricas por modo",
        "bench_quality": "Calidad de recuperación",
        "bench_quality_alt": "Hit rate, MRR y NDCG por modo",
        "bench_latency": "Latencia media",
        "bench_latency_alt": "Latencia media por modo de búsqueda",
        "bench_per_query": "Desglose por consulta",
        "bench_per_query_alt": "Resultados por consulta en modo {mode}",
        "bench_col_mode": "Modo",
        "bench_col_latency": "Latencia media (ms)",
        "bench_col_semantic": "Semántico",
        "bench_col_metric": "Métrica",
        "bench_col_value": "Valor",
        "yes": "Sí",
        "no": "No",
        "emb_unknown": "desconocido",
        "emb_title": "Embeddings: {mode}",
        "emb_gemini": "Las métricas densas e híbridas usan embeddings reales de Gemini.",
        "emb_mock": "Los vectores son determinísticos y no semánticos: las métricas densas no reflejan calidad real.",
        # ------------------------------------------------------------------ latency x-ray
        "stage_embedding": "Embedding",
        "stage_dense": "Densa (vector)",
        "stage_sparse": "Léxica (BM25)",
        "stage_rrf": "Fusión RRF",
        "stage_rerank": "Reranking",
        "diag_col_stage": "Etapa",
        "diag_none": "Sin diagnósticos de latencia para esta respuesta.",
        "diag_search_total": "Búsqueda total",
        "diag_turn_total": "Turno completo",
        "diag_database": "Base de datos",
        "diag_candidates": "Candidatos / bloques",
        "diag_x_label": "Milisegundos",
        "diag_alt": "Latencia por etapa de la búsqueda RAG",
        "diag_col_tool": "Herramienta",
        "diag_col_duration": "Duración",
        "diag_tools_alt": "Duración de cada herramienta ejecutada",
        # ------------------------------------------------------------------ api client
        "err_connection": "Error de conexión: {error}",
        "err_non_json": "Respuesta no JSON del servidor",
        "err_stream_server": "⚠️ Error del servidor ({status}): {text}",
        "err_stream_connection": "\n\n⚠️ Error de conexión durante la transmisión en streaming: {error}",
    },
    "en": {
        # ------------------------------------------------------------------ app shell
        "page_title": "Multimodal RAG & Autonomous AI Agent",
        "lang_label": "🌐 Idioma / Language",
        "sidebar_title": "⚙️ Control Panel",
        "sidebar_caption": "Multimodal RAG System & AI Agent",
        "api_ok": "🟢 **API Connected** ({environment})",
        "api_down": "🔴 **API Unavailable** (Check the `rag_api` container)",
        "main_title": "🤖 Autonomous AI Agent & Multimodal RAG",
        "main_subtitle": (
            "Engine with ReAct reasoning, hybrid search (pgvector / SQLite), "
            "executive PDF report generation and persistent conversational memory."
        ),
        "view_label": "View",
        "view_chat": "Chat",
        "view_search": "RAG Search",
        "view_benchmark": "Benchmark Lab",
        "examples_title": "💡 Example instructions to interact with the agent",
        "example_data": "🔍 **Data / CV Lookup:**\n\n'Who is Mattia Risso and what technical experience does he have?'",
        "example_report": (
            "📄 **Report Generation:**\n\n"
            "'Generate a PDF report with the executive summary of the audit and its conclusions.'"
        ),
        "example_webhook": (
            "🔔 **Notification / Webhook:**\n\n'Notify via webhook that invoice INV-1002 for $1500 was approved.'"
        ),
        "chat_placeholder": "Type your question or instruction for the AI Agent...",
        # ------------------------------------------------------------------ sidebar: sessions
        "session_deleted": "Session deleted.",
        "session_delete_failed": "Could not delete the session: {error}",
        "session_new": "New session (no messages)",
        "session_untitled": "Untitled",
        "session_label": "{title} · {count} msgs",
        "sessions_header": "Sessions",
        "sessions_unavailable": "Session listing is not available in this API.",
        "session_active": "Active session",
        "session_btn_new": "New",
        "session_btn_delete": "Delete",
        "session_id": "ID: `{session_id}`",
        # ------------------------------------------------------------------ sidebar: hyperparameters
        "hp_title": "Agent hyperparameters",
        "hp_search_mode": "Search mode",
        "hp_top_k": "Chunks (top_k)",
        "hp_rerank": "Semantic reranking",
        "hp_override": "Customize temperature and turns",
        "hp_temperature": "Temperature",
        "hp_max_turns": "Max ReAct iterations",
        "hp_doc_filter": "Restrict to document",
        "hp_all_docs": "All documents",
        # ------------------------------------------------------------------ sidebar: golden corpus
        "corpus_header": "Golden Corpus",
        "corpus_restored": "Golden Corpus restored: {created} new documents, {skipped} existing ({duration} ms).",
        "corpus_restore_failed": "Could not restore the Golden Corpus: {error}",
        "corpus_seeded": "Seeded",
        "corpus_unseeded": "Not seeded",
        "corpus_status": "**{seeded}** · DB `{db}` · embeddings `{embeddings}`",
        "corpus_counts": "{documents} documents · {chunks} chunks · {images} images",
        "corpus_status_unavailable": "Demo status unavailable ({error}).",
        "corpus_restore_btn": "Restore Golden Corpus",
        # ------------------------------------------------------------------ sidebar: ingestion / catalog
        "ingest_header": "Document ingestion",
        "ingest_caption": "Upload PDFs or images (invoices, diagrams, CVs).",
        "ingest_uploader": "Select a file",
        "ingest_btn": "Upload and index",
        "ingest_spinner": "Ingesting '{name}'...",
        "ingest_ok": "File uploaded and queued for processing.",
        "ingest_failed": "Upload error: {error}",
        "catalog_header": "Documents in database",
        "catalog_refresh": "Refresh documents",
        "catalog_empty": "No documents indexed yet.",
        "catalog_total": "Total indexed: {count}",
        "doc_type": "**Type:** {value}",
        "doc_status": "**Status:** `{value}`",
        "doc_chunks": "**Chunks:** {value}",
        "doc_date": "**Date:** {value}",
        # ------------------------------------------------------------------ chat
        "citations_title": "📚 Sources and Citations ({count})",
        "citation_document": "Document",
        "citation_page": "p. {page}",
        "citation_page_na": "p. N/A",
        "citation_type": "Type",
        "tools_title": "🛠️ Executed Tools ({count})",
        "tool_input": "Input",
        "tool_output": "Output",
        "report_filename": "report.pdf",
        "report_download": "📥 Download {filename}",
        "feedback_thanks": "Thanks for your rating.",
        "feedback_failed": "Could not record the rating: {error}",
        "xray_title": "🩻 Latency X-ray",
        "xray_last_turn": "🩻 Last turn X-ray",
        "agent_error": "Error communicating with the agent: {error}",
        # ------------------------------------------------------------------ search lab
        "search_header": "Direct RAG search",
        "search_caption": "Runs the hybrid search without the agent, using the sidebar hyperparameters.",
        "search_query": "Query",
        "search_btn": "Search",
        "search_spinner": "Searching...",
        "search_error": "Search error: {error}",
        "search_empty": "No results.",
        "col_document": "Document",
        "col_page": "Page",
        "col_type": "Type",
        "col_content": "Content",
        "search_alt": "Retrieved chunks",
        # ------------------------------------------------------------------ benchmark lab
        "bench_header": "Benchmark Lab",
        "bench_caption": "Compares the dense, sparse and hybrid modes over the Golden Corpus golden queries.",
        "bench_k": "Window k",
        "bench_run": "Run benchmark",
        "bench_spinner": "Evaluating the three modes...",
        "bench_hint_unseeded": " Restore the Golden Corpus from the sidebar.",
        "bench_error": "Could not run the benchmark: {error}.{hint}",
        "bench_empty": "Run the benchmark to see the metrics.",
        "bench_meta": "k = {k} · {queries} queries",
        "bench_no_modes": "The evaluation returned no modes.",
        "bench_summary_alt": "Metrics summary by mode",
        "bench_quality": "Retrieval quality",
        "bench_quality_alt": "Hit rate, MRR and NDCG by mode",
        "bench_latency": "Average latency",
        "bench_latency_alt": "Average latency by search mode",
        "bench_per_query": "Per-query breakdown",
        "bench_per_query_alt": "Per-query results in {mode} mode",
        "bench_col_mode": "Mode",
        "bench_col_latency": "Average latency (ms)",
        "bench_col_semantic": "Semantic",
        "bench_col_metric": "Metric",
        "bench_col_value": "Value",
        "yes": "Yes",
        "no": "No",
        "emb_unknown": "unknown",
        "emb_title": "Embeddings: {mode}",
        "emb_gemini": "Dense and hybrid metrics use real Gemini embeddings.",
        "emb_mock": "Vectors are deterministic and non-semantic: dense metrics do not reflect real quality.",
        # ------------------------------------------------------------------ latency x-ray
        "stage_embedding": "Embedding",
        "stage_dense": "Dense (vector)",
        "stage_sparse": "Lexical (BM25)",
        "stage_rrf": "RRF fusion",
        "stage_rerank": "Reranking",
        "diag_col_stage": "Stage",
        "diag_none": "No latency diagnostics for this response.",
        "diag_search_total": "Total search",
        "diag_turn_total": "Full turn",
        "diag_database": "Database",
        "diag_candidates": "Candidates / blocks",
        "diag_x_label": "Milliseconds",
        "diag_alt": "Latency per RAG search stage",
        "diag_col_tool": "Tool",
        "diag_col_duration": "Duration",
        "diag_tools_alt": "Duration of each executed tool",
        # ------------------------------------------------------------------ api client
        "err_connection": "Connection error: {error}",
        "err_non_json": "Non-JSON response from the server",
        "err_stream_server": "⚠️ Server error ({status}): {text}",
        "err_stream_connection": "\n\n⚠️ Connection error during streaming: {error}",
    },
}


def current_lang() -> str:
    """Active UI language code (`"es"` or `"en"`); unknown values fall back to Spanish."""
    lang = st.session_state.get(LANG_KEY, DEFAULT_LANG)
    return lang if lang in TRANSLATIONS else DEFAULT_LANG


def t(key: str, **kwargs: Any) -> str:
    """Translated text for `key` in the active language, formatted with `kwargs` when given."""
    text = TRANSLATIONS[current_lang()].get(key) or TRANSLATIONS[DEFAULT_LANG].get(key) or key
    return text.format(**kwargs) if kwargs else text
