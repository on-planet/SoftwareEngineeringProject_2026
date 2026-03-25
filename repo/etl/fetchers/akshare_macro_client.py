from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import re
from typing import Iterable

import pandas as pd
import requests

from etl.transformers.macro import normalize_macro_rows
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ak = None
    LOGGER.warning("akshare import failed: %s", exc)


@dataclass(frozen=True)
class AkShareMacroSpec:
    function_name: str
    series_prefix: str
    region: str
    mode: str
    invert: bool = False
    field_aliases: tuple[str, ...] = ()
    group_aliases: tuple[str, ...] = ()


AKSHARE_MACRO_SPECS: tuple[AkShareMacroSpec, ...] = (
    AkShareMacroSpec("macro_china_gdp_yearly", "AK_CHN_GDP_YOY", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_cpi_yearly", "AK_CHN_CPI_YOY", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_cpi_monthly", "AK_CHN_CPI_MOM", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_ppi_yearly", "AK_CHN_PPI_YOY", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_m2_yearly", "AK_CHN_M2_YOY", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_exports_yoy", "AK_CHN_EXPORTS_YOY", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_imports_yoy", "AK_CHN_IMPORTS_YOY", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_trade_balance", "AK_CHN_TRADE_BALANCE", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_industrial_production_yoy", "AK_CHN_IP_YOY", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_pmi_yearly", "AK_CHN_PMI", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_cx_pmi_yearly", "AK_CHN_CAIXIN_PMI", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_cx_services_pmi_yearly", "AK_CHN_CAIXIN_SERVICES_PMI", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_non_man_pmi", "AK_CHN_NON_MAN_PMI", "CHN", "china_base"),
    AkShareMacroSpec("macro_china_fx_reserves_yearly", "AK_CHN_FX_RESERVES", "CHN", "china_base"),
    AkShareMacroSpec(
        "macro_bank_usa_interest_rate",
        "AK_USA_FED_RATE",
        "USA",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_euro_interest_rate",
        "AK_EUR_ECB_RATE",
        "EUR",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_newzealand_interest_rate",
        "AK_NZL_RBNZ_RATE",
        "NZL",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_switzerland_interest_rate",
        "AK_CHE_SNB_RATE",
        "CHE",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_english_interest_rate",
        "AK_GBR_BOE_RATE",
        "GBR",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_australia_interest_rate",
        "AK_AUS_RBA_RATE",
        "AUS",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_japan_interest_rate",
        "AK_JPN_BOJ_RATE",
        "JPN",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_russia_interest_rate",
        "AK_RUS_CBR_RATE",
        "RUS",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_india_interest_rate",
        "AK_IND_RBI_RATE",
        "IND",
        "report_labeled",
    ),
    AkShareMacroSpec(
        "macro_bank_brazil_interest_rate",
        "AK_BRA_BCB_RATE",
        "BRA",
        "report_labeled",
    ),
    AkShareMacroSpec("macro_usa_cpi_yoy", "AK_USA_CPI_YOY", "USA", "report"),
    AkShareMacroSpec("macro_usa_gdp_monthly", "AK_USA_GDP", "USA", "report"),
    AkShareMacroSpec("macro_usa_retail_sales", "AK_USA_RETAIL_SALES", "USA", "report"),
    AkShareMacroSpec("macro_usa_unemployment_rate", "AK_USA_UNEMP", "USA", "report", invert=True),
    AkShareMacroSpec("macro_usa_non_farm", "AK_USA_NON_FARM", "USA", "report"),
    AkShareMacroSpec("macro_usa_core_pce_price", "AK_USA_CORE_PCE", "USA", "report"),
    AkShareMacroSpec("macro_euro_gdp_yoy", "AK_EUR_GDP_YOY", "EUR", "report"),
    AkShareMacroSpec("macro_euro_cpi_yoy", "AK_EUR_CPI_YOY", "EUR", "report"),
    AkShareMacroSpec("macro_euro_unemployment_rate_mom", "AK_EUR_UNEMP", "EUR", "report", invert=True),
    AkShareMacroSpec(
        "macro_china_commodity_price_index",
        "AK_CHN_COMMODITY_PRICE",
        "CHN",
        "wide",
        field_aliases=("VALUE", "CHANGE", "CHG_3M", "CHG_6M", "CHG_1Y", "CHG_2Y", "CHG_3Y"),
    ),
    AkShareMacroSpec(
        "macro_china_energy_index",
        "AK_CHN_ENERGY_INDEX",
        "CHN",
        "wide",
        field_aliases=("VALUE", "CHANGE", "CHG_3M", "CHG_6M", "CHG_1Y", "CHG_2Y", "CHG_3Y"),
    ),
    AkShareMacroSpec(
        "macro_china_fdi",
        "AK_CHN_FDI",
        "CHN",
        "wide",
        field_aliases=("CURRENT", "CURRENT_YOY", "CURRENT_MOM", "CUMULATIVE", "CUMULATIVE_YOY"),
    ),
    AkShareMacroSpec(
        "macro_china_lpr",
        "AK_CHN_LPR",
        "CHN",
        "wide",
        field_aliases=("LPR_1Y", "LPR_5Y", "RATE_1", "RATE_2"),
    ),
    AkShareMacroSpec("macro_china_urban_unemployment", "AK_CHN_URBAN_UNEMP", "CHN", "china_base", invert=True),
    AkShareMacroSpec(
        "macro_china_shrzgm",
        "AK_CHN_SOCIAL_FINANCING",
        "CHN",
        "wide",
        field_aliases=(
            "TOTAL",
            "RMB_LOAN",
            "FX_LOAN",
            "ENTRUSTED_LOAN",
            "TRUST_LOAN",
            "BANK_ACCEPTANCE",
            "CORP_BOND",
            "EQUITY_FINANCING",
        ),
    ),
    AkShareMacroSpec(
        "macro_china_new_financial_credit",
        "AK_CHN_NEW_FIN_CREDIT",
        "CHN",
        "wide",
        field_aliases=("CURRENT", "CURRENT_YOY", "CURRENT_MOM", "CUMULATIVE", "CUMULATIVE_YOY"),
    ),
    AkShareMacroSpec(
        "macro_china_new_house_price",
        "AK_CHN_NEW_HOUSE_PRICE",
        "CHN",
        "house_price",
        field_aliases=("NEW_YOY", "NEW_MOM", "NEW_BASE", "SECOND_YOY", "SECOND_MOM", "SECOND_BASE"),
        group_aliases=("BJ", "SH"),
    ),
    AkShareMacroSpec(
        "macro_china_enterprise_boom_index",
        "AK_CHN_ENTERPRISE_BOOM",
        "CHN",
        "wide",
        field_aliases=("BOOM_INDEX", "BOOM_YOY", "BOOM_MOM", "CONFIDENCE_INDEX", "CONFIDENCE_YOY", "CONFIDENCE_MOM"),
    ),
    AkShareMacroSpec(
        "macro_china_national_tax_receipts",
        "AK_CHN_TAX_RECEIPTS",
        "CHN",
        "wide",
        field_aliases=("TOTAL", "YOY", "QOQ"),
    ),
    AkShareMacroSpec(
        "macro_cnbs",
        "AK_CNBS",
        "CHN",
        "wide",
        field_aliases=(
            "HOUSEHOLD",
            "NON_FIN_CORP",
            "GENERAL_GOV",
            "CENTRAL_GOV",
            "LOCAL_GOV",
            "REAL_ECONOMY",
            "FIN_ASSET",
            "FIN_LIABILITY",
        ),
    ),
)


