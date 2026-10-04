from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_data_service
from app.core.config import Settings, get_settings
from app.schemas.instrument import InstrumentListResponse
from app.services.data_service import DataService

router = APIRouter(tags=["instruments"])


@router.get("/instruments", response_model=InstrumentListResponse)
async def list_instruments(
    query: str = Query("", description="Фильтр по тикеру или названию"),
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
    service: DataService = Depends(get_data_service),
    settings: Settings = Depends(get_settings),
):
    try:
        instruments, source = await service.get_instruments()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    q = query.strip().lower()
    filtered = [
        item
        for item in instruments
        if not q or q in item.ticker.lower() or q in item.name.lower()
    ]
    limit = min(limit, settings.max_limit)
    return InstrumentListResponse(
        items=filtered[offset : offset + limit],
        total=len(filtered),
        source=source,
    )
