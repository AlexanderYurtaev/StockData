from datetime import date

from app.schemas.common import CATEGORY_TITLES, DataSourceInfo, ParticipantCategory
from app.schemas.instrument import Instrument, InstrumentKind
from app.schemas.position import (
    ClosedPositionRow,
    HistoryAggregates,
    HistoryPoint,
    HistoryResponse,
    OpenPositionRow,
    PositionSnapshot,
    SummaryCategory,
    SummaryResponse,
)


def _positive(value: int) -> int:
    return value if value > 0 else 0


def _negative(value: int) -> int:
    return -value if value < 0 else 0


class PositionService:
    """Чистые преобразования снимков данных в ответы API (без I/O)."""

    @staticmethod
    def to_open_rows(
        snapshots: list[PositionSnapshot], instruments: dict[str, Instrument]
    ) -> list[OpenPositionRow]:
        rows = []
        for snap in snapshots:
            instrument = instruments.get(snap.ticker)
            rows.append(
                OpenPositionRow(
                    ticker=snap.ticker,
                    name=instrument.name if instrument else snap.ticker,
                    kind=instrument.kind if instrument else InstrumentKind.STANDARD,
                    date=snap.date,
                    fiz=snap.individual,
                    jur=snap.legal_entity,
                    total=snap.total,
                    total_change=snap.total_change,
                )
            )
        return rows

    @staticmethod
    def to_closed_rows(
        snapshots: list[PositionSnapshot], instruments: dict[str, Instrument]
    ) -> list[ClosedPositionRow]:
        rows = []
        for snap in snapshots:
            instrument = instruments.get(snap.ticker)
            fiz, jur = snap.individual, snap.legal_entity
            net_now = (fiz.long + jur.long) - (fiz.short + jur.short)
            net_prev = net_now - (fiz.long_change - fiz.short_change + jur.long_change - jur.short_change)
            rows.append(
                ClosedPositionRow(
                    ticker=snap.ticker,
                    name=instrument.name if instrument else snap.ticker,
                    kind=instrument.kind if instrument else InstrumentKind.STANDARD,
                    date=snap.date,
                    fiz_long_closed=_negative(fiz.long_change),
                    fiz_short_closed=_negative(fiz.short_change),
                    fiz_long_opened=_positive(fiz.long_change),
                    fiz_short_opened=_positive(fiz.short_change),
                    jur_long_closed=_negative(jur.long_change),
                    jur_short_closed=_negative(jur.short_change),
                    jur_long_opened=_positive(jur.long_change),
                    jur_short_opened=_positive(jur.short_change),
                    net_change_fiz=(fiz.long - fiz.short)
                    - (fiz.long - fiz.long_change - (fiz.short - fiz.short_change)),
                    net_change_jur=(jur.long - jur.short)
                    - (jur.long - jur.long_change - (jur.short - jur.short_change)),
                )
            )
        return rows

    @staticmethod
    def history(
        instrument: Instrument,
        snapshots: list[PositionSnapshot],
        source: DataSourceInfo,
    ) -> HistoryResponse:
        points = [
            HistoryPoint(
                date=snap.date,
                fiz_long=snap.individual.long,
                fiz_short=snap.individual.short,
                jur_long=snap.legal_entity.long,
                jur_short=snap.legal_entity.short,
                total=snap.total,
            )
            for snap in sorted(snapshots, key=lambda s: s.date)
        ]

        totals = {
            key: 0
            for key in (
                "fiz_long_opened", "fiz_long_closed",
                "fiz_short_opened", "fiz_short_closed",
                "jur_long_opened", "jur_long_closed",
                "jur_short_opened", "jur_short_closed",
            )
        }
        for prev, cur in zip(points, points[1:]):
            for prefix in ("fiz", "jur"):
                for side in ("long", "short"):
                    delta = getattr(cur, f"{prefix}_{side}") - getattr(prev, f"{prefix}_{side}")
                    totals[f"{prefix}_{side}_opened"] += _positive(delta)
                    totals[f"{prefix}_{side}_closed"] += _negative(delta)

        return HistoryResponse(
            ticker=instrument.ticker,
            name=instrument.name,
            points=points,
            aggregates=HistoryAggregates(days=len(points), **totals),
            source=source,
        )

    @staticmethod
    def summary(
        snapshots: list[PositionSnapshot], source: DataSourceInfo
    ) -> SummaryResponse:
        items: list[SummaryCategory] = []
        grand_total = sum(
            snap.individual.long
            + snap.individual.short
            + snap.legal_entity.long
            + snap.legal_entity.short
            for snap in snapshots
        )
        for category, stat_attr in (
            (ParticipantCategory.INDIVIDUAL, "individual"),
            (ParticipantCategory.LEGAL_ENTITY, "legal_entity"),
        ):
            long_total = sum(getattr(s, stat_attr).long for s in snapshots)
            short_total = sum(getattr(s, stat_attr).short for s in snapshots)
            volume = long_total + short_total
            items.append(
                SummaryCategory(
                    category=category,
                    title=CATEGORY_TITLES[category],
                    long=long_total,
                    short=short_total,
                    net=long_total - short_total,
                    share_pct=round(volume / grand_total * 100, 1) if grand_total else 0.0,
                    long_holders=sum(getattr(s, stat_attr).long_holders for s in snapshots),
                    short_holders=sum(getattr(s, stat_attr).short_holders for s in snapshots),
                )
            )
        return SummaryResponse(
            date=max(snap.date for snap in snapshots),
            items=items,
            total=grand_total,
            total_change=sum(snap.total_change for snap in snapshots),
            instruments=len(snapshots),
            source=source,
        )

    @staticmethod
    def filter_rows(rows: list, query: str) -> list:
        query = (query or "").strip().lower()
        if not query:
            return rows
        return [
            row
            for row in rows
            if query in row.ticker.lower() or query in row.name.lower()
        ]

    @staticmethod
    def sort_rows(rows: list, key: str, descending: bool) -> list:
        def value(row) -> object:
            if key == "name":
                return row.name.lower()
            if hasattr(row, key):
                return getattr(row, key)
            return 0

        return sorted(rows, key=value, reverse=descending)
