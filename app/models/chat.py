import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class ChatMessage(Base):
    """Modelo ORM para almacenar el historial de mensajes y memoria conversacional del Agente IA."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user', 'assistant', 'tool'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=True
    )
    executed_tools: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=True
    )
    # Metadatos libres del mensaje (p. ej. feedback del usuario: {"feedback": {"rating": 1, "comment": ...}})
    message_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )



async def ensure_chat_schema() -> None:
    """Migración idempotente: añade `message_metadata` a `chat_messages` si la tabla ya existía.

    `init_db()` ya la ejecuta; se conserva como función independiente para llamadas explícitas.
    """
    from app.core import database

    async with database.engine.begin() as conn:
        await database._ensure_message_metadata_column(conn, database.get_active_db_dialect())
