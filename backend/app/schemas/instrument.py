from enum import Enum

from pydantic import BaseModel

from app.schemas.common import DataSourceInfo


class InstrumentKind(str, Enum):
    STANDARD = "standard"  # обычный квартальный контракт
    MINI = "mini"          # мини-контракт
    DAILY = "daily"        # однодневный контракт с автопролонгацией


class Instrument(BaseModel):
    ticker: str
    name: str
    kind: InstrumentKind = InstrumentKind.STANDARD


class InstrumentListResponse(BaseModel):
    items: list[Instrument]
    total: int
    source: DataSourceInfo
