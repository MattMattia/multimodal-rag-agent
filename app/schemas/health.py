from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Esquema de respuesta para el estado de salud del sistema."""
    status: str = Field(..., description="Estado general de la aplicación ('ok' o 'degraded')")
    project: str = Field(..., description="Nombre del proyecto")
    environment: str = Field(..., description="Entorno de ejecución")
    database: str = Field(..., description="Estado de la conexión a PostgreSQL con pgvector")

