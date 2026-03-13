from __future__ import annotations

from typing import Iterable, List, Tuple

from etl.utils.logging import get_logger
from etl.utils.alerting import notify_batch

LOGGER = get_logger(__name__)


def to_list(rows: Iterable[dict]) -> List[dict]:
    return [dict(row) for row in rows]


def ensure_required(rows: Iterable[dict], required: Iterable[str], context: str) -> List[dict]:
    required_set = set(required)
    output: List[dict] = []
    errors: List[str] = []
    for row in rows:
        missing = required_set.difference(row.keys())
        if missing:
            msg = f"[{context}] 缺少字段 {sorted(missing)}: {row}"
            LOGGER.warning(msg)
            errors.append(msg)
            continue
        output.append(dict(row))
    if errors:
        notify_batch(errors)
    return output


def validate_numeric_range(
    rows: Iterable[dict],
    field: str,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    context: str = "validation",
) -> Tuple[List[dict], List[str]]:
    valid: List[dict] = []
    errors: List[str] = []
    for row in rows:
        value = row.get(field)
        if value is None:
            valid.append(row)
            continue
        if min_value is not None and value < min_value:
            msg = f"[{context}] {field}={value} < {min_value}: {row}"
            errors.append(msg)
            continue
        if max_value is not None and value > max_value:
            msg = f"[{context}] {field}={value} > {max_value}: {row}"
            errors.append(msg)
            continue
        valid.append(row)
    if errors:
        notify_batch(errors)
    return valid, errors
