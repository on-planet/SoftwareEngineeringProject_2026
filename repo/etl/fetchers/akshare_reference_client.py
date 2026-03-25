from __future__ import annotations

from datetime import date, datetime
import json
from typing import Iterable

import pandas as pd

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ak = None
    LOGGER.warning("akshare import failed for reference data: %s", exc)


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _safe_text(value: object, max_length: int = 255) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return ""
    return text[:max_length]


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() == "nan":
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


def _safe_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    try:
        parsed = pd.to_datetime(text, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _pick(record: dict, keys: Iterable[str]) -> object:
    for key in keys:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return None


def _symbol_or_none(value: object) -> str | None:
    token = _safe_text(value, 32)
    if not token:
        return None
    normalized = normalize_symbol(token)
    return normalized or None


def _plain_row(record: dict) -> dict:
    output: dict[str, object] = {}
    for key, value in record.items():
        if isinstance(value, (datetime, date)):
            output[str(key)] = value.isoformat()
        elif hasattr(value, "item"):
            try:
                output[str(key)] = value.item()
            except Exception:
                output[str(key)] = str(value)
        else:
            output[str(key)] = value
    return output


def _raw_json(record: dict) -> str:
    return json.dumps(_plain_row(record), ensure_ascii=False, default=str)


def _call_akshare_frame(function_names: tuple[str, ...], **kwargs) -> tuple[pd.DataFrame, str]:
    if ak is None:
        return pd.DataFrame(), ""
    last_exception: Exception | None = None
    for function_name in function_names:
        func = getattr(ak, function_name, None)
        if not callable(func):
            continue
        try:
            frame = func(**kwargs)
        except Exception as exc:  # pragma: no cover - runtime env dependent
            last_exception = exc
            LOGGER.warning("akshare reference fetch failed [%s]: %s", function_name, exc)
            continue
        if isinstance(frame, pd.DataFrame):
            return frame.copy(), function_name
    if last_exception is not None:
        LOGGER.info("akshare reference fallback exhausted [%s]: %s", function_names, last_exception)
    return pd.DataFrame(), ""


def fetch_bond_market_quote_rows(*, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("get_bond_market_quote", "bond_spot_quote"))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        bond_name = _safe_text(record.get("债券简称"), 128)
        if not bond_name:
            continue
        rows.append(
            {
                "quote_org": _safe_text(record.get("报价机构"), 128),
                "bond_name": bond_name,
                "buy_net_price": _safe_float(record.get("买入净价")),
                "sell_net_price": _safe_float(record.get("卖出净价")),
                "buy_yield": _safe_float(record.get("买入收益率")),
                "sell_yield": _safe_float(record.get("卖出收益率")),
                "as_of": snapshot,
                "source": source or "bond_spot_quote",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_bond_market_trade_rows(*, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("get_bond_market_trade", "bond_spot_deal"))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        bond_name = _safe_text(record.get("债券简称"), 128)
        if not bond_name:
            continue
        rows.append(
            {
                "bond_name": bond_name,
                "deal_net_price": _safe_float(record.get("成交净价")),
                "latest_yield": _safe_float(record.get("最新收益率")),
                "change": _safe_float(record.get("涨跌")),
                "weighted_yield": _safe_float(record.get("加权收益率")),
                "volume": _safe_float(record.get("交易量")),
                "as_of": snapshot,
                "source": source or "bond_spot_deal",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_fx_spot_quote_rows(*, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("get_fx_spot_quote", "fx_spot_quote"))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        pair = _safe_text(record.get("货币对"), 32)
        if not pair:
            continue
        rows.append(
            {
                "currency_pair": pair,
                "bid": _safe_float(record.get("买报价")),
                "ask": _safe_float(record.get("卖报价")),
                "as_of": snapshot,
                "source": source or "fx_spot_quote",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_fx_swap_quote_rows(*, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("get_fx_swap_quote", "fx_swap_quote"))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        pair = _safe_text(record.get("货币对"), 32)
        if not pair:
            continue
        rows.append(
            {
                "currency_pair": pair,
                "one_week": _safe_float(record.get("1周")),
                "one_month": _safe_float(record.get("1月")),
                "three_month": _safe_float(record.get("3月")),
                "six_month": _safe_float(record.get("6月")),
                "nine_month": _safe_float(record.get("9月")),
                "one_year": _safe_float(record.get("1年")),
                "as_of": snapshot,
                "source": source or "fx_swap_quote",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_fx_pair_quote_rows(*, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("get_fx_pair_quote", "fx_pair_quote"))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        pair = _safe_text(record.get("货币对"), 32)
        if not pair:
            continue
        rows.append(
            {
                "currency_pair": pair,
                "bid": _safe_float(record.get("买报价")),
                "ask": _safe_float(record.get("卖报价")),
                "as_of": snapshot,
                "source": source or "fx_pair_quote",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_stock_institute_hold_rows(quarter: str, *, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("stock_institute_hold",), symbol=str(quarter))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        symbol = _symbol_or_none(record.get("证券代码"))
        if not symbol:
            continue
        rows.append(
            {
                "quarter": str(quarter),
                "symbol": symbol,
                "stock_name": _safe_text(record.get("证券简称"), 128),
                "institute_count": _safe_float(record.get("机构数")),
                "institute_count_change": _safe_float(record.get("机构数变化")),
                "holding_ratio": _safe_float(record.get("持股比例")),
                "holding_ratio_change": _safe_float(record.get("持股比例增幅")),
                "float_holding_ratio": _safe_float(record.get("占流通股比例")),
                "float_holding_ratio_change": _safe_float(record.get("占流通股比例增幅")),
                "as_of": snapshot,
                "source": source or "stock_institute_hold",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_stock_institute_hold_detail_rows(stock_symbol: str, quarter: str, *, as_of: datetime | None = None) -> list[dict]:
    plain_code = normalize_symbol(stock_symbol).split(".")[0]
    frame, source = _call_akshare_frame(("stock_institute_hold_detail",), stock=plain_code, quarter=str(quarter))
    snapshot = as_of or _now()
    normalized_symbol = normalize_symbol(stock_symbol)
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        rows.append(
            {
                "quarter": str(quarter),
                "stock_symbol": normalized_symbol,
                "institute_type": _safe_text(record.get("持股机构类型"), 64),
                "institute_code": _safe_text(record.get("持股机构代码"), 64),
                "institute_name": _safe_text(record.get("持股机构简称"), 128),
                "institute_full_name": _safe_text(record.get("持股机构全称"), 255),
                "shares": _safe_float(record.get("持股数")),
                "latest_shares": _safe_float(record.get("最新持股数")),
                "holding_ratio": _safe_float(record.get("持股比例")),
                "latest_holding_ratio": _safe_float(record.get("最新持股比例")),
                "float_holding_ratio": _safe_float(record.get("占流通股比例")),
                "latest_float_holding_ratio": _safe_float(record.get("最新占流通股比例")),
                "holding_ratio_change": _safe_float(record.get("持股比例增幅")),
                "float_holding_ratio_change": _safe_float(record.get("占流通股比例增幅")),
                "as_of": snapshot,
                "source": source or "stock_institute_hold_detail",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def _recommend_metric(category: str, record: dict) -> tuple[str | None, float | None]:
    metric_map = {
        "目标涨幅排名": "平均目标涨幅",
        "机构关注度": "关注度",
        "行业关注度": "关注度",
        "股票综合评级": "综合评级",
    }
    preferred_key = metric_map.get(category)
    if preferred_key:
        value = _safe_float(record.get(preferred_key))
        if value is not None:
            return preferred_key, value
    ignored = {"股票代码", "股票简称", "股票名称", "名称", "评级日期", "评级", "最新评级", "综合评级"}
    for key, value in record.items():
        if str(key) in ignored:
            continue
        converted = _safe_float(value)
        if converted is not None:
            return str(key), converted
    return None, None


def fetch_stock_institute_recommend_rows(category: str, *, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("stock_institute_recommend",), symbol=str(category))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        metric_name, metric_value = _recommend_metric(category, record)
        symbol = _symbol_or_none(_pick(record, ("股票代码", "证券代码", "代码")))
        stock_name = _safe_text(_pick(record, ("股票简称", "股票名称", "证券简称", "名称")), 128)
        rows.append(
            {
                "category": str(category),
                "symbol": symbol,
                "stock_name": stock_name,
                "rating_date": _safe_date(_pick(record, ("评级日期", "日期"))),
                "rating": _safe_text(_pick(record, ("评级", "最新评级", "综合评级", "投资评级")), 64),
                "metric_name": metric_name,
                "metric_value": metric_value,
                "extra_text": _safe_text(_pick(record, ("评级机构", "机构", "行业", "评级明细")), 255),
                "as_of": snapshot,
                "source": source or "stock_institute_recommend",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_stock_institute_recommend_detail_rows(symbol: str, *, as_of: datetime | None = None) -> list[dict]:
    normalized_symbol = normalize_symbol(symbol)
    plain_code = normalized_symbol.split(".")[0]
    frame, source = _call_akshare_frame(("stock_institute_recommend_detail",), symbol=plain_code)
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        rows.append(
            {
                "symbol": normalized_symbol,
                "rating_date": _safe_date(_pick(record, ("评级日期", "日期"))),
                "institution": _safe_text(_pick(record, ("评级机构", "机构", "机构名称", "券商")), 128),
                "rating": _safe_text(_pick(record, ("最新评级", "评级", "投资评级")), 64),
                "previous_rating": _safe_text(_pick(record, ("上次评级", "前次评级", "评级变动前")), 64),
                "target_price": _safe_float(_pick(record, ("目标价", "目标价格", "平均目标价"))),
                "title": _safe_text(_pick(record, ("标题", "报告标题", "股票简称")), 255),
                "as_of": snapshot,
                "source": source or "stock_institute_recommend_detail",
                "raw_json": _raw_json(record),
            }
        )
    return rows


def fetch_stock_report_disclosure_rows(market: str, period: str, *, as_of: datetime | None = None) -> list[dict]:
    frame, source = _call_akshare_frame(("stock_report_disclosure",), market=str(market), period=str(period))
    snapshot = as_of or _now()
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        symbol = _symbol_or_none(record.get("股票代码"))
        if not symbol:
            continue
        rows.append(
            {
                "market": str(market),
                "period": str(period),
                "symbol": symbol,
                "stock_name": _safe_text(record.get("股票简称"), 128),
                "first_booking": _safe_date(record.get("首次预约")),
                "first_change": _safe_date(record.get("初次变更")),
                "second_change": _safe_date(record.get("二次变更")),
                "third_change": _safe_date(record.get("三次变更")),
                "actual_disclosure": _safe_date(record.get("实际披露")),
                "as_of": snapshot,
                "source": source or "stock_report_disclosure",
                "raw_json": _raw_json(record),
            }
        )
    return rows
