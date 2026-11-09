"""Textos localizados (es/en) del backend: etiquetas de exportación, contingencia del agente y avisos de evaluación.

Módulo puro y sin dependencias: lo reutilizan PDF, Markdown, el agente y la evaluación.
"""

import re
from typing import Literal

Lang = Literal["es", "en"]
DEFAULT_LANG: Lang = "es"

# Etiquetas de exportación (PDF y Markdown). Las claves son estables; los valores dependen del idioma.
LABELS: dict[str, dict[str, str]] = {
    "es": {
        "executive_summary": "Resumen Ejecutivo",
        "key_takeaways": "Puntos Clave",
        "generated_on": "Generado el",
        "session_export": "Exportación de Sesión",
        "user": "Usuario",
        "agent": "Agente",
        "cited_sources": "Fuentes Citadas",
        "executed_tools": "Herramientas ejecutadas",
        "tool": "Herramienta",
        "page": "Pág",
        "session": "Sesión",
        "section": "Sección",
        "report_brand": "Agente IA Autónomo",
        "report_footer": "Sistema RAG Multimodal & Agente IA Autónomo - Documento Confidencial",
        "report_prefix": "reporte",
        "report_default_title": "Reporte Ejecutivo",
        "report_default_summary": "Sin resumen.",
        "report_generated_msg": "Reporte PDF '{title}' generado exitosamente.",
    },
    "en": {
        "executive_summary": "Executive Summary",
        "key_takeaways": "Key Takeaways",
        "generated_on": "Generated on",
        "session_export": "Session Export",
        "user": "User",
        "agent": "Agent",
        "cited_sources": "Cited Sources",
        "executed_tools": "Executed tools",
        "tool": "Tool",
        "page": "Page",
        "session": "Session",
        "section": "Section",
        "report_brand": "Autonomous AI Agent",
        "report_footer": "Multimodal RAG System & Autonomous AI Agent - Confidential Document",
        "report_prefix": "report",
        "report_default_title": "Executive Report",
        "report_default_summary": "No summary.",
        "report_generated_msg": "PDF report '{title}' generated successfully.",
    },
}

# Texto sintetizado por el motor de contingencia del agente.
FALLBACK: dict[str, dict[str, str]] = {
    "es": {
        "search_failed": "⚠️ No se pudo consultar la base de conocimientos: {error}\n",
        "retrieved": "De acuerdo con la información recuperada de los documentos{source_tag}:\n\n{context}...",
        "processed": "He procesado tu solicitud: '{message}'.",
        "pdf_done": "\n📄 Se ha generado el informe ejecutivo en PDF: [{filename}]({url}).",
        "webhook_done": "\n🔔 Se ha despachado la notificación vía webhook: {message}.",
        "source_tag": " [Fuente: {document}, Pág {page}]",
        "pdf_title_default": "Informe Ejecutivo de Conocimiento",
        "pdf_title_audit": "Informe de Auditoría de Sistemas y Estado Financiero",
        "pdf_title_profile": "Perfil Profesional y Habilidades de Mattia Risso",
        "pdf_summary_ctx": "Síntesis ejecutiva de la información documental analizada: {context}",
        "pdf_point_verified": "Información verificada: {context}...",
        "pdf_point_contrasted": "Datos contrastados contra las fuentes documentales indexadas en pgvector.",
        "pdf_point_analysis": "Análisis estructurado y preparado para toma de decisiones ejecutivas.",
        "pdf_summary_query": "Informe correspondiente a la consulta: '{message}'.",
        "pdf_point_search": "Búsqueda ejecutada en la base de conocimientos documental.",
        "pdf_point_validation": "Validación de registros completada satisfactoriamente.",
        "gemini_notice": (
            "⚠️ [Aviso del sistema: La API de Gemini no respondió temporalmente ({error_type}: {error}...). "
            "Se ejecutó el procesamiento documental con el motor de contingencia.]\n\n"
        ),
        "gemini_notice_stream": (
            "⚠️ [Aviso del sistema: La API de Gemini no respondió ({error_type}: {error}...). "
            "Se ejecutó el procesamiento documental con el motor de contingencia.]\n\n"
        ),
        "stream_separator": "\n\n[Se cambió al motor de contingencia]\n\n",
    },
    "en": {
        "search_failed": "⚠️ Could not query the knowledge base: {error}\n",
        "retrieved": "Based on the information retrieved from the documents{source_tag}:\n\n{context}...",
        "processed": "I have processed your request: '{message}'.",
        "pdf_done": "\n📄 The executive PDF report has been generated: [{filename}]({url}).",
        "webhook_done": "\n🔔 The webhook notification has been dispatched: {message}.",
        "source_tag": " [Source: {document}, Page {page}]",
        "pdf_title_default": "Executive Knowledge Report",
        "pdf_title_audit": "Systems Audit and Financial Status Report",
        "pdf_title_profile": "Professional Profile and Skills of Mattia Risso",
        "pdf_summary_ctx": "Executive synthesis of the analyzed document information: {context}",
        "pdf_point_verified": "Verified information: {context}...",
        "pdf_point_contrasted": "Data cross-checked against the document sources indexed in pgvector.",
        "pdf_point_analysis": "Structured analysis ready for executive decision-making.",
        "pdf_summary_query": "Report for the query: '{message}'.",
        "pdf_point_search": "Search executed against the document knowledge base.",
        "pdf_point_validation": "Record validation completed successfully.",
        "gemini_notice": (
            "⚠️ [System notice: The Gemini API did not respond in time ({error_type}: {error}...). "
            "Document processing was run with the contingency engine.]\n\n"
        ),
        "gemini_notice_stream": (
            "⚠️ [System notice: The Gemini API did not respond ({error_type}: {error}...). "
            "Document processing was run with the contingency engine.]\n\n"
        ),
        "stream_separator": "\n\n[Switched to the contingency engine]\n\n",
    },
}

