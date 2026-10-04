import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.data_service import DataService

logging.basicConfig(level=logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        timeout=settings.request_timeout,
        headers={"User-Agent": "futures-positions-viewer/0.1"},
        follow_redirects=True,
    ) as http:
        service = DataService(http)
        app.state.data_service = service
        await service.start_background()
        try:
            yield
        finally:
            await service.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Открытые и закрытые позиции физических и юридических лиц "
        "по фьючерсам на акции российской биржи."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
