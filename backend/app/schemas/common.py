from enum import Enum

from pydantic import BaseModel


class ParticipantCategory(str, Enum):
    INDIVIDUAL = "individual"
    LEGAL_ENTITY = "legal_entity"


CATEGORY_TITLES: dict[ParticipantCategory, str] = {
    ParticipantCategory.INDIVIDUAL: "Физические лица",
    ParticipantCategory.LEGAL_ENTITY: "Юридические лица",
}


class PositionView(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class DataSourceInfo(BaseModel):
    provider: str
    real: bool
    label: str
