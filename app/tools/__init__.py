"""Catálogo de herramientas (tools) para el Agente IA Autónomo."""

# Import the services package first: it imports app.tools.* itself, so entering through app.tools
# would otherwise hit a partially initialised app.tools.rag_tool (circular import).
import app.services  # noqa: F401,I001
from app.tools.pdf_generator import execute_generate_report_pdf
from app.tools.rag_tool import execute_search_knowledge_base
from app.tools.webhook_tool import execute_dispatch_webhook

__all__ = [
    "execute_search_knowledge_base",
    "execute_generate_report_pdf",
    "execute_dispatch_webhook",
]