def _build_series_keys() -> tuple[str, ...]:
    keys: set[str] = set()
    for spec in AKSHARE_MACRO_SPECS:
        if spec.mode == "china_base":
            keys.add(f"{spec.series_prefix}:{spec.region}")
            continue
        if spec.mode in {"report", "report_labeled"}:
            for alias in ("ACTUAL", "FORECAST", "PREVIOUS"):
                keys.add(f"{spec.series_prefix}_{alias}:{spec.region}")
            continue
        if spec.mode == "house_price":
            for group_alias in spec.group_aliases:
                for alias in spec.field_aliases:
                    keys.add(f"{spec.series_prefix}_{group_alias}_{alias}:{spec.region}")
            continue
        for alias in spec.field_aliases:
            keys.add(f"{spec.series_prefix}_{alias}:{spec.region}")
    return tuple(sorted(keys))


AKSHARE_MACRO_SERIES_KEYS = _build_series_keys()
AKSHARE_MACRO_KEY_COUNT = len(AKSHARE_MACRO_SERIES_KEYS)


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    quarter_match = re.search(r"(\d{4})\s*[年/-]?\s*(?:Q|第)?\s*([1-4])\s*季", text, flags=re.IGNORECASE)
    if quarter_match:
        year = int(quarter_match.group(1))
        quarter = int(quarter_match.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)
    quarter_match_alt = re.search(r"(\d{4})\s*Q\s*([1-4])", text, flags=re.IGNORECASE)
    if quarter_match_alt:
        year = int(quarter_match_alt.group(1))
        quarter = int(quarter_match_alt.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)

    month_range_match = re.search(r"(\d{4})\s*年\s*(\d{1,2})(?:\s*[-~至]\s*(\d{1,2}))?\s*月", text)
    if month_range_match:
        year = int(month_range_match.group(1))
        month_start = int(month_range_match.group(2))
        month_end = int(month_range_match.group(3) or month_start)
        month = min(12, max(1, month_end))
        return date(year, month, 1)

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%Y%m%d", "%Y"):
        try:
            parsed = datetime.strptime(text[: len(fmt)], fmt)
        except Exception:
            continue
        if fmt == "%Y":
            return date(parsed.year, 1, 1)
        if fmt in {"%Y-%m", "%Y/%m"}:
            return date(parsed.year, parsed.month, 1)
        return parsed.date()

    digits_only = re.sub(r"\D", "", text)
    if len(digits_only) == 6:
        try:
            return datetime.strptime(digits_only, "%Y%m").date().replace(day=1)
        except Exception:
            pass

    try:
        parsed = pd.to_datetime(text, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).replace(",", "").replace("%", "").strip())
    except Exception:
        return None
    if number != number:
        return None
    return number


