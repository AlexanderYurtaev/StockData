import random
from datetime import date, timedelta

from app.providers.base import DataProvider, previous_weekday
from app.schemas.instrument import Instrument, InstrumentKind
from app.schemas.position import CategoryStat, HistoryPoint, PositionSnapshot

# (тикер, название, тип, базовая ликвидность в контрактах)
DEMO_INSTRUMENTS: list[tuple[str, str, InstrumentKind, int]] = [
    ("SBRF", "Фьючерс на обыкновенные акции ПАО Сбербанк", InstrumentKind.STANDARD, 220_000),
    ("SBERF", "Однодневный фьючерс на обыкновенные акции ПАО Сбербанк", InstrumentKind.DAILY, 260_000),
    ("GAZR", "Фьючерс на обыкновенные акции ПАО «Газпром»", InstrumentKind.STANDARD, 140_000),
    ("LKOH", "Фьючерс на обыкновенные акции ПАО «ЛУКОЙЛ»", InstrumentKind.STANDARD, 60_000),
    ("GMKN", "Фьючерс на обыкновенные акции ПАО «ГМК «Норильский никель»", InstrumentKind.STANDARD, 35_000),
    ("ROSN", "Фьючерс на обыкновенные акции ПАО «Роснефть»", InstrumentKind.STANDARD, 45_000),
    ("VTBR", "Фьючерс на обыкновенные акции ПАО Банк ВТБ", InstrumentKind.STANDARD, 90_000),
    ("TATN", "Фьючерс на обыкновенные акции ПАО «Татнефть»", InstrumentKind.STANDARD, 40_000),
    ("AFLT", "Фьючерс на обыкновенные акции ПАО «Аэрофлот»", InstrumentKind.STANDARD, 70_000),
    ("MTSI", "Фьючерс на обыкновенные акции ПАО «МТС»", InstrumentKind.STANDARD, 25_000),
    ("ALRS", "Фьючерс на обыкновенные акции АК «АЛРОСА»", InstrumentKind.STANDARD, 30_000),
    ("CHMF", "Фьючерс на обыкновенные акции ПАО «Северсталь»", InstrumentKind.STANDARD, 20_000),
    ("MAGN", "Фьючерс на обыкновенные акции ПАО «ММК»", InstrumentKind.STANDARD, 25_000),
    ("PLZL", "Фьючерс на обыкновенные акции ПАО «Полюс»", InstrumentKind.STANDARD, 20_000),
    ("PLZLM", "Фьючерс на обыкновенные акции ПАО «Полюс» (мини)", InstrumentKind.MINI, 8_000),
    ("SNGR", "Фьючерс на обыкновенные акции ПАО «Сургутнефтегаз»", InstrumentKind.STANDARD, 30_000),
    ("IRAO", "Фьючерс на обыкновенные акции ПАО «Интер РАО»", InstrumentKind.STANDARD, 22_000),
    ("FEES", "Фьючерс на обыкновенные акции ПАО «Россети»", InstrumentKind.STANDARD, 15_000),
    ("MOEX", "Фьючерс на обыкновенные акции ПАО Московская Биржа", InstrumentKind.STANDARD, 18_000),
    ("YDEX", "Фьючерс на обыкновенные акции МКПАО «Яндекс»", InstrumentKind.STANDARD, 35_000),
    ("T", "Фьючерс на обыкновенные акции МКПАО «Т-Технологии»", InstrumentKind.STANDARD, 40_000),
    ("OZON", "Фьючерс на обыкновенные акции ООО «Озон»", InstrumentKind.STANDARD, 22_000),
    ("IMOEX", "Однодневный фьючерс на Индекс МосБиржи", InstrumentKind.DAILY, 300_000),
    ("MIX", "Фьючерс на Индекс МосБиржи", InstrumentKind.STANDARD, 180_000),
    ("RTS", "Фьючерс на Индекс РТС", InstrumentKind.STANDARD, 150_000),
]

SERIES_DAYS = 120
DEMO_SEED = 20261003


