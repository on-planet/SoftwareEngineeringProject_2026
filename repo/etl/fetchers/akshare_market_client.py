from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, List
import os

PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
AKSHARE_DISABLE_PROXY = os.getenv("AKSHARE_DISABLE_PROXY", "1").strip().lower() not in {"0", "false", "no"}
if AKSHARE_DISABLE_PROXY:
    for _proxy_key in PROXY_ENV_KEYS:
        os.environ.pop(_proxy_key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    try:
        import requests as _requests  # type: ignore

        _original_session_init = _requests.sessions.Session.__init__

        def _session_init_without_proxy(self, *args, **kwargs):
            _original_session_init(self, *args, **kwargs)
            self.trust_env = False

        _requests.sessions.Session.__init__ = _session_init_without_proxy
    except Exception:
        pass

from etl.fetchers.snowball_client import (
    normalize_symbol as _normalize_symbol,
    normalize_index_symbol as _normalize_index_symbol,
    market_from_symbol as _market_from_symbol,
    index_name as _index_name,
    index_market as _index_market,
    supported_index_specs as _supported_index_specs,
    to_snowball_symbol as _to_snowball_symbol,
    from_snowball_symbol as _from_snowball_symbol,
    _safe_float,
    _to_date,
    _to_datetime,
    _index_map,
    _index_specs_by_symbol,
)
from etl.fetchers.akshare_hk_stock_client import (
    fetch_hk_stock_universe_rows,
    fetch_hk_stock_profile_rows,
)
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)
CN_TZ = timezone(timedelta(hours=8))
EASTMONEY_KLINE_ENDPOINT = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
EASTMONEY_KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
EASTMONEY_KLINE_UT = "7eea3edcaed734bea9cbfc24409ed989"
EASTMONEY_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Connection": "close",
    "Referer": "https://quote.eastmoney.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ),
}

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover
    ak = None
    LOGGER.warning("akshare import failed in akshare market client: %s", exc)

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover
    pd = None
    LOGGER.warning("pandas import failed in akshare market client: %s", exc)

try:
    import requests  # type: ignore
except Exception as exc:  # pragma: no cover
    requests = None
    LOGGER.warning("requests import failed in akshare market client: %s", exc)


# ---------- 别名保持兼容 ----------
def normalize_symbol(symbol: str) -> str:
    return _normalize_symbol(symbol)


def normalize_index_symbol(symbol: str) -> str:
    return _normalize_index_symbol(symbol)


def market_from_symbol(symbol: str) -> str:
    return _market_from_symbol(symbol)


def index_name(symbol: str) -> str:
    return _index_name(symbol)


def index_market(symbol: str) -> str:
    return _index_market(symbol)


def supported_index_specs() -> list[dict]:
    return _supported_index_specs()


def to_snowball_symbol(symbol: str) -> str:
    return _to_snowball_symbol(symbol)


def from_snowball_symbol(symbol: str) -> str:
    return _from_snowball_symbol(symbol)


@contextmanager
def snowball_session():
    """空上下文管理器，保持兼容。"""
    yield


# ---------- A 股基础信息 ----------
_A_BASIC_CACHE: list[dict] | None = None
_A_BASIC_CACHE_TS: float = 0.0
_A_BASIC_TTL: int = max(30, int(os.getenv("AKSHARE_A_BASIC_CACHE_TTL", "300")))