# Advertencia del informe de evaluación cuando los embeddings son simulados.
EVAL_MOCK_WARNING: dict[str, str] = {
    "es": (
        "Embeddings simulados: los puntajes de dense y hybrid provienen de vectores determinísticos SHA-256 "
        "(mock) y no miden calidad semántica; solo sparse (BM25) es significativo sin GOOGLE_API_KEY."
    ),
    "en": (
        "Simulated embeddings: dense and hybrid scores come from deterministic SHA-256 vectors "
        "(mock) and do not measure semantic quality; only sparse (BM25) is meaningful without GOOGLE_API_KEY."
    ),
}

_LANGUAGE_INSTRUCTION: dict[str, str] = {
    "es": "IDIOMA DE RESPUESTA: responde SIEMPRE en español, independientemente del idioma de los documentos.",
    "en": (
        "RESPONSE LANGUAGE: ALWAYS answer in English, regardless of the language of the documents or of the "
        "rules above that mention Spanish. Keep tool names and JSON keys unchanged."
    ),
}

_ES_WORDS = frozenset(
    "el la los las un una unos unas de del que qué y o en es son por para con sin como cómo cuál cuáles cuánto "
    "cuántos quién quiénes dónde cuándo mi tu su se lo al más muy pero también esto esta este estos estas "
    "hola gracias dame genera genéralo resume explica tiene hay fue está están puedes puede hacer sobre".split()
)
_EN_WORDS = frozenset(
    "the a an of and or in is are was were to for with without what which who whom where when why how my your "
    "his her its it this that these those do does did can could would should hello hi thanks please give "
    "generate summarize explain has have had about from be been not but also".split()
)
_WORD_RE = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)
_SPANISH_MARKS_RE = re.compile(r"[¿¡áéíóúñü]", re.IGNORECASE)


def normalize_lang(value: str | None) -> Lang:
    """Devuelve 'en' solo si se pide explícitamente; cualquier otro valor cae al idioma por defecto."""
    return "en" if value == "en" else DEFAULT_LANG


def detect_language(text: str) -> Lang:
    """Heurística determinística: signos ¿¡, acentos y stopwords. Empate o texto indecidible -> 'es'."""
    if not text or not text.strip():
        return DEFAULT_LANG
    es_score = len(_SPANISH_MARKS_RE.findall(text)) * 2
    en_score = 0
    for word in _WORD_RE.findall(text.lower()):
        if word in _ES_WORDS:
            es_score += 1
        if word in _EN_WORDS:
            en_score += 1
    return "en" if en_score > es_score else DEFAULT_LANG


def resolve_language(requested: str | None, text: str) -> Lang:
    """Idioma efectivo: 'es'/'en' explícito se respeta; 'auto' (o ausente) se detecta desde el mensaje."""
    if requested in ("es", "en"):
        return normalize_lang(requested)
    return detect_language(text)


def labels(lang: str | None) -> dict[str, str]:
    return LABELS[normalize_lang(lang)]


def fallback_texts(lang: str | None) -> dict[str, str]:
    return FALLBACK[normalize_lang(lang)]


def language_instruction(lang: str | None) -> str:
    return _LANGUAGE_INSTRUCTION[normalize_lang(lang)]