def _normalize_grouped_rows(rows: Iterable[dict], *, invert: bool = False) -> list[dict]:
    by_key: dict[str, list[dict]] = {}
    for row in rows:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        by_key.setdefault(key, []).append(row)
    output: list[dict] = []
    for key, items in by_key.items():
        items.sort(key=lambda item: item.get("date") or date.min)
        output.extend(normalize_macro_rows(items, invert=invert))
    return output


def _normalize_alias_token(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", str(text or "").strip()).strip("_").upper()
    if cleaned:
        return cleaned
    digest = hashlib.md5(str(text or "").encode("utf-8")).hexdigest()[:8].upper()
    return f"X{digest}"


def _fetch_macro_china_shrzgm_fallback() -> pd.DataFrame:
    url_candidates = (
        ("https://data.mofcom.gov.cn/datamofcom/front/gnmy/shrzgmQuery", True),
        ("https://data.mofcom.gov.cn/datamofcom/front/gnmy/shrzgmQuery", False),
        ("http://data.mofcom.gov.cn/datamofcom/front/gnmy/shrzgmQuery", None),
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
    }
    for url, verify in url_candidates:
        try:
            request_kwargs = {"headers": headers, "timeout": 20}
            if verify is not None and url.startswith("https://"):
                request_kwargs["verify"] = verify
            response = requests.post(url, **request_kwargs)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                continue
            df = pd.DataFrame(payload)
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception as exc:
            LOGGER.warning("akshare macro shrzgm fallback failed [%s verify=%s]: %s", url, verify, exc)
            continue
    return pd.DataFrame()


def _call_akshare_function(spec: AkShareMacroSpec) -> pd.DataFrame:
    if ak is None:
        return pd.DataFrame()
    func = getattr(ak, spec.function_name, None)
    if func is None:
        LOGGER.warning("akshare macro function missing: %s", spec.function_name)
        return pd.DataFrame()
    try:
        df = func()
    except Exception as exc:
        LOGGER.warning("akshare macro fetch failed [%s]: %s", spec.function_name, exc)
        if spec.function_name == "macro_china_shrzgm":
            fallback_df = _fetch_macro_china_shrzgm_fallback()
            if not fallback_df.empty:
                LOGGER.info("akshare macro fallback loaded rows for [%s]: %s", spec.function_name, len(fallback_df))
                return fallback_df
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame) or df.empty:
        if spec.function_name == "macro_china_shrzgm":
            fallback_df = _fetch_macro_china_shrzgm_fallback()
            if not fallback_df.empty:
                LOGGER.info("akshare macro fallback loaded rows for [%s]: %s", spec.function_name, len(fallback_df))
                return fallback_df
        return pd.DataFrame()
    return df.copy()


