import asyncio
import logging
from datetime import date

import httpx

from app.core.cache import TTLCache
from app.core.config import Settings
from app.providers.base import DataProvider, previous_weekday
from app.schemas.instrument import Instrument, InstrumentKind
from app.schemas.position import CategoryStat, PositionSnapshot

logger = logging.getLogger(__name__)

# Отчёт MOEX «Открытые позиции» публикуется с лагом ~1 торговый день,
# поэтому запрошенная дата может вернуть пустой ответ — идём назад по
# будням до первой даты с данными (не более MAX_DATE_LOOKBACK шагов).
MAX_DATE_LOOKBACK = 7
# API иногда отвечает пустым телом на частые запросы — повторяем с паузой.
EMPTY_RETRIES = 2
RETRY_DELAY = 0.6


class MoexOpenPositionsProvider(DataProvider):
    """Реальные данные внутреннего API страницы MOEX «Открытые позиции».

    Формат ответа по инструменту: список метрик (кол-во контрактов,
    изменение к пред. дню, кол-во лиц) с разбивкой long_fiz/short_fiz/
    long_jur/short_jur.
    """

    name = "moex"
    real = True
    label = "MOEX — отчёт «Открытые позиции» (web.moex.com)"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings
        self._cache = TTLCache()

    # ------------------------------------------------------------------ HTTP

    async def _get_json(self, path: str, params: dict[str, str]) -> list | dict:
        response = await self._http.get(
            f"{self._settings.moex_base_url}{path}", params=params
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------ инструменты

    @staticmethod
    def _is_stock_futures(title: str | None) -> bool:
        if not title:
            return False
        return "обыкновенные акции" in title or "привилегированные акции" in title

    # Внутри «Индекс МосБиржи …» прячутся не-фондовые индексы — исключаем их
    NON_EQUITY_INDEX_MARKS = ("Биткоин", "Эфириум", "юанях", "IPO", "гос. обл")

    @classmethod
    def _is_equity_index_futures(cls, title: str | None) -> bool:
        """Индексные фьючерсы на фондовые индексы (МосБиржи, РТС):
        IMOEX, MIX, MXI, RTS, RTSM. Крипто-, валютные, облигационные и
        прочие индексы не включаем."""
        if not title:
            return False
        if any(mark in title for mark in cls.NON_EQUITY_INDEX_MARKS):
            return False
        return "Индекс МосБиржи" in title or "Индекс РТС" in title

    def _instrument_kind(self, title: str) -> InstrumentKind:
        if "мини" in title.lower():
            return InstrumentKind.MINI
        if title.startswith("Однодневный"):
            return InstrumentKind.DAILY
        return InstrumentKind.STANDARD

    async def get_instruments(self, on_date: date | None = None) -> list[Instrument]:
        day = on_date or previous_weekday(date.today())
        cache_key = f"instruments:{day}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        payload = await self._get_json(
            "/open-position/instruments/F",
            {"date": day.isoformat(), "lang": "ru"},
        )
        assets = payload[1].get("assets", []) if isinstance(payload, list) else []
        instruments = [
            Instrument(
                ticker=asset["asset_code"],
                name=asset["title"],
                kind=self._instrument_kind(asset["title"]),
            )
            for asset in assets
            if self._is_stock_futures(asset.get("title"))
            or self._is_equity_index_futures(asset.get("title"))
        ]
        instruments.sort(key=lambda item: item.ticker)
        await self._cache.set(
            cache_key, instruments, self._settings.instruments_cache_ttl
        )
        return instruments

    # --------------------------------------------------------------- позиции

    def _parse_asset_rows(self, rows: list[dict], ticker: str, day: date) -> PositionSnapshot | None:
        contracts = change = holders = None
        for row in rows:
            title = row.get("title") or ""
            if "Кол-во контрактов" in title:
                contracts = row
            elif "Изменение к пред. торговому дню, шт" in title:
                change = row
            elif "лиц, имеющих" in title:
                holders = row

        if contracts is None:
            return None

        def val(row: dict | None, key: str) -> int:
            if row is None:
                return 0
            return int(round(float(row.get(key) or 0)))

        return PositionSnapshot(
            date=day,
            ticker=ticker,
            individual=CategoryStat(
                long=val(contracts, "long_fiz"),
                short=val(contracts, "short_fiz"),
                long_change=val(change, "long_fiz"),
                short_change=val(change, "short_fiz"),
                long_holders=val(holders, "long_fiz"),
                short_holders=val(holders, "short_fiz"),
            ),
            legal_entity=CategoryStat(
                long=val(contracts, "long_jur"),
                short=val(contracts, "short_jur"),
                long_change=val(change, "long_jur"),
                short_change=val(change, "short_jur"),
                long_holders=val(holders, "long_jur"),
                short_holders=val(holders, "short_jur"),
            ),
            total=val(contracts, "total"),
            total_change=val(change, "total"),
        )

    async def _fetch_asset_snapshot(self, ticker: str, day: date) -> PositionSnapshot | None:
        for attempt in range(EMPTY_RETRIES + 1):
            payload = await self._get_json(
                f"/open-position/F/{ticker}", {"date": day.isoformat(), "lang": "ru"}
            )
            rows = payload[1].get("openpositions", []) if isinstance(payload, list) and len(payload) > 1 else []
            snapshot = self._parse_asset_rows(rows, ticker, day) if rows else None
            if snapshot is not None:
                return snapshot
            if attempt < EMPTY_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        logger.warning("MOEX: пустой ответ для %s на %s после %d попыток", ticker, day, EMPTY_RETRIES + 1)
        return None

    async def get_ticker_on_date(self, ticker: str, day: date) -> PositionSnapshot | None:
        return await self._fetch_asset_snapshot(ticker, day)

    async def _fetch_many(self, tickers: list[str], day: date) -> list[PositionSnapshot]:
        semaphore = asyncio.Semaphore(self._settings.fetch_concurrency)

        async def guarded(ticker: str) -> PositionSnapshot | None:
            async with semaphore:
                try:
                    return await self._fetch_asset_snapshot(ticker, day)
                except httpx.HTTPError:
                    logger.warning("MOEX: не удалось получить %s на %s", ticker, day)
                    return None

        results = await asyncio.gather(*(guarded(t) for t in tickers))
        return [snap for snap in results if snap is not None]

    async def get_snapshot(self, on_date: date | None = None) -> list[PositionSnapshot]:
        cache_key = f"snapshot:{on_date or 'latest'}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        instruments = await self.get_instruments()
        tickers = [item.ticker for item in instruments]

        day = on_date or previous_weekday(date.today())
        for _ in range(MAX_DATE_LOOKBACK):
            snapshots = await self._fetch_many(tickers, day)
            if snapshots:
                await self._cache.set(
                    cache_key, snapshots, self._settings.snapshot_cache_ttl
                )
                return snapshots
            day = previous_weekday(day)

        raise RuntimeError(f"MOEX: нет данных ни за одну из последних {MAX_DATE_LOOKBACK} дат")

    async def get_history(
        self, ticker: str, days: int, end_date: date | None = None
    ) -> list[PositionSnapshot]:
        cache_key = f"history:{ticker}:{days}:{end_date or 'latest'}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        max_lookback = days * 2 + 10
        candidates: list[date] = []
        day = end_date or previous_weekday(date.today())
        for _ in range(max_lookback):
            candidates.append(day)
            day = previous_weekday(day)

        collected: list[PositionSnapshot] = []
        step = self._settings.fetch_concurrency
        for offset in range(0, len(candidates), step):
            batch = candidates[offset : offset + step]
            semaphore = asyncio.Semaphore(step)

            async def guarded(day: date) -> PositionSnapshot | None:
                async with semaphore:
                    try:
                        return await self._fetch_asset_snapshot(ticker, day)
                    except httpx.HTTPError:
                        logger.warning("MOEX: не удалось получить %s на %s", ticker, day)
                        return None

            results = await asyncio.gather(*(guarded(d) for d in batch))
            collected.extend(snap for snap in results if snap is not None)

        collected.sort(key=lambda snap: snap.date)
        result = collected[-days:]
        await self._cache.set(cache_key, result, self._settings.history_cache_ttl)
        return result
