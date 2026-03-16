from __future__ import annotations

from datetime import date
from typing import Iterable, List
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)
_CSI_INDEX_WEIGHT_URL = (
    "https://csi-web-dev.oss-cn-shanghai-finance-1-pub.aliyuncs.com/"
    "static/html/csindex/public/uploads/file/autofile/closeweight/{index_code}closeweight.xls"
)
_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/vnd.ms-excel,application/octet-stream,*/*",
}

try:
    import pysnowball as ball  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ball = None
    LOGGER.warning("pysnowball import failed: %s", exc)

try:
    import xlrd  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    xlrd = None
    LOGGER.warning("xlrd import failed: %s", exc)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        number = float(text)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _extract_dict_rows(payload) -> list[dict]:
    rows: list[dict] = []
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            rows.append(node)
            stack.extend(node.values())
            continue
        if isinstance(node, list):
            stack.extend(node)
    return [row for row in rows if row]


def _pick(record: dict, keys: Iterable[str]):
    for key in keys:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return None


def _extract_weight_records(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict):
        weight_list = data.get("weightList") or data.get("weights") or data.get("items")
        if isinstance(weight_list, list):
            return [item for item in weight_list if isinstance(item, dict)]
    return [row for row in _extract_dict_rows(payload) if isinstance(row, dict)]


def _header_index(row: list[str], *keywords: str) -> int | None:
    lowered = [item.strip().lower() for item in row]
    for idx, cell in enumerate(lowered):
        if all(keyword in cell for keyword in keywords):
            return idx
    return None


def _normalize_sheet_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _parse_public_weight_sheet(local_symbol: str, as_of: date, rows: list[list[str]]) -> list[dict]:
    header_row_index = None
    for idx, row in enumerate(rows):
        if _header_index(row, "constituent", "code") is not None or _header_index(row, "成份券", "代码") is not None:
            header_row_index = idx
            break
    if header_row_index is None:
        return []

    header = rows[header_row_index]
    code_idx = _header_index(header, "constituent", "code")
    if code_idx is None:
        code_idx = _header_index(header, "成份券", "代码")
    name_idx = _header_index(header, "constituent", "name")
    if name_idx is None:
        name_idx = _header_index(header, "成份券", "名称")
    weight_idx = _header_index(header, "weight")
    if code_idx is None or weight_idx is None:
        return []

    parsed: list[dict] = []
    seen: set[str] = set()
    for rank, row in enumerate(rows[header_row_index + 1 :], start=1):
        if code_idx >= len(row):
            continue
        symbol = _normalize_constituent_symbol(row[code_idx])
        if symbol is None or symbol in seen:
            continue
        seen.add(symbol)
        weight = _safe_float(row[weight_idx]) or 0.0
        if weight > 1:
            weight = weight / 100.0
        item = {
            "index_symbol": local_symbol,
            "symbol": symbol,
            "date": as_of,
            "weight": weight,
            "rank": rank,
            "source": "CSI",
        }
        if name_idx is not None and name_idx < len(row):
            name = str(row[name_idx]).strip()
            if name:
                item["name"] = name
        parsed.append(item)
    return parsed


def _load_public_index_constituents(local_symbol: str, index_code: str, as_of: date) -> list[dict]:
    if xlrd is None:
        return []
    url = _CSI_INDEX_WEIGHT_URL.format(index_code=index_code)
    request = Request(url, headers=_REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        LOGGER.warning("csi closeweight fetch failed [%s]: %s", index_code, exc)
        return []
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        LOGGER.warning("csi closeweight fetch failed [%s]: %s", index_code, exc)
        return []

    try:
        workbook = xlrd.open_workbook(file_contents=payload)
        sheet = workbook.sheet_by_index(0)
    except Exception as exc:
        LOGGER.warning("csi closeweight parse failed [%s]: %s", index_code, exc)
        return []

    rows = [
        [_normalize_sheet_cell(sheet.cell_value(row_idx, col_idx)) for col_idx in range(sheet.ncols)]
        for row_idx in range(sheet.nrows)
    ]
    return _parse_public_weight_sheet(local_symbol, as_of, rows)


def _market_suffix_from_text(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if "beijing" in text or "北" in text:
        return "BJ"
    if "shanghai" in text or "上" in text or "沪" in text:
        return "SH"
    if "shenzhen" in text or "深" in text or "圳" in text:
        return "SZ"
    if "hong kong" in text or "港" in text:
        return "HK"
    return None


def _normalize_constituent_symbol(raw_symbol: object, *, market_hint: str | None = None) -> str | None:
    token = str(raw_symbol or "").strip().upper()
    if not token:
        return None
    if token.endswith((".SH", ".SZ", ".BJ", ".HK", ".US")) or re.match(r"^[A-Z]{2}\d{6}$", token):
        normalized = normalize_symbol(token)
        if normalized.endswith((".SH", ".SZ", ".BJ", ".HK", ".US")):
            return normalized
        return None

    digits = re.sub(r"\D", "", token)
    if len(digits) != 6:
        return None
    if market_hint in {"SH", "SZ", "BJ"}:
        return f"{digits}.{market_hint}"
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    if digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    return f"{digits}.SZ"


def _index_code_map() -> dict[str, str]:
    raw = os.getenv(
        "SNOWBALL_INDEX_CONS_MAP",
        "000016.SH=000016,000300.SH=000300,000688.SH=000688,899050.BJ=899050,"
        "000001.SH=000001,399001.SZ=399001,399006.SZ=399006",
    )
    output: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        left, right = item.split("=", 1)
        index_symbol = normalize_symbol(left.strip())
        index_code = re.sub(r"\D", "", right.strip())
        if index_symbol and index_code:
            output[index_symbol] = index_code
    return output


def get_index_constituents(index_symbol: str, as_of: date) -> List[dict]:
    local_symbol = normalize_symbol(index_symbol)
    index_code = _index_code_map().get(local_symbol, re.sub(r"\D", "", local_symbol))
    if not index_code:
        return []

    rows: list[dict] = []
    if local_symbol in {
        "000016.SH",
        "SH000016",
        "000300.SH",
        "SH000300",
        "000905.SH",
        "SH000905",
        "000905",
        "000688.SH",
        "SH000688",
        "899050.BJ",
        "BJ899050",
    }:
        from etl.fetchers.baostock_client import (
            get_hs300_constituents,
            get_index_member_constituents,
            get_sz50_constituents,
            get_zz500_constituents,
        )

        if local_symbol in {"000016.SH", "SH000016"}:
            rows = get_sz50_constituents(local_symbol, as_of)
        elif local_symbol in {"000300.SH", "SH000300"}:
            rows = get_hs300_constituents(local_symbol, as_of)
        elif local_symbol in {"000905.SH", "SH000905", "000905"}:
            rows = get_zz500_constituents(local_symbol, as_of)
        else:
            rows = get_index_member_constituents(local_symbol, as_of)

        if rows:
            return ensure_required(rows, ["index_symbol", "symbol", "date", "weight"], "index.constituents")
        LOGGER.info("baostock constituents empty [%s], fallback to snowball/csi", local_symbol)

    if ball is not None:
        try:
            payload = ball.index_weight_top10(index_code)
        except Exception as exc:
            LOGGER.warning("snowball index_weight_top10 failed [%s]: %s", index_code, exc)
        else:
            seen: set[str] = set()
            for record in _extract_weight_records(payload):
                market_hint = (
                    _market_suffix_from_text(_pick(record, ("marketNameCn", "market_name_cn", "exchangeNameCn", "exchange_name_cn")))
                    or _market_suffix_from_text(_pick(record, ("marketNameEn", "market_name_en", "exchangeNameEn", "exchange_name_en")))
                    or ("BJ" if local_symbol.endswith(".BJ") else None)
                )
                raw_symbol = _pick(
                    record,
                    (
                        "securityCode",
                        "security_code",
                        "stockCode",
                        "stock_code",
                        "consCode",
                        "cons_code",
                        "secu_code",
                        "stockSymbol",
                        "stock_symbol",
                    ),
                )
                if raw_symbol in (None, ""):
                    fallback_symbol = _pick(record, ("symbol",))
                    if isinstance(fallback_symbol, str) and re.search(r"[A-Z.]", fallback_symbol.upper()):
                        raw_symbol = fallback_symbol
                if raw_symbol in (None, ""):
                    continue
                symbol = _normalize_constituent_symbol(raw_symbol, market_hint=market_hint)
                if symbol is None or symbol in seen:
                    continue
                seen.add(symbol)
                weight = _safe_float(_pick(record, ("weight", "weightValue", "iweight", "weight_rate", "ratio"))) or 0.0
                if weight > 1:
                    weight = weight / 100.0
                row = {
                    "index_symbol": local_symbol,
                    "symbol": symbol,
                    "date": as_of,
                    "weight": weight,
                }
                name = _pick(record, ("securityName", "security_name", "stockName", "stock_name", "consName", "cons_name"))
                if name not in (None, ""):
                    row["name"] = str(name)
                rank = _pick(record, ("rowNum", "row_num", "rank"))
                try:
                    if rank not in (None, ""):
                        row["rank"] = int(rank)
                except (TypeError, ValueError):
                    pass
                row["source"] = "Snowball"
                rows.append(row)
    else:
        LOGGER.warning("pysnowball unavailable, fallback to CSI closeweight if possible")

    if not rows:
        LOGGER.info("index constituents primary source empty [%s], fallback to CSI closeweight", local_symbol)
        rows = _load_public_index_constituents(local_symbol, index_code, as_of)
        if rows:
            LOGGER.info("index constituents loaded from CSI closeweight [%s] count=%s", local_symbol, len(rows))
        else:
            LOGGER.warning("index constituents unavailable after CSI fallback [%s]", local_symbol)
    return ensure_required(rows, ["index_symbol", "symbol", "date", "weight"], "index.constituents")
