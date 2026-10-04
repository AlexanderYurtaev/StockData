from fastapi import Request

from app.services.data_service import DataService
from app.services.position_service import PositionService


def get_data_service(request: Request) -> DataService:
    return request.app.state.data_service


def get_position_service() -> PositionService:
    return PositionService()
