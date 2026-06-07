from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.services.live_index_service import list_live_index_constituents
from etl.providers import get_provider

LOGGER = get_logger("api.index_constituents")
_provider = get_provider()

_LATEST_DATE_SQL = text(
    """
    SELECT MAX(date) AS latest_date
    FROM index_constituents
    WHERE index_symbol = :symbol
      AND (:as_of IS NULL OR date <= :as_of)
    """
)

_LIST_ROWS_SQL = text(
    """
    SELECT ic.index_symbol, ic.symbol, ic.date, ic.weight, s.name, s.market, s.sector
    FROM index_constituents AS ic
    LEFT JOIN stocks AS s ON s.symbol = ic.symbol
    WHERE ic.index_symbol = :symbol
      AND ic.date = :target_date
    ORDER BY ic.weight DESC NULLS LAST, ic.symbol ASC
    LIMIT :limit OFFSET :offset
    """
)

_TOTAL_SQL = text(
    """
    SELECT COUNT(*) AS total
    FROM index_constituents
    WHERE index_symbol = :symbol
      AND date = :target_date
    """
)


def _list_persisted_index_constituents(
    db: Session,
    index_symbol: str,
    as_of: date | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    try:
        target_date = db.execute(_LATEST_DATE_SQL, {"symbol": index_symbol, "as_of": as_of}).scalar()
        if target_date is None:
            return [], 0

        total = int(
            db.execute(
                _TOTAL_SQL,
                {"symbol": index_symbol, "target_date": target_date},
            ).scalar()
            or 0
        )
        if total <= 0:
            return [], 0

        records = (
            db.execute(
                _LIST_ROWS_SQL,
                {
                    "symbol": index_symbol,
                    "target_date": target_date,
                    "limit": limit,
                    "offset": offset,
                },
            )
            .mappings()
            .all()
        )
    except Exception as exc:
        LOGGER.warning("load persisted index constituents failed [%s]: %s", index_symbol, exc)
        return [], 0

    items: list[dict] = []
    for index, record in enumerate(records, start=offset + 1):
        row = dict(record)
        row.setdefault("rank", index)
        row.setdefault("source", "DB")
        items.append(row)
    return items, total


def list_index_constituents(
    db: Session,
    index_symbol: str,
    as_of: date | None = None,
    limit: int = 200,
    offset: int = 0,
    allow_live_fallback: bool = False,
):
    canonical_symbol = _provider.market.normalize_index_symbol(index_symbol)
    items, total = _list_persisted_index_constituents(db, canonical_symbol, as_of, limit, offset)
    if total > 0:
        return items, total
    if allow_live_fallback:
        return list_live_index_constituents(canonical_symbol, as_of=as_of, limit=limit, offset=offset)
    return [], 0
