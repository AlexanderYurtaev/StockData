from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_data_service, get_position_service
from app.core.config import Settings, get_settings
from app.schemas.common import PositionView
from app.schemas.instrument import Instrument
from app.schemas.position import (
    HistoryResponse,
    PositionsResponse,
    PricePoint,
    SummaryResponse,
    TotalsHistoryResponse,
)
from app.providers.underlying import resolve_underlying
from app.services.data_service import DataService
from app.services.position_service import PositionService

router = APIRouter(tags=["positions"])

OPEN_SORT_KEYS = {
    "ticker", "name", "total", "total_change",
    "fiz_long", "fiz_short", "fiz_long_change", "fiz_short_change",
    "jur_long", "jur_short", "jur_long_change", "jur_short_change",
}
CLOSED_SORT_KEYS = {
    "ticker", "name",
    "fiz_long_closed", "fiz_short_closed", "fiz_long_opened", "fiz_short_opened",
    "jur_long_closed", "jur_short_closed", "jur_long_opened", "jur_short_opened",
    "net_change_fiz", "net_change_jur",
}


@router.get("/positions", response_model=PositionsResponse)
async def get_positions(
    view: PositionView = Query(PositionView.OPEN, description="open — открытые, closed — закрытие за день"),
    query: str = Query("", description="Фильтр по тикеру или названию"),
    tickers: str = Query("", description="Список тикеров через запятую, например SBRF,GAZR"),
    sort: str = Query("", description="Поле сортировки"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
    service: DataService = Depends(get_data_service),
    positions: PositionService = Depends(get_position_service),
    settings: Settings = Depends(get_settings),
):
    try:
        snapshots, source = await service.get_snapshot()
        instruments, _ = await service.get_instruments()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    by_ticker: dict[str, Instrument] = {item.ticker: item for item in instruments}
    if view == PositionView.CLOSED:
        rows = positions.to_closed_rows(snapshots, by_ticker)
        allowed, default_sort = CLOSED_SORT_KEYS, "fiz_long_closed"
    else:
        rows = positions.to_open_rows(snapshots, by_ticker)
        allowed, default_sort = OPEN_SORT_KEYS, "total"

    rows = positions.filter_rows(rows, query)
    ticker_filter = {t.strip().upper() for t in tickers.split(",") if t.strip()}
    if ticker_filter:
        rows = [row for row in rows if row.ticker in ticker_filter]
    sort_key = sort if sort in allowed else default_sort
    rows = positions.sort_rows(rows, sort_key, order == "desc")

    limit = min(limit, settings.max_limit)
    data_date = snapshots[0].date if snapshots else None
    return PositionsResponse(
        items=rows[offset : offset + limit],
        total=len(rows),
        date=data_date,
        view=view,
        source=source,
    )


@router.get("/positions/history", response_model=HistoryResponse)
async def get_history(
    ticker: str = Query(..., min_length=1, description="Тикер фьючерса, например GAZR"),
    days: int = Query(14, ge=2),
    on_date: date | None = Query(None, description="Конечная дата периода"),
    service: DataService = Depends(get_data_service),
    positions: PositionService = Depends(get_position_service),
    settings: Settings = Depends(get_settings),
):
    days = min(days, settings.history_days_max)
    try:
        instruments, _ = await service.get_instruments()
        instrument = next((i for i in instruments if i.ticker == ticker.upper()), None)
        if instrument is None:
            raise HTTPException(status_code=404, detail=f"Инструмент {ticker} не найден")
        snapshots, source = await service.get_history(instrument.ticker, days, on_date)
    except HTTPException:
        raise
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    prices, price_label = [], None
    if snapshots:
        resolved = resolve_underlying(instrument.ticker)
        if resolved:
            kind, code = resolved
            rows, _ = await service.get_price_history(
                kind, code, snapshots[0].date, snapshots[-1].date
            )
            prices = [PricePoint(date=d, close=c) for d, c in rows]
            price_label = ("Индекс " if kind == "index" else "Акция ") + code

    history = positions.history(instrument, snapshots, source)
    return HistoryResponse(
        ticker=instrument.ticker,
        name=instrument.name,
        points=history.points,
        aggregates=history.aggregates,
        prices=prices,
        price_label=price_label,
        source=source,
    )


@router.get("/positions/totals-history", response_model=TotalsHistoryResponse)
async def get_totals_history(
    days: int = Query(14, ge=2, description="Сколько торговых дней назад"),
    on_date: date | None = Query(None, description="Конечная дата периода"),
    service: DataService = Depends(get_data_service),
    settings: Settings = Depends(get_settings),
):
    days = min(days, settings.history_days_max)
    try:
        points, source = await service.get_totals_history(days, on_date)
        instruments, _ = await service.get_instruments()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    prices, price_label = [], None
    if points:
        rows, _ = await service.get_price_history(
            "index", "IMOEX", points[0].date, points[-1].date
        )
        prices = [PricePoint(date=d, close=c) for d, c in rows]
        price_label = "Индекс МосБиржи"

    return TotalsHistoryResponse(
        points=points,
        instruments=len(instruments),
        prices=prices,
        price_label=price_label,
        source=source,
    )


@router.get("/positions/summary", response_model=SummaryResponse)
async def get_summary(service: DataService = Depends(get_data_service),
                      positions: PositionService = Depends(get_position_service)):
    try:
        snapshots, source = await service.get_snapshot()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return positions.summary(snapshots, source)
