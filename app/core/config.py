import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la aplicación cargada desde variables de entorno y archivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # General
    PROJECT_NAME: str = "Sistema RAG Multimodal & Agente IA Autónomo"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Base de Datos
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rag_multimodal"

    # Google AI / Gemini API
    GOOGLE_API_KEY: str = ""
    GEMINI_AGENT_MODEL: str = "gemini-1.5-pro"
    GEMINI_VISION_MODEL: str = "gemini-1.5-flash"

    # Langfuse / Observabilidad y Telemetría
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://langfuse:3000"
    LANGFUSE_ENABLED: bool = False

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    @property
    def sync_database_url(self) -> str:
        """Retorna la URL de base de datos síncrona (psycopg2) si se requiere para librerías como Alembic o drivers síncronos."""
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        return self.DATABASE_URL


settings = Settings()

