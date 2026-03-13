from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
