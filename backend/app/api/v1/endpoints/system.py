from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.deps import get_data_service
from app.core.config import Settings, get_settings
from app.services.data_service import DataService

router = APIRouter(tags=["system"])


@router.get("/system/health")
async def health(
    settings: Settings = Depends(get_settings),
    service: DataService = Depends(get_data_service),
):
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "time": datetime.now(timezone.utc).isoformat(),
        "data_source": settings.data_source,
        "providers": service.providers_status(),
        "storage": service.storage_status(),
        "last_provider_error": service.last_error,
    }
