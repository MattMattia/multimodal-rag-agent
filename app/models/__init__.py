"""Modelos ORM de SQLAlchemy para tablas relacionales y vectores."""

from app.core.database import Base
from app.models.chat import ChatMessage
from app.models.document import Document, DocumentChunk, DocumentImage

__all__ = ["Base", "ChatMessage", "Document", "DocumentChunk", "DocumentImage"]
