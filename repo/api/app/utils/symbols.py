from __future__ import annotations

import re

_SYMBOL_RE = re.compile(r"^[A-Z]{2}\d{6}$")
_HK_SYMBOL_RE = re.compile(r"^HK\d{4,5}$")
_US_SYMBOL_RE = re.compile(r"^US[A-Z.]+$")


def normalize_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    if not upper:
        return upper
    if upper.endswith((".SH", ".SZ", ".HK", ".US")):
        if upper.endswith(".HK"):
            code = upper[:-3]
            if code.isdigit():
                return f"{code.zfill(5)}.HK"
        return upper
    if _SYMBOL_RE.match(upper):
        market = upper[:2]
        code = upper[2:]
        return f"{code}.{market}"
    if _HK_SYMBOL_RE.match(upper):
        return f"{upper[2:].zfill(5)}.HK"
    if _US_SYMBOL_RE.match(upper):
        return f"{upper[2:]}.US"
    digits = re.sub(r"\D", "", upper)
    if len(digits) == 5:
        return f"{digits}.HK"
    if len(digits) == 6 and digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    if len(digits) == 6:
        return f"{digits}.SZ"
    if upper.isalpha():
        return f"{upper}.US"
    return upper
