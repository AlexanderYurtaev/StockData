import asyncio
import logging
import math
import time
from datetime import date

from app.core.config import Settings
from app.providers.base import DataProvider, candidate_days, previous_weekday
from app.schemas.instrument import Instrument
from app.schemas.position import HistoryPoint, PositionSnapshot
from app.storage.db import PositionsDatabase

logger = logging.getLogger(__name__)

# Считаем срез в базе свежим, если он не старше этого числа дней
# (длинные праздники + лаг публикации отчёта)
MAX_STALE_DAYS = 4


class ArchiveProvider(DataProvider):
    """Кэширующий прокси над источником: накапливает позиции в SQLite.

    - срез позиций: свежий — из базы, устаревший — докачка с биржи и запись;
    - история: докачивает только недостающие даты (ленивый бэкфилл задним
      числом при первом просмотре), результат остаётся в базе навсегда.
    """

    name = "moex_archive"
    real = True
    label = "MOEX «Открытые позиции» + локальный архив (SQLite)"

    def __init__(self, source: DataProvider, db: PositionsDatabase, settings: Settings) -> None:
        self._source = source
        self._db = db
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.fetch_concurrency)

    async def get_instruments(self, on_date: date | None = None) -> list[Instrument]:
        return await self._source.get_instruments(on_date)

    async def get_snapshot(self, on_date: date | None = None) -> list[PositionSnapshot]:
        day = on_date or previous_weekday(date.today())
        latest = self._db.latest_date(before=day)
        if latest is not None and (day - latest).days <= MAX_STALE_DAYS:
            # Дата свежая, но набор тикеров может быть неполным (например,
            # после докачки истории одного инструмента) — добираем недостающее
            known = self._db.tickers_for_date(latest)
            instruments = await self.get_instruments()
            missing = [i.ticker for i in instruments if i.ticker not in known]
            if missing:
                fetched = await asyncio.gather(
                    *(self._guarded_fetch(ticker, latest) for ticker in missing)
                )
                found = [snap for snap in fetched if snap is not None]
                if found:
                    self._db.upsert(found)
                logger.info("Архив: срез %s добран по %d инструментам", latest, len(found))
            rows = self._db.rows_for_date(latest)
            self._ensure_totals(rows, len(instruments))
            return rows

        snapshots = await self._source.get_snapshot(on_date=day)
        self._db.upsert(snapshots)
        self._ensure_totals(snapshots, len(await self.get_instruments()))
        return snapshots

    def _ensure_totals(self, snapshots: list[PositionSnapshot], instrument_count: int) -> None:
        """Полный срез даты — пересчитываем и сохраняем дневной агрегат."""
        if not snapshots or len(snapshots) < instrument_count:
            return
        day = snapshots[0].date
        self._db.upsert_totals(
            day,
            fiz_long=sum(s.individual.long for s in snapshots),
            fiz_short=sum(s.individual.short for s in snapshots),
            jur_long=sum(s.legal_entity.long for s in snapshots),
            jur_short=sum(s.legal_entity.short for s in snapshots),
            total=sum(s.total for s in snapshots),
            instruments=len(snapshots),
        )

    async def get_totals_history(self, days: int, end_date: date | None = None) -> list[HistoryPoint]:
        """История суммарных позиций по всем инструментам списка.

        Достаёт готовые дневные агрегаты из базы; недостающие даты докачивает
        с биржи (по всем инструментам на дату) и сохраняет навсегда.
        """
        day = end_date or previous_weekday(date.today())
        candidates = candidate_days(day, days)
        since = candidates[-1]

        # Длинные периоды сэмплируем: ~90 точек на период достаточно для
        # графика, а объём докачки сокращается в step раз (каждая дата —
        # по одному запросу на инструмент)
        estimated_trading = int(days * 5 / 7)
        step = max(1, math.ceil(estimated_trading / 90)) if days > 110 else 1
        sampled = candidates[::step]

        instruments = await self.get_instruments()
        tickers = [i.ticker for i in instruments]
        have = self._db.get_total_dates(sampled)
        empty_ok = self._db.trusted_empty_total_dates(sampled)
        missing = [d for d in sampled if d not in have and d not in empty_ok]

        if missing:
            logger.info(
                "Архив: агрегаты — докачиваем %d дат по %d инструментам",
                len(missing), len(tickers),
            )
            started = time.monotonic()
            # Даты обрабатываем последовательно, инструменты внутри даты —
            # параллельно: шторм «все даты × все тикеры» сразу вызывает
            # троттлинг MOEX, и свежие даты ошибочно помечаются пустыми.
            # Пустые ответы при докачке с большими паузами ретраятся сами.
            semaphore = asyncio.Semaphore(self._settings.fetch_concurrency)

            async def fetch_pair(d: date, ticker: str) -> tuple[date, PositionSnapshot | None]:
                async with semaphore:
                    try:
                        return d, await self._source.get_ticker_on_date(ticker, d)
                    except Exception as error:  # noqa: BLE001 — дата доберётся при следующем запросе
                        logger.warning("Архив: %s на %s не получен: %s", ticker, d, error)
                        return d, None

            for d in missing:
                # Состав инструментов на эту дату — у биржи он меняется:
                # сравнивать с сегодняшним набором нельзя
                expected = await self.get_instruments(on_date=d)
                expected_tickers = [i.ticker for i in expected]

                # Праздники/непубликуемые даты определяем пробой по ликвидным
                # инструментам, прежде чем запрашивать весь список.
                probe_tickers = [t for t in ("GAZR", "SBRF", "LKOH") if t in expected_tickers]
                probes = await asyncio.gather(*(fetch_pair(d, t) for t in probe_tickers))
                if probes and all(snap is None for _, snap in probes):
                    self._db.mark_total_date_empty(d)
                    continue

                results = await asyncio.gather(*(fetch_pair(d, t) for t in expected_tickers))
                snaps = [s for _, s in results if s is not None and s.date == d]
                if snaps:
                    self._db.upsert(snaps)
                    self._ensure_totals(snaps, len(expected_tickers))
                else:
                    self._db.mark_total_date_empty(d)
            logger.info(
                "Архив: агрегаты — %d дат докачаны за %.1f с",
                len(missing), time.monotonic() - started,
            )

        rows = self._db.get_totals_since(since)
        points = [
            HistoryPoint(
                date=date.fromisoformat(row[0]),
                fiz_long=row[1], fiz_short=row[2],
                jur_long=row[3], jur_short=row[4],
                total=row[5],
            )
            for row in rows
        ]
        return points[-days:]

    async def get_history(
        self, ticker: str, days: int, end_date: date | None = None
    ) -> list[PositionSnapshot]:
        day = end_date or previous_weekday(date.today())
        candidates = candidate_days(day, days)
        since = candidates[-1]

        have = self._db.dates_with_data(ticker, candidates)
        empty_ok = self._db.trusted_empty_dates(ticker, candidates)
        missing = [d for d in candidates if d not in have and d not in empty_ok]

        if missing:
            fetched = await asyncio.gather(
                *(self._guarded_fetch(ticker, d) for d in missing)
            )
            found = [snap for snap in fetched if snap is not None]
            if found:
                self._db.upsert(found)
            for snap_day, snap in zip(missing, fetched):
                if snap is None:
                    self._db.mark_empty(ticker, snap_day)
            logger.info(
                "Архив: %s — докачано %d дат (%d без данных)",
                ticker, len(found), len(missing) - len(found),
            )

        return self._db.rows_for_ticker(ticker, since)[-days:]

    async def _guarded_fetch(self, ticker: str, day: date) -> PositionSnapshot | None:
        async with self._semaphore:
            try:
                return await self._source.get_ticker_on_date(ticker, day)
            except Exception as error:  # noqa: BLE001 — дата просто останется незакэшированной
                logger.warning("Архив: не удалось получить %s на %s: %s", ticker, day, error)
                return None

    @property
    def db(self) -> PositionsDatabase:
        return self._db

    def storage_stats(self) -> dict:
        stats = self._db.stats()
        return {"enabled": True, **stats}
