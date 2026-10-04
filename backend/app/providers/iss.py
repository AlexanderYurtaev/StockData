"""История цен базовых активов и индексов из открытого API ISS Московской биржи.

Свечи акций — доска TQBR (если бумаги там нет, пробуем все доски), индексы —
доска SNDX. Результат кэшируется в SQLite: скачанные диапазоны не перекачиваются,
добирается только хвост.
"""

import logging
from datetime import date, timedelta

import httpx

from app.core.config import Settings
from app.storage.db import PositionsDatabase

logger = logging.getLogger(__name__)

PAGE_SIZE = 100


class IssPricesProvider:
    name = "iss_prices"
    real = True
    label = "ISS MOEX — история цен"

    def __init__(self, http: httpx.AsyncClient, settings: Settings, db: PositionsDatabase) -> None:
        self._http = http
        self._settings = settings
        self._db = db
        self._base = "https://iss.moex.com/iss/history"

    async def get_price_history(
        self, kind: str, code: str, from_date: date, till_date: date
    ) -> list[tuple[date, float]]:
        # Определяем, какая часть запрошенного диапазона не покрыта кэшем:
        # голова (старые даты) и хвост (свежие) докачиваются по отдельности
        rng = self._db.get_price_range(code)
        fetch_from = fetch_till = None
        if rng is None:
            fetch_from, fetch_till = from_date, till_date
        else:
            min_d, max_d = rng
            head_ok = min_d <= from_date + timedelta(days=3)
            tail_ok = max_d >= till_date - timedelta(days=4)
            if head_ok and tail_ok:
                pass  # диапазон полностью в кэше
            elif head_ok:  # не хватает только свежих дат
                fetch_from, fetch_till = max_d - timedelta(days=3), till_date
            elif tail_ok:  # не хватает только старых дат — типично при
                # расширении периода (60 дней после 30 и т.д.)
                fetch_from, fetch_till = from_date, min(min_d + timedelta(days=3), till_date)
            else:
                fetch_from, fetch_till = from_date, till_date

        if fetch_from is not None:
            rows = await self._fetch_iss(kind, code, fetch_from, fetch_till)
            if rows:
                self._db.upsert_prices(code, rows)
            else:
                logger.info("ISS: цены %s за %s..%s недоступны", code, fetch_from, fetch_till)
        return self._db.get_prices(code, from_date, till_date)

    async def _fetch_iss(
        self, kind: str, code: str, from_date: date, till_date: date
    ) -> list[tuple[date, float]]:
        if kind == "index":
            urls = [f"{self._base}/engines/stock/markets/index/boards/SNDX/securities/{code}.json"]
        else:
            urls = [
                f"{self._base}/engines/stock/markets/shares/boards/TQBR/securities/{code}.json",
                f"{self._base}/engines/stock/markets/shares/securities/{code}.json",
            ]

        for url in urls:
            rows = await self._fetch_pages(url, code, from_date, till_date)
            if rows:
                return rows
        return []

    async def _fetch_pages(
        self, url: str, code: str, from_date: date, till_date: date
    ) -> list[tuple[date, float]]:
        rows: list[tuple[date, float]] = []
        start = 0
        while True:
            response = await self._http.get(
                url,
                params={
                    "from": from_date.isoformat(),
                    "till": till_date.isoformat(),
                    "start": start,
                    "iss.meta": "off",
                },
            )
            response.raise_for_status()
            block = response.json().get("history", {})
            cols = block.get("columns", [])
            data = block.get("data", [])
            if "TRADEDATE" not in cols or "CLOSE" not in cols:
                return []
            di, ci = cols.index("TRADEDATE"), cols.index("CLOSE")
            for record in data:
                if record[ci] is None:
                    continue
                rows.append((date.fromisoformat(record[di]), float(record[ci])))
            if len(data) < PAGE_SIZE:
                return rows
            start += PAGE_SIZE
