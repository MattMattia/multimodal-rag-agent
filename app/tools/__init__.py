"""Catálogo de herramientas (tools) para el Agente IA Autónomo."""

from app.tools.pdf_generator import execute_generate_report_pdf
from app.tools.rag_tool import execute_search_knowledge_base
from app.tools.webhook_tool import execute_dispatch_webhook

__all__ = [
    "execute_search_knowledge_base",
    "execute_generate_report_pdf",
    "execute_dispatch_webhook",
]
