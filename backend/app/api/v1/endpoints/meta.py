from fastapi import APIRouter, Depends

from app.api.deps import get_data_service
from app.core.config import Settings, get_settings
from app.schemas.common import CATEGORY_TITLES, ParticipantCategory, PositionView
from app.services.data_service import DataService

router = APIRouter(tags=["meta"])


@router.get("/meta")
async def meta(
    settings: Settings = Depends(get_settings),
    service: DataService = Depends(get_data_service),
):
    return {
        "categories": [
            {"code": category.value, "title": title}
            for category, title in CATEGORY_TITLES.items()
        ],
        "views": [
            {"code": view.value, "title": "Открытые позиции" if view == PositionView.OPEN else "Закрытие за день"}
            for view in PositionView
        ],
        "history_days_default": settings.history_days_default,
        "history_days_max": settings.history_days_max,
        "providers": service.providers_status(),
        "description": (
            "Открытые и закрытые позиции физических и юридических лиц "
            "по фьючерсам на акции. Закрытие позиций — неотрицательная часть "
            "изменения числа контрактов к предыдущему торговому дню."
        ),
    }
