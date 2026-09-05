from fastapi import APIRouter

from app.api.v1.endpoints import agent, documents, health, search

api_router = APIRouter()

# Registro de routers por dominio / recurso
api_router.include_router(health.router, prefix="", tags=["Health"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(search.router, prefix="/search", tags=["Search / RAG"])
api_router.include_router(agent.router, prefix="/agent", tags=["Autonomous Agent"])
