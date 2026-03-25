from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from app.services.live_market_service import get_live_kline
from app.schemas.kline import KlineCompareIn, KlineCompareSeriesIn, KlinePeriod


def get_stock_kline(
    symbol: str,
    *,
    period: KlinePeriod = "day",
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    return get_live_kline(symbol, period=period, limit=limit, end=end, start=start, is_index=False)


def get_index_kline(
    symbol: str,
    *,
    period: KlinePeriod = "day",
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    return get_live_kline(symbol, period=period, limit=limit, end=end, start=start, is_index=True)


def get_compare_kline(payload: KlineCompareIn):
    requests = list(payload.series or [])
    if not requests:
        return {"period": payload.period, "limit": payload.limit, "series": []}

    results: list[dict | None] = [None] * len(requests)

    def _fetch(item: KlineCompareSeriesIn) -> dict:
        try:
            if item.kind == "index":
                items = get_index_kline(
                    item.symbol,
                    period=payload.period,
                    limit=payload.limit,
                    end=item.end,
                    start=item.start,
                )
            else:
                items = get_stock_kline(
                    item.symbol,
                    period=payload.period,
                    limit=payload.limit,
                    end=item.end,
                    start=item.start,
                )
            return {
                "symbol": item.symbol.upper(),
                "kind": item.kind,
                "period": payload.period,
                "items": items,
                "error": None,
            }
        except Exception as exc:
            return {
                "symbol": item.symbol.upper(),
                "kind": item.kind,
                "period": payload.period,
                "items": [],
                "error": str(exc) or "kline compare failed",
            }

    max_workers = min(8, len(requests))
    if max_workers <= 1:
        results[0] = _fetch(requests[0])
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_fetch, item): index
                for index, item in enumerate(requests)
            }
            for future in as_completed(future_map):
                results[future_map[future]] = future.result()

    return {
        "period": payload.period,
        "limit": payload.limit,
        "series": [item for item in results if item is not None],
    }
