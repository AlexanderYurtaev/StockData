"""Локальный архив позиций на SQLite.

Хранит разобранные PositionSnapshot (плоские колонки) и маркеры «даты без
данных». Операции синхронные: объёмы малы (десятки строк на запрос), длительность
— микросекунды; конкурентный доступ сериализуется блокировкой. Точка расширения:
заменить на PostgreSQL, сохранив интерфейс.
"""

import os
import sqlite3
import threading
from datetime import date

from app.schemas.position import CategoryStat, PositionSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    ticker            TEXT NOT NULL,
    date              TEXT NOT NULL,
    fiz_long          INTEGER NOT NULL DEFAULT 0,
    fiz_short         INTEGER NOT NULL DEFAULT 0,
    fiz_long_change   INTEGER NOT NULL DEFAULT 0,
    fiz_short_change  INTEGER NOT NULL DEFAULT 0,
    fiz_long_holders  INTEGER NOT NULL DEFAULT 0,
    fiz_short_holders INTEGER NOT NULL DEFAULT 0,
    jur_long          INTEGER NOT NULL DEFAULT 0,
    jur_short         INTEGER NOT NULL DEFAULT 0,
    jur_long_change   INTEGER NOT NULL DEFAULT 0,
    jur_short_change  INTEGER NOT NULL DEFAULT 0,
    jur_long_holders  INTEGER NOT NULL DEFAULT 0,
    jur_short_holders INTEGER NOT NULL DEFAULT 0,
    total             INTEGER NOT NULL DEFAULT 0,
    total_change      INTEGER NOT NULL DEFAULT 0,
    fetched_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(date);