def _flatten_china_base(spec: AkShareMacroSpec, df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, record in df.iterrows():
        row_date = _to_date(record.iloc[0] if len(record) > 0 else None)
        value = _to_float(record.iloc[-1] if len(record) > 0 else None)
        if row_date is None or value is None:
            continue
        rows.append({"key": f"{spec.series_prefix}:{spec.region}", "date": row_date, "value": value})
    return _normalize_grouped_rows(rows, invert=spec.invert)


def _report_aliases(numeric_count: int) -> tuple[str, ...]:
    if numeric_count >= 3:
        return ("ACTUAL", "FORECAST", "PREVIOUS")
    if numeric_count == 2:
        return ("ACTUAL", "PREVIOUS")
    if numeric_count == 1:
        return ("ACTUAL",)
    return ()


def _flatten_report(spec: AkShareMacroSpec, df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, record in df.iterrows():
        row_date = _to_date(record.iloc[0] if len(record) > 0 else None)
        if row_date is None:
            continue
        numeric_values: list[float] = []
        for value in record.iloc[1:]:
            converted = _to_float(value)
            if converted is None:
                continue
            numeric_values.append(converted)
        aliases = _report_aliases(len(numeric_values))
        for alias, value in zip(aliases, numeric_values):
            rows.append({"key": f"{spec.series_prefix}_{alias}:{spec.region}", "date": row_date, "value": value})
    return _normalize_grouped_rows(rows, invert=spec.invert)


def _flatten_report_labeled(spec: AkShareMacroSpec, df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, record in df.iterrows():
        if len(record) < 3:
            continue
        row_date = _to_date(record.iloc[1])
        if row_date is None:
            continue
        numeric_values: list[float] = []
        for value in record.iloc[2:]:
            converted = _to_float(value)
            if converted is None:
                continue
            numeric_values.append(converted)
        aliases = _report_aliases(len(numeric_values))
        for alias, value in zip(aliases, numeric_values):
            rows.append({"key": f"{spec.series_prefix}_{alias}:{spec.region}", "date": row_date, "value": value})
    return _normalize_grouped_rows(rows, invert=spec.invert)


def _flatten_wide(spec: AkShareMacroSpec, df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, record in df.iterrows():
        row_date = _to_date(record.iloc[0] if len(record) > 0 else None)
        if row_date is None:
            continue
        for alias, value in zip(spec.field_aliases, record.iloc[1:]):
            converted = _to_float(value)
            if converted is None:
                continue
            rows.append({"key": f"{spec.series_prefix}_{alias}:{spec.region}", "date": row_date, "value": converted})
    return _normalize_grouped_rows(rows, invert=spec.invert)


def _flatten_house_price(spec: AkShareMacroSpec, df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    city_alias_map = {
        "北京": "BJ",
        "上海": "SH",
    }
    valid_groups = set(spec.group_aliases)
    for _, record in df.iterrows():
        if len(record) < 8:
            continue
        row_date = _to_date(record.iloc[0])
        if row_date is None:
            continue
        city_raw = str(record.iloc[1] or "").strip()
        city_alias = city_alias_map.get(city_raw, _normalize_alias_token(city_raw))
        if valid_groups and city_alias not in valid_groups:
            continue
        for alias, value in zip(spec.field_aliases, record.iloc[2:]):
            converted = _to_float(value)
            if converted is None:
                continue
            rows.append(
                {
                    "key": f"{spec.series_prefix}_{city_alias}_{alias}:{spec.region}",
                    "date": row_date,
                    "value": converted,
                }
            )
    return _normalize_grouped_rows(rows, invert=spec.invert)


def _flatten_dataframe(spec: AkShareMacroSpec, df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    if spec.mode == "china_base":
        return _flatten_china_base(spec, df)
    if spec.mode == "report":
        return _flatten_report(spec, df)
    if spec.mode == "report_labeled":
        return _flatten_report_labeled(spec, df)
    if spec.mode == "wide":
        return _flatten_wide(spec, df)
    if spec.mode == "house_price":
        return _flatten_house_price(spec, df)
    LOGGER.warning("unsupported akshare macro mode [%s] for %s", spec.mode, spec.function_name)
    return []


def _filter_rows_with_latest_fallback(
    rows: list[dict],
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    if not rows:
        return []

    filtered_by_end = [
        row for row in rows if isinstance(row.get("date"), date) and (end is None or row["date"] <= end)
    ]
    if start is None:
        return filtered_by_end

    by_key: dict[str, list[dict]] = {}
    for row in filtered_by_end:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        by_key.setdefault(key, []).append(row)

    output: list[dict] = []
    for items in by_key.values():
        in_range = [row for row in items if row["date"] >= start]
        if in_range:
            output.extend(in_range)
            continue
        latest_row = max(items, key=lambda item: item.get("date") or date.min)
        output.append(latest_row)
    output.sort(key=lambda item: (str(item.get("key") or ""), item.get("date") or date.min))
    return output


def fetch_akshare_rows_for_spec(spec: AkShareMacroSpec, *, start: date | None = None, end: date | None = None) -> list[dict]:
    df = _call_akshare_function(spec)
    rows = _flatten_dataframe(spec, df)
    return _filter_rows_with_latest_fallback(rows, start=start, end=end)


def fetch_all_akshare_macro_rows(*, start: date | None = None, end: date | None = None) -> list[dict]:
    rows: list[dict] = []
    for spec in AKSHARE_MACRO_SPECS:
        rows.extend(fetch_akshare_rows_for_spec(spec, start=start, end=end))
    return rows


def _find_spec_for_key(key: str) -> AkShareMacroSpec | None:
    normalized = str(key or "").strip().upper()
    for spec in AKSHARE_MACRO_SPECS:
        if normalized.startswith(f"{spec.series_prefix}:") or normalized.startswith(f"{spec.series_prefix}_"):
            return spec
    return None


def is_akshare_macro_key(key: str) -> bool:
    return _find_spec_for_key(key) is not None


def fetch_akshare_series_rows(key: str, start: date | None = None, end: date | None = None) -> list[dict]:
    spec = _find_spec_for_key(key)
    if spec is None:
        return []
    rows = fetch_akshare_rows_for_spec(spec, start=start, end=end)
    return [row for row in rows if str(row.get("key") or "").upper() == str(key or "").strip().upper()]
