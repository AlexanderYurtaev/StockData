from fastapi import APIRouter

from app.api.v1.endpoints import instruments, meta, positions, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(meta.router)
api_router.include_router(instruments.router)
api_router.include_router(positions.router)