CREATE TABLE IF NOT EXISTS empty_dates (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    PRIMARY KEY (ticker, date)
);
-- Дневные агрегаты по всем инструментам (для графика «Динамика по рынку»)
CREATE TABLE IF NOT EXISTS daily_totals (
    date       TEXT PRIMARY KEY,
    fiz_long   INTEGER NOT NULL DEFAULT 0,
    fiz_short  INTEGER NOT NULL DEFAULT 0,
    jur_long   INTEGER NOT NULL DEFAULT 0,
    jur_short  INTEGER NOT NULL DEFAULT 0,
    total      INTEGER NOT NULL DEFAULT 0,
    instruments INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS empty_total_dates (
    date TEXT PRIMARY KEY
);
-- История цен базовых активов и индексов (ISS MOEX)
CREATE TABLE IF NOT EXISTS prices (
    underlying TEXT NOT NULL,
    date       TEXT NOT NULL,
    close      REAL NOT NULL,
    PRIMARY KEY (underlying, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
"""


class PositionsDatabase:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- записи

    def upsert(self, snapshots: list[PositionSnapshot]) -> None:
        rows = [
            (
                s.ticker,
                s.date.isoformat(),
                s.individual.long, s.individual.short,
                s.individual.long_change, s.individual.short_change,
                s.individual.long_holders, s.individual.short_holders,
                s.legal_entity.long, s.legal_entity.short,
                s.legal_entity.long_change, s.legal_entity.short_change,
                s.legal_entity.long_holders, s.legal_entity.short_holders,
                s.total, s.total_change,
            )
            for s in snapshots
        ]
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO snapshots VALUES ("
                "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                rows,
            )
            self._conn.commit()
            # Дата с данными отменяет ранее сохранённые маркеры «пусто»
            self._conn.executemany(
                "DELETE FROM empty_dates WHERE ticker = ? AND date = ?",
                [(s.ticker, s.date.isoformat()) for s in snapshots],
            )
            self._conn.commit()

    def mark_empty(self, ticker: str, day: date) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO empty_dates VALUES (?, ?)",
                (ticker, day.isoformat()),
            )
            self._conn.commit()

    # --------------------------------------------------- дневные агрегаты

    def upsert_totals(
        self, day: date, fiz_long: int, fiz_short: int,
        jur_long: int, jur_short: int, total: int, instruments: int,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO daily_totals"
                "(date, fiz_long, fiz_short, jur_long, jur_short, total, instruments, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (day.isoformat(), fiz_long, fiz_short, jur_long, jur_short, total, instruments),
            )
            self._conn.execute(
                "DELETE FROM empty_total_dates WHERE date = ?", (day.isoformat(),)
            )
            self._conn.commit()

    def mark_total_date_empty(self, day: date) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO empty_total_dates VALUES (?)", (day.isoformat(),)
            )
            self._conn.commit()

    def get_total_dates(self, dates: list[date]) -> dict[date, int]:
        """date -> число инструментов, по которым посчитан агрегат."""
        if not dates:
            return {}
        placeholders = ",".join("?" * len(dates))
        rows = self._conn.execute(
            f"SELECT date, instruments FROM daily_totals WHERE date IN ({placeholders})",
            [d.isoformat() for d in dates],
        ).fetchall()
        return {date.fromisoformat(row[0]): row[1] for row in rows}

    def trusted_empty_total_dates(self, dates: list[date]) -> set[date]:
        """Пустая дата достоверна, если позже уже есть ненулевые агрегаты."""
        if not dates:
            return set()
        placeholders = ",".join("?" * len(dates))
        rows = self._conn.execute(
            f"""
            SELECT e.date FROM empty_total_dates e
            WHERE e.date IN ({placeholders})
              AND EXISTS (
                SELECT 1 FROM daily_totals t
                WHERE t.date > e.date AND t.instruments > 0
              )
            """,
            [d.isoformat() for d in dates],
        ).fetchall()
        return {date.fromisoformat(row[0]) for row in rows}

    def get_totals_since(self, since: date) -> list[tuple]:
        return self._conn.execute(
            "SELECT date, fiz_long, fiz_short, jur_long, jur_short, total "
            "FROM daily_totals WHERE date >= ? AND instruments > 0 ORDER BY date",
            (since.isoformat(),),
        ).fetchall()

    # ---------------------------------------------------------------- цены

    def upsert_prices(self, code: str, rows: list[tuple[date, float]]) -> None:
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO prices VALUES (?, ?, ?)",
                [(code, d.isoformat(), c) for d, c in rows],
            )
            self._conn.commit()

    def get_prices(self, code: str, since: date, till: date) -> list[tuple[date, float]]:
        rows = self._conn.execute(
            "SELECT date, close FROM prices WHERE underlying = ? AND date BETWEEN ? AND ? ORDER BY date",
            (code, since.isoformat(), till.isoformat()),
        ).fetchall()
        return [(date.fromisoformat(r[0]), r[1]) for r in rows]

    def get_price_range(self, code: str) -> tuple[date, date] | None:
        row = self._conn.execute(
            "SELECT MIN(date), MAX(date) FROM prices WHERE underlying = ?", (code,)
        ).fetchone()
        if not row or not row[0]:
            return None
        return date.fromisoformat(row[0]), date.fromisoformat(row[1])

    # ---------------------------------------------------------------- чтение

    def dates_with_data(self, ticker: str, dates: list[date]) -> set[date]:
        return self._select_dates(
            "SELECT date FROM snapshots WHERE ticker = ? AND date IN (%s)"
            % ",".join("?" * len(dates)),
            [ticker, *(d.isoformat() for d in dates)],
        )

    def trusted_empty_dates(self, ticker: str, dates: list[date]) -> set[date]:
        """Пустая дата достоверна, только если по рынку уже опубликованы более
        поздние данные — иначе это может быть просто лаг публикации отчёта."""
        if not dates:
            return set()
        placeholders = ",".join("?" * len(dates))
        rows = self._conn.execute(
            f"""
            SELECT e.date FROM empty_dates e
            WHERE e.ticker = ? AND e.date IN ({placeholders})
              AND EXISTS (SELECT 1 FROM snapshots s WHERE s.date > e.date)
            """,
            [ticker, *(d.isoformat() for d in dates)],
        ).fetchall()
        return {date.fromisoformat(row[0]) for row in rows}

    def latest_date(self, before: date | None = None) -> date | None:
        query = "SELECT MAX(date) FROM snapshots"
        params: list[object] = []
        if before is not None:
            query += " WHERE date <= ?"
            params.append(before.isoformat())
        row = self._conn.execute(query, params).fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None

    def tickers_for_date(self, day: date) -> set[str]:
        rows = self._conn.execute(
            "SELECT ticker FROM snapshots WHERE date = ?", (day.isoformat(),)
        ).fetchall()
        return {row[0] for row in rows}

    def rows_for_date(self, day: date) -> list[PositionSnapshot]:
        rows = self._conn.execute(
            "SELECT * FROM snapshots WHERE date = ? ORDER BY ticker",
            (day.isoformat(),),
        ).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    def rows_for_ticker(self, ticker: str, since: date) -> list[PositionSnapshot]:
        rows = self._conn.execute(
            "SELECT * FROM snapshots WHERE ticker = ? AND date >= ? ORDER BY date",
            (ticker, since.isoformat()),
        ).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    def stats(self) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT date), MAX(date) FROM snapshots"
        ).fetchone()
        return {
            "points": row[0],
            "dates": row[1],
            "latest_date": row[2],
        }

    # ----------------------------------------------------------- вспомогательное

    def _select_dates(self, query: str, params: list[object]) -> set[date]:
        if not params[1:]:
            return set()
        rows = self._conn.execute(query, params).fetchall()
        return {date.fromisoformat(row[0]) for row in rows}

    @staticmethod
    def _row_to_snapshot(row: tuple) -> PositionSnapshot:
        return PositionSnapshot(
            date=date.fromisoformat(row[1]),
            ticker=row[0],
            individual=CategoryStat(
                long=row[2], short=row[3],
                long_change=row[4], short_change=row[5],
                long_holders=row[6], short_holders=row[7],
            ),
            legal_entity=CategoryStat(
                long=row[8], short=row[9],
                long_change=row[10], short_change=row[11],
                long_holders=row[12], short_holders=row[13],
            ),
            total=row[14],
            total_change=row[15],
        )
