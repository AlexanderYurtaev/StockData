from abc import ABC, abstractmethod
from datetime import date, timedelta

from app.schemas.instrument import Instrument
from app.schemas.position import PositionSnapshot


class DataProvider(ABC):
    """Контракт источника данных.

    Чтобы добавить новый источник (например, выгрузку из БД или другой отчёт
    биржи), достаточно реализовать этот интерфейс и зарегистрировать провайдер
    в DataService._build_chain().
    """

    name: str = "base"
    real: bool = False
    label: str = ""

    @abstractmethod
    async def get_instruments(self, on_date: date | None = None) -> list[Instrument]:
        """Список фьючерсов на акции. Без аргумента — на последний торговый день;
        с датой — состав инструментов, существовавший на ту дату."""

    @abstractmethod
    async def get_snapshot(self, on_date: date | None = None) -> list[PositionSnapshot]:
        """Позиции по всем инструментам на последний доступный торговый день
        (не позднее on_date)."""

    @abstractmethod
    async def get_history(
        self, ticker: str, days: int, end_date: date | None = None
    ) -> list[PositionSnapshot]:
        """История позиций одного инструмента, не более `days` торговых дней."""

    async def get_ticker_on_date(self, ticker: str, day: date) -> PositionSnapshot | None:
        """Снимок одного инструмента на конкретную дату (None — данных нет).

        Нужен архивирующим провайдерам для докачки недостающих дат;
        источник может не поддерживать — тогда возвращает None.
        """
        return None


def previous_weekday(day: date) -> date:
    prev = day
    while True:
        prev = prev.fromordinal(prev.toordinal() - 1)
        if prev.weekday() < 5:
            return prev


def candidate_days(end: date, days: int, buffer: int = 10) -> list[date]:
    """Будни в календарном диапазоне `days` дней назад от `end` (+ запас на праздники).

    Растёт линейно с периодом (5/7 от календарных дней), в отличие от старого
    правила «×2+10», которое для многолетних периодов запрашивало лишнее.
    """
    start = end - timedelta(days=days)
    cursor = end
    out: list[date] = []
    while cursor >= start:
        out.append(cursor)
        cursor = previous_weekday(cursor)
    for _ in range(buffer):
        out.append(cursor)
        cursor = previous_weekday(cursor)
    return out
