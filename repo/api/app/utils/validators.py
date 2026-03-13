from __future__ import annotations

from fastapi import HTTPException


def raise_validation_error(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def validate_symbol_match(path_symbol: str, payload_symbol: str) -> None:
    if path_symbol != payload_symbol:
        raise_validation_error("Symbol mismatch")