class DemoProvider(DataProvider):
    """Детерминированные синтетические данные — офлайн-фолбэк и тесты.

    Профиль реалистичен: физлица преимущественно в лонгах, юридические —
    в шортах (хеджирование базового актива).
    """

    name = "demo"
    real = False
    label = "Демо-данные (синтетический генератор)"

    def __init__(self) -> None:
        self._series: dict[str, list[PositionSnapshot]] = {}
        self._dates = self._build_dates()

    def _build_dates(self) -> list[date]:
        days: list[date] = []
        day = previous_weekday(date.today())
        for _ in range(SERIES_DAYS):
            days.append(day)
            day = previous_weekday(day)
        return list(reversed(days))

    def _series_for(self, ticker: str, name: str, kind: InstrumentKind, base: int) -> list[PositionSnapshot]:
        if ticker in self._series:
            return self._series[ticker]

        rng = random.Random(f"{DEMO_SEED}:{ticker}")
        snapshots: list[PositionSnapshot] = []
        # Физлица: лонги 40–55% базы, шорты 12–22%; юрлица: лонги 10–18%, шорты 38–52%
        fiz_long = base * rng.uniform(0.40, 0.55)
        fiz_short = base * rng.uniform(0.12, 0.22)
        jur_long = base * rng.uniform(0.10, 0.18)
        jur_short = base * rng.uniform(0.38, 0.52)

        prev: PositionSnapshot | None = None
        for day in self._dates:
            fiz_long = max(100.0, fiz_long * rng.uniform(0.985, 1.015))
            fiz_short = max(100.0, fiz_short * rng.uniform(0.985, 1.015))
            jur_long = max(100.0, jur_long * rng.uniform(0.98, 1.02))
            jur_short = max(100.0, jur_short * rng.uniform(0.98, 1.02))

            snapshot = PositionSnapshot(
                date=day,
                ticker=ticker,
                individual=CategoryStat(
                    long=round(fiz_long),
                    short=round(fiz_short),
                    long_change=round(fiz_long) - (prev.individual.long if prev else 0),
                    short_change=round(fiz_short) - (prev.individual.short if prev else 0),
                    long_holders=round((fiz_long ** 0.5) * 3),
                    short_holders=round((fiz_short ** 0.5) * 2.5),
                ),
                legal_entity=CategoryStat(
                    long=round(jur_long),
                    short=round(jur_short),
                    long_change=round(jur_long) - (prev.legal_entity.long if prev else 0),
                    short_change=round(jur_short) - (prev.legal_entity.short if prev else 0),
                    long_holders=round((jur_long ** 0.5) * 0.8),
                    short_holders=round((jur_short ** 0.5) * 0.6),
                ),
                total=round(fiz_long + fiz_short + jur_long + jur_short),
                total_change=0,
            )
            snapshot.total_change = (
                snapshot.total - prev.total
                if prev
                else snapshot.individual.long_change
                + snapshot.individual.short_change
                + snapshot.legal_entity.long_change
                + snapshot.legal_entity.short_change
            )
            snapshots.append(snapshot)
            prev = snapshot

        self._series[ticker] = snapshots
        return snapshots

    async def get_instruments(self, on_date: date | None = None) -> list[Instrument]:
        return [
            Instrument(ticker=ticker, name=name, kind=kind)
            for ticker, name, kind, _base in DEMO_INSTRUMENTS
        ]

    def _snapshots_upto(self, on_date: date | None) -> list[PositionSnapshot]:
        limit = on_date or self._dates[-1]
        latest: list[PositionSnapshot] = []
        for ticker, name, kind, base in DEMO_INSTRUMENTS:
            series = self._series_for(ticker, name, kind, base)
            applicable = [snap for snap in series if snap.date <= limit]
            if applicable:
                latest.append(applicable[-1])
        return latest

    async def get_snapshot(self, on_date: date | None = None) -> list[PositionSnapshot]:
        return self._snapshots_upto(on_date)

    async def get_history(
        self, ticker: str, days: int, end_date: date | None = None
    ) -> list[PositionSnapshot]:
        entry = next(
            ((t, n, k, b) for t, n, k, b in DEMO_INSTRUMENTS if t == ticker), None
        )
        if entry is None:
            return []
        series = self._series_for(*entry)
        limit = end_date or self._dates[-1]
        applicable = [snap for snap in series if snap.date <= limit]
        return applicable[-days:]

    async def get_ticker_on_date(self, ticker: str, day: date) -> PositionSnapshot | None:
        entry = next(
            ((t, n, k, b) for t, n, k, b in DEMO_INSTRUMENTS if t == ticker), None
        )
        if entry is None:
            return None
        series = self._series_for(*entry)
        applicable = [snap for snap in series if snap.date <= day]
        return applicable[-1] if applicable else None

    async def get_totals_history(self, days: int, end_date: date | None = None) -> list[HistoryPoint]:
        """Сумма по всем демо-инструментам на каждую дату периода."""
        limit = end_date or self._dates[-1]
        dates = [d for d in self._dates if d <= limit][-days:]
        points: list[HistoryPoint] = []
        for day in dates:
            fiz_long = fiz_short = jur_long = jur_short = 0
            for ticker, name, kind, base in DEMO_INSTRUMENTS:
                series = self._series_for(ticker, name, kind, base)
                snap = next((s for s in series if s.date == day), None)
                if snap is None:
                    continue
                fiz_long += snap.individual.long
                fiz_short += snap.individual.short
                jur_long += snap.legal_entity.long
                jur_short += snap.legal_entity.short
            points.append(
                HistoryPoint(
                    date=day, fiz_long=fiz_long, fiz_short=fiz_short,
                    jur_long=jur_long, jur_short=jur_short,
                    total=fiz_long + fiz_short + jur_long + jur_short,
                )
            )
        return points

    async def get_price_history(
        self, kind: str, code: str, from_date: date, till_date: date
    ) -> list[tuple[date, float]]:
        """Синтетическая цена (случайное блуждание) — детерминирована по тикеру."""
        rng = random.Random(f"price:{code}")
        price = 50.0 + rng.random() * 4450.0
        out: list[tuple[date, float]] = []
        day = from_date
        while day <= till_date:
            if day.weekday() < 5:
                price = max(1.0, price * rng.uniform(0.97, 1.03))
                out.append((day, round(price, 2)))
            day += timedelta(days=1)
        return out
