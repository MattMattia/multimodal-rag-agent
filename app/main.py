from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import init_db

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger("rag-app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicialización de BD y recursos al arrancar."""
    logger.info("Iniciando %s en entorno [%s]...", settings.PROJECT_NAME, settings.ENVIRONMENT)
    # Crear carpetas de uploads si no existen
    Path("uploads/documents").mkdir(parents=True, exist_ok=True)
    Path("uploads/images").mkdir(parents=True, exist_ok=True)
    Path("uploads/reports").mkdir(parents=True, exist_ok=True)

    # Inicializar tablas y extensiones en PostgreSQL
    await init_db()

    yield
    logger.info("Apagando %s...", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend para Sistema RAG Multimodal & Agente IA Autónomo con soporte para PDFs complejos, tablas e imágenes.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configuración de Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar directorio estático de uploads para servir/previsualizar archivos e imágenes
Path("uploads").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/health", tags=["General"])
async def root_health():
    """Endpoint básico y rápido de verificación de salud para monitoreo y orquestadores."""
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
    }


@app.get("/", tags=["General"])
async def root_info():
    """Ruta raíz informativa con enlaces a la documentación de la API."""
    return {
        "message": f"Bienvenido a {settings.PROJECT_NAME}",
        "docs": "/docs",
        "health": "/health",
        "api_v1": settings.API_V1_STR,
    }


# Montar enrutador v1
app.include_router(api_router, prefix=settings.API_V1_STR)
