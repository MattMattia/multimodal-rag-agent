import uuid
from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.config import settings
from app.core.database import Base


class Document(Base):
    """Modelo ORM que representa un documento cargado en el sistema."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )  # 'pending', 'processing', 'completed', 'failed'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False
    )

    # Relaciones
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.created_at",
    )
    images: Mapped[list["DocumentImage"]] = relationship(
        "DocumentImage",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentImage.created_at",
    )


class DocumentChunk(Base):
    """Modelo ORM para fragmentos de documentos con soporte para chunking jerárquico (Parent-Child)."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_type: Mapped[str] = mapped_column(
        String(50), default="text", nullable=False, index=True
    )  # 'text', 'table', 'image_description'
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # vector(N) nativo (con índice HNSW) en PostgreSQL; array JSON de floats en SQLite
    embedding: Mapped[list[float] | None] = mapped_column(
        JSON(none_as_null=True).with_variant(Vector(settings.EMBEDDING_DIMENSION), "postgresql"), nullable=True
    )
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relaciones
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    parent: Mapped[Optional["DocumentChunk"]] = relationship(
        "DocumentChunk", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="parent", cascade="all, delete-orphan"
    )


class DocumentImage(Base):
    """Modelo ORM para imágenes y diagramas extraídos de documentos o cargados directamente."""

    __tablename__ = "document_images"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relaciones
    document: Mapped["Document"] = relationship("Document", back_populates="images")

