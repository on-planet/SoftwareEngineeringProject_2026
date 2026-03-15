from __future__ import annotations

from fastapi import HTTPException

from app.utils.symbols import normalize_symbol


def raise_validation_error(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def validate_symbol_match(path_symbol: str, payload_symbol: str) -> None:
    if normalize_symbol(path_symbol) != normalize_symbol(payload_symbol):
        raise_validation_error("Symbol mismatch")
