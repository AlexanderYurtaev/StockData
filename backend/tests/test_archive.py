from datetime import date, timedelta

import pytest

from app.core.config import Settings
from app.providers.base import DataProvider, previous_weekday
from app.providers.demo import DemoProvider
from app.schemas.instrument import Instrument
from app.schemas.position import CategoryStat, PositionSnapshot
from app.storage.db import PositionsDatabase
from app.providers.archive import ArchiveProvider

TODAY = previous_weekday(date.today())


def make_snapshot(ticker: str, day: date, long_value: int) -> PositionSnapshot:
    return PositionSnapshot(
        date=day,
        ticker=ticker,
        individual=CategoryStat(long=long_value, short=long_value // 2),
        legal_entity=CategoryStat(long=long_value // 3, short=long_value // 4),
        total=long_value + long_value // 2 + long_value // 3 + long_value // 4,
    )


class FakeSource(DataProvider):
    """Считает обращения; на каждую дату генерирует детерминированный снимок."""

    name = "fake"
    real = False
    label = "fake"

    def __init__(self, gap_dates: set[date] | None = None) -> None:
        self.snapshot_calls = 0
        self.date_calls: list[tuple[str, date]] = []
        self.gap_dates = gap_dates or set()

    async def get_instruments(self, on_date=None) -> list[Instrument]:
        return [Instrument(ticker="AAA", name="Тест А"), Instrument(ticker="BBB", name="Тест Б")]

    async def get_snapshot(self, on_date: date | None = None) -> list[PositionSnapshot]:
        self.snapshot_calls += 1
        day = on_date or previous_weekday(TODAY)
        return [make_snapshot("AAA", day, 1000), make_snapshot("BBB", day, 2000)]

    async def get_history(self, ticker: str, days: int, end_date=None) -> list[PositionSnapshot]:
        return []

    async def get_ticker_on_date(self, ticker: str, day: date) -> PositionSnapshot | None:
        self.date_calls.append((ticker, day))
        if day in self.gap_dates:
            return None
        return make_snapshot(ticker, day, day.toordinal() % 5000 + 100)


@pytest.fixture
def db(tmp_path):
    database = PositionsDatabase(str(tmp_path / "test.db"))
    yield database
    database.close()


@pytest.fixture
def source():
    return FakeSource()


@pytest.fixture
def archive(db, source):
    return ArchiveProvider(source, db, Settings())


async def test_history_backfills_then_reads_from_db(archive, source):
    first = await archive.get_history("AAA", days=5)
    requested = len(source.date_calls)
    assert requested > 0
    assert 1 <= len(first) <= 5
    assert [p.date for p in first] == sorted(p.date for p in first)

    second = await archive.get_history("AAA", days=5)
    assert len(source.date_calls) == requested, "второй запрос не должен обращаться к источнику"
    assert [(p.date, p.total) for p in second] == [(p.date, p.total) for p in first]


async def test_history_respects_requested_days(archive, source):
    points = await archive.get_history("AAA", days=14)
    assert len(points) == 14


async def test_empty_date_marker_prevents_refetch(archive, source, db):
    # «дыра» в середине периода: более свежие данные уже есть, поэтому
    # маркер «пусто» достоверен и дата не перекачивается
    gap = previous_weekday(previous_weekday(TODAY))
    source.gap_dates = {gap}
    points = await archive.get_history("AAA", days=5)
    assert all(p.date != gap for p in points)
    calls_after_first = len(source.date_calls)

    await archive.get_history("AAA", days=5)
    gap_calls = [c for c in source.date_calls[calls_after_first:] if c[1] == gap]
    assert not gap_calls, "пустая дата не должна запрашиваться повторно"


async def test_snapshot_served_from_db_when_fresh(archive, source):
    await archive.get_snapshot()
    assert source.snapshot_calls == 1

    second = await archive.get_snapshot()
    assert source.snapshot_calls == 1, "свежий срез должен читаться из базы"
    assert second and second[0].ticker == "AAA"


async def test_snapshot_refetches_when_stale(archive, source, db):
    old = TODAY - timedelta(days=10)
    db.upsert([make_snapshot("AAA", old, 500)])
    await archive.get_snapshot()
    assert source.snapshot_calls == 1, "устаревший срез должен докачиваться"


async def test_snapshot_completes_missing_tickers(archive, source):
    await archive.get_history("AAA", days=3)  # в базе — только AAA
    snapshots = await archive.get_snapshot()
    tickers = {s.ticker for s in snapshots}
    assert tickers == {"AAA", "BBB"}, "неполный срез должен добираться по тикерам"
    assert source.snapshot_calls == 0, "полная перекачка срезa не нужна"


async def test_over_demo_source(db):
    source = DemoProvider()
    archive = ArchiveProvider(source, db, Settings())
    points = await archive.get_history("GAZR", days=10)
    assert len(points) == 10
    assert all(isinstance(p.total, int) for p in points)
