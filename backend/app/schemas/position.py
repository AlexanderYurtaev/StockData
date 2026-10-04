from datetime import date as Date

from pydantic import BaseModel

from app.schemas.common import DataSourceInfo, ParticipantCategory, PositionView
from app.schemas.instrument import InstrumentKind

# Префиксы fiz/jur соответствуют колонкам отчёта MOEX «Открытые позиции»
# (long_fiz / short_fiz / long_jur / short_jur).


class CategoryStat(BaseModel):
    long: int = 0
    short: int = 0
    long_change: int = 0  # изменение к предыдущему торговому дню, контрактов
    short_change: int = 0
    long_holders: int = 0  # кол-во лиц с открытыми позициями
    short_holders: int = 0


class PositionSnapshot(BaseModel):
    """Снимок позиций по одному инструменту на одну дату."""

    date: Date
    ticker: str
    individual: CategoryStat = CategoryStat()
    legal_entity: CategoryStat = CategoryStat()
    total: int = 0  # совокупный объём открытых позиций по инструменту
    total_change: int = 0


class OpenPositionRow(BaseModel):
    """Строка таблицы «Открытые» — последний доступный торговый день."""

    ticker: str
    name: str
    kind: InstrumentKind = InstrumentKind.STANDARD
    date: Date
    fiz: CategoryStat
    jur: CategoryStat
    total: int
    total_change: int


class ClosedPositionRow(BaseModel):
    """Строка «Закрытые» — закрытие позиций за последний торговый день.

    closed = сумма дневных уменьшений числа контрактов (неотрицательная часть
    изменения к предыдущему дню); opened — соответственно рост.
    """

    ticker: str
    name: str
    kind: InstrumentKind = InstrumentKind.STANDARD
    date: Date
    fiz_long_closed: int
    fiz_short_closed: int
    fiz_long_opened: int
    fiz_short_opened: int
    jur_long_closed: int
    jur_short_closed: int
    jur_long_opened: int
    jur_short_opened: int
    net_change_fiz: int  # net = (long - short) сегодня минус вчера
    net_change_jur: int


class HistoryPoint(BaseModel):
    date: Date
    fiz_long: int
    fiz_short: int
    jur_long: int
    jur_short: int
    total: int


class HistoryAggregates(BaseModel):
    """Сводка по истории: сколько позиций открыто/закрыто за период."""

    days: int = 0
    fiz_long_opened: int = 0
    fiz_long_closed: int = 0
    fiz_short_opened: int = 0
    fiz_short_closed: int = 0
    jur_long_opened: int = 0
    jur_long_closed: int = 0
    jur_short_opened: int = 0
    jur_short_closed: int = 0


class PricePoint(BaseModel):
    """Цена закрытия базового актива (акция) или индекса на дату."""

    date: Date
    close: float


class HistoryResponse(BaseModel):
    ticker: str
    name: str
    points: list[HistoryPoint]
    aggregates: HistoryAggregates
    prices: list[PricePoint] = []
    price_label: str | None = None
    source: DataSourceInfo


class TotalsHistoryResponse(BaseModel):
    """История суммарных позиций по всем инструментам списка."""

    points: list[HistoryPoint]
    instruments: int = 0
    prices: list[PricePoint] = []
    price_label: str | None = None
    source: DataSourceInfo


class PositionsResponse(BaseModel):
    items: list[OpenPositionRow | ClosedPositionRow]
    total: int
    date: Date | None = None
    view: PositionView
    source: DataSourceInfo


class SummaryCategory(BaseModel):
    category: ParticipantCategory
    title: str
    long: int
    short: int
    net: int
    share_pct: float  # доля категории в совокупном объёме (long + short)
    long_holders: int
    short_holders: int


class SummaryResponse(BaseModel):
    date: Date
    items: list[SummaryCategory]
    total: int
    total_change: int
    instruments: int = 0  # сколько инструментов вошло в агрегаты
    source: DataSourceInfo
