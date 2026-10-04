import asyncio
import logging
import sqlite3
import time

import httpx

from app.core.config import Settings, get_settings
from app.providers.archive import ArchiveProvider
from app.providers.base import DataProvider
from app.providers.demo import DemoProvider
from app.providers.iss import IssPricesProvider
from app.providers.moex import MoexOpenPositionsProvider
from app.schemas.common import DataSourceInfo
from app.schemas.instrument import Instrument
from app.schemas.position import PositionSnapshot
from app.storage.db import PositionsDatabase

logger = logging.getLogger(__name__)


class DataService:
    """Оркестратор провайдеров: цепочка с фолбэком и «остыванием» после сбоев.

    Публичные методы возвращают кортеж (данные, информация об источнике),
    чтобы API честно показывал, откуда пришли данные.
    """

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._settings: Settings = get_settings()
        self._demo = DemoProvider()
        self._moex = MoexOpenPositionsProvider(http, self._settings) if http else None
        self._archive: ArchiveProvider | None = None
        self._db: PositionsDatabase | None = None
        self._prices: IssPricesProvider | None = None
        self._provider_failed_at: dict[str, float] = {}
        self._sync_task: asyncio.Task | None = None
        self.last_error: str | None = None
        self._build_chain(http)

    def _build_chain(self, http: httpx.AsyncClient | None) -> None:
        source: DataProvider | None = self._moex
        if source is not None and self._settings.db_enabled:
            try:
                self._db = PositionsDatabase(self._settings.db_path)
                self._archive = ArchiveProvider(source, self._db, self._settings)
                source = self._archive
            except sqlite3.Error as error:
                logger.warning("Локальный архив недоступен (%s) — работаем напрямую с биржей", error)
                self._archive = None
        self._primary = source
        if http is not None and self._db is not None:
            self._prices = IssPricesProvider(http, self._settings, self._db)

    async def start_background(self) -> None:
        if self._sync_task is None and self._archive and self._settings.sync_interval > 0:
            self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
        if self._archive is not None:
            self._archive.db.close()

    async def _sync_loop(self) -> None:
        """Фоновая синхронизация: держит срез и дневные агрегаты актуальными.

        Первая итерация выполняется сразу после старта (прогрев), дальше —
        раз в sync_interval секунд.
        """
        try:
            while True:
                try:
                    snapshots, source = await self.get_snapshot()
                    if snapshots:
                        logger.info(
                            "Синхронизация: %d инструментов на %s (%s)",
                            len(snapshots), snapshots[0].date, source.provider,
                        )
                    if self._archive:
                        points = await self._archive.get_totals_history(
                            self._settings.total_backfill_days
                        )
                        logger.info(
                            "Синхронизация: агрегаты готовы за %d торговых дней", len(points)
                        )
                except Exception as error:  # noqa: BLE001 — синхронизация не должна ронять сервис
                    logger.warning("Синхронизация не удалась: %s", error)
                await asyncio.sleep(self._settings.sync_interval)
        except asyncio.CancelledError:
            pass

    def _in_cooldown(self, name: str) -> bool:
        failed_at = self._provider_failed_at.get(name)
        return (
            failed_at is not None
            and time.monotonic() - failed_at < self._settings.provider_fail_cooldown
        )

    def _mark_failed(self, provider: DataProvider, error: Exception) -> None:
        self._provider_failed_at[provider.name] = time.monotonic()
        self.last_error = f"{provider.name}: {error}"
        logger.warning("Провайдер %s недоступен: %s", provider.name, error)

    def _source_info(self, provider: DataProvider) -> DataSourceInfo:
        return DataSourceInfo(provider=provider.name, real=provider.real, label=provider.label)

    def _chain(self) -> list[DataProvider]:
        chain: list[DataProvider] = []
        if self._settings.data_source == "moex":
            if self._primary is not None:
                chain.append(self._primary)
        elif self._settings.data_source == "demo":
            chain.append(self._demo)
        else:  # auto
            if self._primary is not None and not self._in_cooldown(self._primary.name):
                chain.append(self._primary)
            chain.append(self._demo)
        return chain

    async def _run(self, method: str, *args: object):
        last_error: Exception | None = None
        for provider in self._chain():
            try:
                result = await getattr(provider, method)(*args)
                return result, self._source_info(provider)
            except Exception as error:  # noqa: BLE001 — фолбэк на следующий источник
                last_error = error
                self._mark_failed(provider, error)
        raise RuntimeError(f"Ни один провайдер не ответил: {last_error}")

    async def get_instruments(self) -> tuple[list[Instrument], DataSourceInfo]:
        return await self._run("get_instruments")  # type: ignore[return-value]

    async def get_snapshot(self) -> tuple[list[PositionSnapshot], DataSourceInfo]:
        return await self._run("get_snapshot")  # type: ignore[return-value]

    async def get_history(
        self, ticker: str, days: int, end_date=None
    ) -> tuple[list[PositionSnapshot], DataSourceInfo]:
        return await self._run("get_history", ticker, days, end_date)  # type: ignore[return-value]

    async def get_totals_history(self, days: int, end_date=None):
        return await self._run("get_totals_history", days, end_date)  # type: ignore[return-value]

    async def get_price_history(
        self, kind: str, code: str, from_date, till_date
    ) -> tuple[list[tuple], DataSourceInfo]:
        """Цены базового актива: ISS MOEX, в демо-режиме — синтетика."""
        demo_rows = await self._demo.get_price_history(kind, code, from_date, till_date)
        demo_info = self._source_info(self._demo)
        if self._settings.data_source == "demo" or self._prices is None:
            return demo_rows, demo_info
        try:
            return await self._prices.get_price_history(kind, code, from_date, till_date), \
                self._source_info(self._prices)
        except Exception as error:  # noqa: BLE001 — график остаётся без линии цены
            self.last_error = f"prices: {error}"
            logger.warning("Цены из ISS недоступны (%s) — график без линии цены", error)
            return demo_rows, demo_info

    def providers_status(self) -> list[dict]:
        providers: list[DataProvider] = [self._primary] if self._primary else []
        providers.append(self._demo)
        return [
            {
                "name": p.name,
                "real": p.real,
                "label": p.label,
                "in_cooldown": self._in_cooldown(p.name),
            }
            for p in providers
        ]

    def storage_status(self) -> dict:
        if self._archive is None:
            return {"enabled": False}
        return self._archive.storage_stats()
