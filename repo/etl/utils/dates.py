from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


def to_t1(as_of: date, offset_days: int = 1) -> date:
    """Convert to T-1 date based on offset days."""
    return as_of - timedelta(days=offset_days)


def date_range(start: date, end: date) -> Iterable[date]:
    """Inclusive date range iterator."""
    if start > end:
        return
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
