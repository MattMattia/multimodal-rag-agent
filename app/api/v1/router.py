from fastapi import APIRouter, Depends

from app.core.security import require_api_key

from app.api.v1.endpoints import agent, documents, files, health, search

api_router = APIRouter()

# /health permanece abierto (sonda de liveness); el resto exige X-API-Key si API_KEY está configurada
protected = [Depends(require_api_key)]

# Registro de routers por dominio / recurso
api_router.include_router(health.router, prefix="", tags=["Health"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"], dependencies=protected)
api_router.include_router(search.router, prefix="/search", tags=["Search / RAG"], dependencies=protected)
api_router.include_router(agent.router, prefix="/agent", tags=["Autonomous Agent"], dependencies=protected)
api_router.include_router(files.router, prefix="", tags=["Files"], dependencies=protected)