def _load_a_stock_basics() -> list[dict]:
    global _A_BASIC_CACHE, _A_BASIC_CACHE_TS
    if ak is None or pd is None:
        return []
    now = __import__("time").monotonic()
    if _A_BASIC_CACHE is not None and (now - _A_BASIC_CACHE_TS) < _A_BASIC_TTL:
        return list(_A_BASIC_CACHE)

    try:
        df = ak.stock_info_a_code_name()
    except Exception as exc:
        LOGGER.warning("akshare stock_info_a_code_name failed: %s", exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    for record in df.to_dict(orient="records"):
        code = str(record.get("code") or "").strip()
        name = str(record.get("name") or "").strip()
        if not code or not name:
            continue
        if len(code) == 6:
            if code.startswith(("4", "8")):
                symbol = f"{code}.BJ"
            elif code.startswith(("5", "6", "9")):
                symbol = f"{code}.SH"
            else:
                symbol = f"{code}.SZ"
        else:
            symbol = normalize_symbol(code)
        rows.append({"symbol": symbol, "name": name, "market": "A", "sector": "Unknown"})

    _A_BASIC_CACHE = list(rows)
    _A_BASIC_CACHE_TS = now
    LOGGER.info("akshare a stock basics loaded rows=%s", len(rows))
    return rows


# ---------- 港股基础信息 ----------
_HK_BASIC_CACHE: list[dict] | None = None
_HK_BASIC_CACHE_TS: float = 0.0
_HK_BASIC_TTL: int = max(30, int(os.getenv("AKSHARE_HK_BASIC_CACHE_TTL", "300")))


def _load_hk_stock_basics() -> list[dict]:
    global _HK_BASIC_CACHE, _HK_BASIC_CACHE_TS
    now = __import__("time").monotonic()
    if _HK_BASIC_CACHE is not None and (now - _HK_BASIC_CACHE_TS) < _HK_BASIC_TTL:
        return list(_HK_BASIC_CACHE)
    rows = fetch_hk_stock_universe_rows()
    _HK_BASIC_CACHE = list(rows)
    _HK_BASIC_CACHE_TS = now
    return rows


# ---------- 全市场基础信息 ----------
def get_stock_basics(symbols: Iterable[str] | None = None) -> List[dict]:
    a_rows = _load_a_stock_basics()
    hk_rows = _load_hk_stock_basics()
    all_rows = {row["symbol"]: row for row in a_rows + hk_rows}

    if symbols is None:
        return list(all_rows.values())

    requested = [normalize_symbol(str(s)) for s in symbols if str(s).strip()]
    result: list[dict] = []
    for sym in requested:
        row = all_rows.get(sym)
        if row:
            result.append(dict(row))
        else:
            result.append({"symbol": sym, "name": sym, "market": market_from_symbol(sym), "sector": "Unknown"})
    return ensure_required(result, ["symbol", "name", "market", "sector"], "akshare.stock_basic")


def get_stock_basic() -> List[dict]:
    return get_stock_basics()


# ---------- 实时行情 ----------
_A_SPOT_CACHE: dict[str, dict] = {}
_A_SPOT_CACHE_TS: float = 0.0
_A_SPOT_TTL: int = max(10, int(os.getenv("AKSHARE_A_SPOT_CACHE_TTL", "60")))

_HK_SPOT_CACHE: dict[str, dict] = {}
_HK_SPOT_CACHE_TS: float = 0.0
_HK_SPOT_TTL: int = max(10, int(os.getenv("AKSHARE_HK_SPOT_CACHE_TTL", "60")))


def _fetch_a_spot() -> dict[str, dict]:
    global _A_SPOT_CACHE, _A_SPOT_CACHE_TS
    if ak is None or pd is None:
        return {}
    now = __import__("time").monotonic()
    if _A_SPOT_CACHE and (now - _A_SPOT_CACHE_TS) < _A_SPOT_TTL:
        return dict(_A_SPOT_CACHE)

    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as exc:
        LOGGER.warning("akshare stock_zh_a_spot_em failed: %s", exc)
        return {}
    if df is None or getattr(df, "empty", True):
        return {}

    result: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        code = str(record.get("代码") or record.get("code") or "").strip()
        if not code:
            continue
        if len(code) == 6:
            if code.startswith(("4", "8")):
                symbol = f"{code}.BJ"
            elif code.startswith(("5", "6", "9")):
                symbol = f"{code}.SH"
            else:
                symbol = f"{code}.SZ"
        else:
            symbol = normalize_symbol(code)

        current = _safe_float(record.get("最新价") or record.get("current") or record.get("price"))
        last_close = _safe_float(record.get("昨收") or record.get("last_close") or record.get("preclose"))
        change = _safe_float(record.get("涨跌额") or record.get("change") or record.get("chg"))
        percent = _safe_float(record.get("涨跌幅") or record.get("percent") or record.get("pct"))
        if change is None and current is not None and last_close not in (None, 0):
            change = current - last_close
        if percent is None and change is not None and last_close not in (None, 0):
            percent = change / last_close * 100.0

        result[symbol] = {
            "symbol": symbol,
            "name": str(record.get("名称") or record.get("name") or symbol).strip(),
            "current": current,
            "change": change,
            "percent": percent,
            "open": _safe_float(record.get("今开") or record.get("open")),
            "high": _safe_float(record.get("最高") or record.get("high")),
            "low": _safe_float(record.get("最低") or record.get("low")),
            "last_close": last_close,
            "volume": _safe_float(record.get("成交量") or record.get("volume") or record.get("vol")),
            "amount": _safe_float(record.get("成交额") or record.get("amount") or record.get("turnover")),
            "turnover_rate": _safe_float(record.get("换手率") or record.get("turnover_rate")),
            "amplitude": _safe_float(record.get("振幅") or record.get("amplitude")),
            "timestamp": datetime.now(tz=CN_TZ),
        }

    _A_SPOT_CACHE = dict(result)
    _A_SPOT_CACHE_TS = now
    LOGGER.info("akshare a spot loaded rows=%s", len(result))
    return result


def _fetch_hk_spot() -> dict[str, dict]:
    global _HK_SPOT_CACHE, _HK_SPOT_CACHE_TS
    if ak is None or pd is None:
        return {}
    now = __import__("time").monotonic()
    if _HK_SPOT_CACHE and (now - _HK_SPOT_CACHE_TS) < _HK_SPOT_TTL:
        return dict(_HK_SPOT_CACHE)

    fetch_fn = getattr(ak, "stock_hk_spot_em", None) or getattr(ak, "stock_hk_spot", None)
    if fetch_fn is None:
        return {}
    try:
        df = fetch_fn()
    except Exception as exc:
        LOGGER.warning("akshare hk spot failed: %s", exc)
        return {}
    if df is None or getattr(df, "empty", True):
        return {}

    result: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        code = str(record.get("代码") or record.get("code") or "").strip()
        if not code:
            continue
        symbol = f"{code.zfill(5)}.HK"
        current = _safe_float(record.get("最新价") or record.get("current") or record.get("price"))
        last_close = _safe_float(record.get("昨收") or record.get("last_close"))
        change = _safe_float(record.get("涨跌额") or record.get("change"))
        percent = _safe_float(record.get("涨跌幅") or record.get("percent"))
        if change is None and current is not None and last_close not in (None, 0):
            change = current - last_close
        if percent is None and change is not None and last_close not in (None, 0):
            percent = change / last_close * 100.0

        result[symbol] = {
            "symbol": symbol,
            "name": str(record.get("名称") or record.get("name") or symbol).strip(),
            "current": current,
            "change": change,
            "percent": percent,
            "open": _safe_float(record.get("今开") or record.get("open")),
            "high": _safe_float(record.get("最高") or record.get("high")),
            "low": _safe_float(record.get("最低") or record.get("low")),
            "last_close": last_close,
            "volume": _safe_float(record.get("成交量") or record.get("volume")),
            "amount": _safe_float(record.get("成交额") or record.get("amount")),
            "timestamp": datetime.now(tz=CN_TZ),
        }

    _HK_SPOT_CACHE = dict(result)
    _HK_SPOT_CACHE_TS = now
    LOGGER.info("akshare hk spot loaded rows=%s", len(result))
    return result


def get_stock_quote(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    if normalized.endswith(".HK"):
        quotes = _fetch_hk_spot()
        q = quotes.get(normalized)
        return q if q else None
    quotes = _fetch_a_spot()
    q = quotes.get(normalized)
    return q if q else None


def get_stock_quotes(symbols: Iterable[str] | None = None) -> List[dict]:
    a_quotes = _fetch_a_spot()
    hk_quotes = _fetch_hk_spot()
    all_quotes = {**a_quotes, **hk_quotes}

    if symbols is None:
        return list(all_quotes.values())

    requested = [normalize_symbol(str(s)) for s in symbols if str(s).strip()]
    seen: set[str] = set()
    result: list[dict] = []
    for sym in requested:
        if sym in seen:
            continue
        seen.add(sym)
        q = all_quotes.get(sym)
        if q:
            result.append(dict(q))
    return result


# ---------- 行情详情（PE/PB 等） ----------
def get_stock_quote_detail(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    if normalized.endswith(".HK"):
        return {}
    # 优先从 spot 缓存获取已有字段
    spot = _fetch_a_spot().get(normalized)
    result: dict = {"symbol": normalized}
    if spot:
        result["market_cap"] = _safe_float(spot.get("amount"))  # spot 中可能没有市值
    # AkShare 没有直接的 quote_detail 接口，尝试 individual_info
    if ak is not None and pd is not None:
        try:
            code = normalized.split(".")[0]
            df = ak.stock_individual_info_em(symbol=code)
            if df is not None and not getattr(df, "empty", True):
                info = dict(zip(df["item"], df["value"]))
                result["pe_ttm"] = _safe_float(info.get("市盈率-动态") or info.get("PE(TTM)"))
                result["pb"] = _safe_float(info.get("市净率") or info.get("PB"))
                result["market_cap"] = _safe_float(info.get("总市值") or info.get("总市值"))
                result["float_market_cap"] = _safe_float(info.get("流通市值"))
        except Exception as exc:
            LOGGER.debug("akshare stock_individual_info_em failed [%s]: %s", normalized, exc)
    return result if len(result) > 1 else None


# ---------- 盘口 ----------
def get_stock_pankou(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    if normalized.endswith(".HK"):
        return {}
    if ak is None or pd is None:
        return None
    try:
        code = normalized.split(".")[0]
        df = ak.stock_bid_ask_em(symbol=code)
    except Exception as exc:
        LOGGER.warning("akshare stock_bid_ask_em failed [%s]: %s", normalized, exc)
        return None
    if df is None or getattr(df, "empty", True):
        return None

    info = dict(zip(df["item"], df["value"]))
    bids: list[dict] = []
    asks: list[dict] = []
    for i in range(1, 6):
        bp = _safe_float(info.get(f"bid{i}") or info.get(f"buy{i}"))
        bc = _safe_float(info.get(f"bid{i}_volume") or info.get(f"buy{i}_vol"))
        if bp is not None or bc is not None:
            bids.append({"level": i, "price": bp, "volume": bc})
        sp = _safe_float(info.get(f"ask{i}") or info.get(f"sell{i}"))
        sc = _safe_float(info.get(f"ask{i}_volume") or info.get(f"sell{i}_vol"))
        if sp is not None or sc is not None:
            asks.append({"level": i, "price": sp, "volume": sc})

    return {
        "symbol": normalized,
        "diff": _safe_float(info.get("diff") or info.get("difference")),
        "ratio": _safe_float(info.get("ratio") or info.get("diff_percent")),
        "timestamp": datetime.now(tz=CN_TZ),
        "bids": bids,
        "asks": asks,
    }


# ---------- K 线历史 ----------
def get_kline_history(
    symbol: str,
    *,
    period: str = "day",
    count: int = 240,
    as_of: date | None = None,
    is_index: bool = False,
) -> List[dict]:
    normalized = normalize_index_symbol(symbol) if is_index else normalize_symbol(symbol)
    if not is_index and normalized.endswith(".HK"):
        return _get_hk_kline_history(normalized, period=period, count=count, as_of=as_of)
    if is_index:
        return _get_index_kline_history(normalized, period=period, count=count, as_of=as_of)
    return _get_a_kline_history(normalized, period=period, count=count, as_of=as_of)


def _get_a_kline_history(
    symbol: str,
    *,
    period: str = "day",
    count: int = 240,
    as_of: date | None = None,
) -> List[dict]:
    if ak is None or pd is None:
        return []
    code = symbol.split(".")[0]
    period_map = {"day": "daily", "week": "weekly", "month": "monthly"}
    ak_period = period_map.get(period, "daily")
    end_at = as_of or date.today()
    lookback = {"day": max(400, count * 3), "week": max(800, count * 14), "month": max(1500, count * 40)}.get(period, count * 3)
    start_at = end_at - timedelta(days=lookback)
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period=ak_period,
            start_date=start_at.strftime("%Y%m%d"),
            end_date=end_at.strftime("%Y%m%d"),
            adjust="",
        )
    except Exception as exc:
        LOGGER.warning("akshare stock_zh_a_hist failed [%s]: %s", symbol, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    for record in df.to_dict(orient="records"):
        row_date = _to_date(record.get("日期") or record.get("date") or record.get("time"))
        if row_date is None:
            continue
        if as_of is not None and row_date > as_of:
            continue
        open_val = _safe_float(record.get("开盘") or record.get("open"))
        high_val = _safe_float(record.get("最高") or record.get("high"))
        low_val = _safe_float(record.get("最低") or record.get("low"))
        close_val = _safe_float(record.get("收盘") or record.get("close"))
        volume_val = _safe_float(record.get("成交量") or record.get("volume"))
        if None in (open_val, high_val, low_val, close_val, volume_val):
            continue
        rows.append({
            "symbol": symbol,
            "date": row_date,
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "volume": volume_val,
        })
    rows.sort(key=lambda item: (item["date"], item["symbol"]))
    if count > 0:
        rows = rows[-count:]
    return rows


def _get_hk_kline_history(
    symbol: str,
    *,
    period: str = "day",
    count: int = 240,
    as_of: date | None = None,
) -> List[dict]:
    if ak is None or pd is None:
        return []
    code = symbol.split(".")[0].zfill(5)
    period_map = {"day": "daily", "week": "weekly", "month": "monthly"}
    ak_period = period_map.get(period, "daily")
    end_at = as_of or date.today()
    lookback = {"day": max(400, count * 3), "week": max(800, count * 14), "month": max(1500, count * 40)}.get(period, count * 3)
    start_at = end_at - timedelta(days=lookback)
    try:
        df = ak.stock_hk_hist(
            symbol=code,
            period=ak_period,
            start_date=start_at.strftime("%Y%m%d"),
            end_date=end_at.strftime("%Y%m%d"),
            adjust="",
        )
    except Exception as exc:
        LOGGER.warning("akshare stock_hk_hist failed [%s]: %s", symbol, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    for record in df.to_dict(orient="records"):
        row_date = _to_date(record.get("日期") or record.get("date"))
        if row_date is None:
            continue
        if as_of is not None and row_date > as_of:
            continue
        open_val = _safe_float(record.get("开盘") or record.get("open"))
        high_val = _safe_float(record.get("最高") or record.get("high"))
        low_val = _safe_float(record.get("最低") or record.get("low"))
        close_val = _safe_float(record.get("收盘") or record.get("close"))
        volume_val = _safe_float(record.get("成交量") or record.get("volume"))
        if None in (open_val, high_val, low_val, close_val, volume_val):
            continue
        rows.append({
            "symbol": symbol,
            "date": row_date,
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "volume": volume_val,
        })
    rows.sort(key=lambda item: (item["date"], item["symbol"]))
    if count > 0:
        rows = rows[-count:]
    return rows


def _eastmoney_index_secid(symbol: str) -> str | None:
    normalized = normalize_index_symbol(symbol)
    code = normalized.split(".")[0]
    if normalized.endswith(".SH"):
        return f"1.{code}"
    if normalized.endswith(".SZ"):
        return f"0.{code}"
    if normalized.endswith(".BJ"):
        return f"0.{code}"
    return None


def _get_index_kline_history_from_eastmoney(
    symbol: str,
    *,
    period: str = "day",
    count: int = 240,
    as_of: date | None = None,
) -> List[dict]:
    if requests is None:
        return []
    secid = _eastmoney_index_secid(symbol)
    if not secid:
        return []
    period_map = {"day": "101", "week": "102", "month": "103"}
    klt = period_map.get(period, "101")
    end_at = as_of or date.today()
    lookback = {"day": max(400, count * 3), "week": max(800, count * 14), "month": max(1500, count * 40)}.get(period, count * 3)
    start_at = end_at - timedelta(days=lookback)
    params = {
        "fields1": EASTMONEY_KLINE_FIELDS1,
        "fields2": EASTMONEY_KLINE_FIELDS2,
        "ut": EASTMONEY_KLINE_UT,
        "klt": klt,
        "fqt": "0",
        "secid": secid,
        "beg": start_at.strftime("%Y%m%d"),
        "end": end_at.strftime("%Y%m%d"),
    }
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            EASTMONEY_KLINE_ENDPOINT,
            params=params,
            headers=EASTMONEY_HEADERS,
            timeout=15,
            proxies={"http": None, "https": None},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        LOGGER.warning("eastmoney index kline fallback failed [%s]: %s", symbol, exc)
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    klines = data.get("klines") if isinstance(data, dict) else None
    if not isinstance(klines, list):
        return []

    rows: list[dict] = []
    for item in klines:
        parts = str(item or "").split(",")
        if len(parts) < 6:
            continue
        row_date = _to_date(parts[0])
        if row_date is None:
            continue
        if as_of is not None and row_date > as_of:
            continue
        open_val = _safe_float(parts[1])
        close_val = _safe_float(parts[2])
        high_val = _safe_float(parts[3])
        low_val = _safe_float(parts[4])
        volume_val = _safe_float(parts[5])
        if None in (open_val, high_val, low_val, close_val, volume_val):
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": row_date,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "volume": volume_val,
            }
        )
    rows.sort(key=lambda item: (item["date"], item["symbol"]))
    if count > 0:
        rows = rows[-count:]
    if rows:
        LOGGER.info("eastmoney index kline fallback loaded [%s] rows=%s", symbol, len(rows))
    return rows


def _get_index_kline_history(
    symbol: str,
    *,
    period: str = "day",
    count: int = 240,
    as_of: date | None = None,
) -> List[dict]:
    if ak is None or pd is None:
        return []
    code = symbol.split(".")[0]
    period_map = {"day": "daily", "week": "weekly", "month": "monthly"}
    ak_period = period_map.get(period, "daily")
    end_at = as_of or date.today()
    lookback = {"day": max(400, count * 3), "week": max(800, count * 14), "month": max(1500, count * 40)}.get(period, count * 3)
    start_at = end_at - timedelta(days=lookback)
    try:
        df = ak.index_zh_a_hist(
            symbol=code,
            period=ak_period,
            start_date=start_at.strftime("%Y%m%d"),
            end_date=end_at.strftime("%Y%m%d"),
        )
    except Exception as exc:
        LOGGER.warning("akshare index_zh_a_hist failed [%s]: %s", symbol, exc)
        return _get_index_kline_history_from_eastmoney(symbol, period=period, count=count, as_of=as_of)
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    for record in df.to_dict(orient="records"):
        row_date = _to_date(record.get("日期") or record.get("date"))
        if row_date is None:
            continue
        if as_of is not None and row_date > as_of:
            continue
        open_val = _safe_float(record.get("开盘") or record.get("open"))
        high_val = _safe_float(record.get("最高") or record.get("high"))
        low_val = _safe_float(record.get("最低") or record.get("low"))
        close_val = _safe_float(record.get("收盘") or record.get("close"))
        volume_val = _safe_float(record.get("成交量") or record.get("volume"))
        if None in (open_val, high_val, low_val, close_val, volume_val):
            continue
        rows.append({
            "symbol": symbol,
            "date": row_date,
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "volume": volume_val,
        })
    rows.sort(key=lambda item: (item["date"], item["symbol"]))
    if count > 0:
        rows = rows[-count:]
    return rows


def get_daily_history(symbol: str, *, count: int = 480, as_of: date | None = None) -> List[dict]:
    return get_kline_history(symbol, period="day", count=count, as_of=as_of)


def get_index_history(symbol: str, *, count: int = 480, as_of: date | None = None) -> List[dict]:
    return get_kline_history(symbol, period="day", count=count, as_of=as_of, is_index=True)


# ---------- 批量日线价格 ----------
def get_daily_prices(symbols, as_of: date, *, workers: int | None = None) -> List[dict]:
    unique: list[str] = []
    seen: set[str] = set()
    for s in symbols or []:
        sym = normalize_symbol(str(s))
        if sym and sym not in seen:
            seen.add(sym)
            unique.append(sym)
    if not unique:
        return []

    rows: list[dict] = []
    # 简化：逐个获取最后一条 K 线
    for sym in unique:
        hist = get_kline_history(sym, period="day", count=30, as_of=as_of)
        if hist:
            rows.append(hist[-1])
    return ensure_required(rows, ["symbol", "date", "open", "high", "low", "close", "volume"], "akshare.daily")


# ---------- 月线价格 ----------
def get_monthly_prices(symbols, as_of: date) -> List[dict]:
    unique: list[str] = []
    seen: set[str] = set()
    for s in symbols or []:
        sym = normalize_symbol(str(s))
        if sym and sym not in seen:
            seen.add(sym)
            unique.append(sym)
    if not unique:
        return []

    rows: list[dict] = []
    for sym in unique:
        hist = get_kline_history(sym, period="month", count=60, as_of=as_of)
        if hist:
            # 找到 as_of 当天或之前的最近一个月线
            best = None
            for item in hist:
                item_date = item.get("date")
                if isinstance(item_date, datetime):
                    item_date = item_date.date()
                if item_date is None or item_date > as_of:
                    continue
                if best is None or item_date > best["date"]:
                    best = item
            if best:
                rows.append(best)
    return ensure_required(rows, ["symbol", "date", "open", "high", "low", "close", "volume"], "akshare.monthly")


# ---------- 指数日线 ----------
def get_index_daily(as_of: date) -> List[dict]:
    if ak is None or pd is None:
        return []
    rows: list[dict] = []
    for local_symbol in _index_map().keys():
        hist = get_kline_history(local_symbol, period="day", count=30, as_of=as_of, is_index=True)
        if hist:
            best = hist[-1]
            close_val = best.get("close")
            preclose = close_val  # 简化为相同值，如果需要可用前一日
            if len(hist) >= 2:
                preclose = hist[-2].get("close")
            change = (close_val - preclose) if close_val is not None and preclose is not None else 0.0
            rows.append({
                "symbol": local_symbol,
                "date": best.get("date") or as_of,
                "close": close_val,
                "change": change,
            })
    return ensure_required(rows, ["symbol", "date", "close", "change"], "akshare.index_daily")


# ---------- 财务数据 ----------
def get_financials(symbol: str, period: str) -> dict:
    normalized = normalize_symbol(symbol)
    if ak is None or pd is None:
        return {}
    try:
        code = normalized.split(".")[0]
        df = ak.stock_financial_abstract(symbol=code)
    except Exception as exc:
        LOGGER.warning("akshare stock_financial_abstract failed [%s]: %s", normalized, exc)
        return {}
    if df is None or getattr(df, "empty", True):
        return {}

    # df columns: 选项, 指标, 20260331, 20251231...
    # 找到与 period 匹配的列（如 202512）
    target_prefix = period[:6] if len(period) >= 6 else period
    matched_col: str | None = None
    for col in df.columns:
        if str(col).startswith(target_prefix):
            matched_col = str(col)
            break
    if matched_col is None:
        # 使用最近一期
        numeric_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 8]
        if numeric_cols:
            matched_col = sorted(numeric_cols)[-1]
        else:
            return {}

    data = dict(zip(df["指标"], df[matched_col]))

    revenue = _safe_float(data.get("营业总收入") or data.get("营业收入") or data.get("总收入")) or 0.0
    net_income = _safe_float(data.get("归母净利润") or data.get("净利润") or data.get("归属于母公司股东的净利润")) or 0.0
    cash_flow = _safe_float(data.get("经营活动产生的现金流量净额") or data.get("经营现金流")) or 0.0
    roe = _safe_float(data.get("净资产收益率") or data.get("ROE")) or 0.0
    debt_ratio = _safe_float(data.get("资产负债率") or data.get("负债率")) or 0.0
    if debt_ratio > 1:
        debt_ratio = debt_ratio / 100.0

    row = {
        "symbol": normalized,
        "period": matched_col[:6] if matched_col else period,
        "revenue": float(revenue),
        "net_income": float(net_income),
        "cash_flow": float(cash_flow),
        "roe": float(roe),
        "debt_ratio": float(debt_ratio),
    }
    return row if any(abs(v) > 1e-12 for k, v in row.items() if k != "symbol" and k != "period") else {}


def get_recent_financials(symbol: str, *, count: int = 8, as_of: date | None = None) -> List[dict]:
    target = as_of or date.today()
    month = ((target.month - 1) // 3 + 1) * 3
    quarter_end = date(target.year, month, 1)
    if month == 12:
        quarter_end = quarter_end.replace(day=31)
    else:
        quarter_end = date(quarter_end.year, quarter_end.month + 1, 1) - timedelta(days=1)
    if quarter_end > target:
        month -= 3
        if month <= 0:
            month += 12
            year = target.year - 1
        else:
            year = target.year
        quarter_end = date(year, month, 1)
        if month == 12:
            quarter_end = quarter_end.replace(day=31)
        else:
            quarter_end = date(quarter_end.year, quarter_end.month + 1, 1) - timedelta(days=1)

    periods: list[str] = []
    current = quarter_end
    for _ in range(max(1, count)):
        periods.append(f"{current.year:04d}{current.month:02d}")
        month = current.month - 3
        year = current.year
        if month <= 0:
            month += 12
            year -= 1
        current = date(year, month, 1)
        if month == 12:
            current = current.replace(day=31)
        else:
            current = date(current.year, current.month + 1, 1) - timedelta(days=1)

    deduped: dict[str, dict] = {}
    for period in periods:
        row = get_financials(symbol, period)
        actual_period = row.get("period") if row else None
        if row and actual_period:
            deduped[str(actual_period)] = row
    return sorted(deduped.values(), key=lambda item: item["period"], reverse=True)


# ---------- 研报 ----------
def get_stock_reports(symbol: str, *, limit: int = 10) -> List[dict]:
    normalized = normalize_symbol(symbol)
    if ak is None or pd is None:
        return []
    try:
        code = normalized.split(".")[0]
        df = ak.stock_research_report_em(symbol=code)
    except Exception as exc:
        LOGGER.warning("akshare stock_research_report_em failed [%s]: %s", normalized, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for record in df.to_dict(orient="records"):
        title = str(record.get("报告标题") or record.get("title") or "").strip()
        if not title:
            continue
        institution = str(record.get("机构") or record.get("机构名称") or record.get("institution") or "").strip()
        rating = str(record.get("评级") or record.get("rating") or "").strip()
        pub_date = _to_date(record.get("日期") or record.get("date") or record.get("publish_date"))
        link = str(record.get("报告PDF链接") or record.get("link") or "").strip()
        key = (title, link)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "title": title,
            "published_at": pub_date,
            "link": link,
            "summary": "",
            "institution": institution,
            "rating": rating,
            "source": "AkShare Research Report",
        })
    rows.sort(key=lambda item: item.get("published_at") or datetime.min, reverse=True)
    return rows[: max(1, limit)]


# ---------- 盈利预测 ----------
def get_stock_earning_forecasts(symbol: str, *, limit: int = 10) -> List[dict]:
    normalized = normalize_symbol(symbol)
    if ak is None or pd is None:
        return []
    try:
        code = normalized.split(".")[0]
        df = ak.stock_profit_forecast_em(symbol=code)
    except Exception as exc:
        LOGGER.warning("akshare stock_profit_forecast_em failed [%s]: %s", normalized, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for record in df.to_dict(orient="records"):
        title = str(record.get("报告标题") or record.get("title") or "").strip()
        if not title:
            continue
        institution = str(record.get("机构") or record.get("institution") or "").strip()
        rating = str(record.get("评级") or record.get("rating") or "").strip()
        pub_date = _to_date(record.get("日期") or record.get("date"))
        link = str(record.get("链接") or record.get("link") or "").strip()
        key = (title, link)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "title": title,
            "published_at": pub_date,
            "link": link,
            "summary": "",
            "institution": institution,
            "rating": rating,
            "source": "AkShare Profit Forecast",
        })
    rows.sort(key=lambda item: item.get("published_at") or datetime.min, reverse=True)
    return rows[: max(1, limit)]


# ---------- 搜索 ----------
def search_stocks(keyword: str, market: str | None = None, limit: int = 50) -> List[dict]:
    if not keyword.strip():
        return []
    # AkShare 没有直接的股票搜索接口，使用基础信息过滤
    basics = get_stock_basics()
    kw_upper = keyword.strip().upper()
    candidates: list[dict] = []
    seen: set[str] = set()
    for row in basics:
        symbol = row.get("symbol", "")
        name = row.get("name", "")
        if kw_upper in symbol.upper() or kw_upper in name.upper():
            if market and row.get("market") != market.upper():
                continue
            if symbol in seen:
                continue
            seen.add(symbol)
            candidates.append(row)
            if len(candidates) >= limit:
                break
    return candidates


def get_market_stock_pool(market: str, *, limit: int = 100) -> List[dict]:
    basics = get_stock_basics()
    target = market.upper()
    result = [row for row in basics if row.get("market") == target][:limit]
    return result
