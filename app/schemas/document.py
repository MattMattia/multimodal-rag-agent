from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DocumentChunkResponse(BaseModel):
    """Esquema para representar un chunk de documento con su información jerárquica."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    content: str
    chunk_type: str = Field(..., description="Tipo de chunk: 'text', 'table', 'image_description'")
    page_number: Optional[int] = None
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentImageResponse(BaseModel):
    """Esquema para representar una imagen extraída con su descripción de Gemini."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    image_path: str
    description: str
    page_number: Optional[int] = None
    image_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    """Respuesta inicial tras recibir y encolar un documento para procesamiento."""

    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    message: str


class DocumentResponse(BaseModel):
    """Esquema general de un documento almacenado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: str
    file_path: str
    upload_date: datetime
    status: str
    error_message: Optional[str] = None
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)
    total_chunks: int = 0
    total_images: int = 0


class DocumentDetailResponse(DocumentResponse):
    """Esquema detallado que incluye lista de fragmentos e imágenes."""

    chunks: List[DocumentChunkResponse] = Field(default_factory=list)
    images: List[DocumentImageResponse] = Field(default_factory=list)

