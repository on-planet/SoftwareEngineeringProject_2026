from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Iterable

from etl.fetchers.snowball_client import (
    get_stock_earning_forecasts,
    get_kline_history,
    get_stock_pankou,
    get_stock_quote,
    get_stock_quote_detail,
    get_stock_reports,
    normalize_symbol,
)
from etl.loaders.pg_loader import (
    list_stock_intraday_meta,
    list_stock_live_snapshot_meta,
    upsert_stock_intraday_kline,
    upsert_stock_live_snapshots,
    upsert_stock_research_items,
)
from etl.utils.logging import get_logger
from etl.utils.stock_basics_cache import list_cached_symbols

LOGGER = get_logger(__name__)
STATE_DIR = Path(__file__).resolve().parents[1] / "state"
CHECKPOINT_PATH = STATE_DIR / "stock_detail_job_checkpoint.json"
STATUS_PATH = STATE_DIR / "stock_detail_job_status.json"
SECTION_WORKERS = max(1, int(os.getenv("STOCK_DETAIL_JOB_SECTION_WORKERS", "3")))
SNAPSHOT_WORKERS = max(1, int(os.getenv("STOCK_DETAIL_JOB_SNAPSHOT_WORKERS", "3")))
RESEARCH_WORKERS = max(1, int(os.getenv("STOCK_DETAIL_JOB_RESEARCH_WORKERS", "2")))
SNAPSHOT_MAX_AGE_HOURS = max(1, int(os.getenv("STOCK_DETAIL_SNAPSHOT_MAX_AGE_HOURS", "48")))
INTRADAY_MAX_AGE_HOURS = max(1, int(os.getenv("STOCK_DETAIL_INTRADAY_MAX_AGE_HOURS", "48")))
RESEARCH_MAX_AGE_HOURS = max(1, int(os.getenv("STOCK_DETAIL_RESEARCH_MAX_AGE_HOURS", "168")))
INTRADAY_REQUIRED_PERIODS = {"1m", "30m", "60m"}


def _snapshot_row(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    quote: dict = {}
    detail: dict = {}
    pankou: dict = {}
    with ThreadPoolExecutor(max_workers=SNAPSHOT_WORKERS, thread_name_prefix="stock_snapshot") as executor:
        future_map = {
            executor.submit(get_stock_quote, normalized): "quote",
            executor.submit(get_stock_quote_detail, normalized): "detail",
            executor.submit(get_stock_pankou, normalized): "pankou",
        }
        for future in as_completed(future_map):
            section = future_map[future]
            try:
                result = future.result() or {}
            except Exception as exc:
                LOGGER.warning("stock_detail_job snapshot %s failed [%s]: %s", section, normalized, exc)
                result = {}
            if section == "quote":
                quote = result
            elif section == "detail":
                detail = result
            elif section == "pankou":
                pankou = result
    if not quote and not detail and not pankou:
        return None
    return {
        "symbol": normalized,
        "as_of": datetime.now(),
        "current": quote.get("current"),
        "change": quote.get("change"),
        "percent": quote.get("percent"),
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "last_close": quote.get("last_close"),
        "volume": quote.get("volume"),
        "amount": quote.get("amount"),
        "turnover_rate": quote.get("turnover_rate"),
        "amplitude": quote.get("amplitude"),
        "quote_timestamp": quote.get("timestamp"),
        "pe_ttm": detail.get("pe_ttm"),
        "pb": detail.get("pb"),
        "ps_ttm": detail.get("ps_ttm"),
        "pcf": detail.get("pcf"),
        "market_cap": detail.get("market_cap"),
        "float_market_cap": detail.get("float_market_cap"),
        "dividend_yield": detail.get("dividend_yield"),
        "volume_ratio": detail.get("volume_ratio"),
        "lot_size": detail.get("lot_size"),
        "pankou_diff": pankou.get("diff"),
        "pankou_ratio": pankou.get("ratio"),
        "pankou_timestamp": pankou.get("timestamp"),
        "pankou_bids_json": json.dumps(pankou.get("bids") or [], ensure_ascii=False),
        "pankou_asks_json": json.dumps(pankou.get("asks") or [], ensure_ascii=False),
        "source": "snowball",
    }


def _research_rows(symbol: str, *, report_limit: int, forecast_limit: int) -> list[dict]:
    normalized = normalize_symbol(symbol)
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=RESEARCH_WORKERS, thread_name_prefix="stock_research") as executor:
        future_map = {
            executor.submit(get_stock_reports, normalized, limit=report_limit): "report",
            executor.submit(get_stock_earning_forecasts, normalized, limit=forecast_limit): "earning_forecast",
        }
        for future in as_completed(future_map):
            item_type = future_map[future]
            try:
                items = future.result() or []
            except Exception as exc:
                LOGGER.warning("stock_detail_job research %s failed [%s]: %s", item_type, normalized, exc)
                items = []
            for item in items:
                rows.append(
                    {
                        "symbol": normalized,
                        "item_type": item_type,
                        "title": item.get("title") or "",
                        "published_at": item.get("published_at"),
                        "link": item.get("link") or "",
                        "summary": item.get("summary"),
                        "institution": item.get("institution"),
                        "rating": item.get("rating"),
                        "source": item.get("source"),
                    }
                )
    return rows


def _intraday_rows(symbol: str) -> list[dict]:
    normalized = normalize_symbol(symbol)
    rows: list[dict] = []
    for period, count in (("1m", 240), ("30m", 240), ("60m", 240)):
        for item in get_kline_history(normalized, period=period, count=count, is_index=False):
            timestamp = item.get("date")
            if timestamp is None:
                continue
            rows.append(
                {
                    "symbol": normalized,
                    "period": period,
                    "timestamp": timestamp,
                    "open": item.get("open"),
                    "high": item.get("high"),
                    "low": item.get("low"),
                    "close": item.get("close"),
                    "volume": item.get("volume"),
                }
            )
    return rows


def _collect_symbol_payload(symbol: str, *, report_limit: int, forecast_limit: int) -> dict:
    normalized = normalize_symbol(symbol)
    payload: dict = {
        "symbol": normalized,
        "snapshot": None,
        "research": [],
        "intraday": [],
        "section_statuses": {"snapshot": False, "research": False, "intraday": False},
    }
    with ThreadPoolExecutor(max_workers=SECTION_WORKERS, thread_name_prefix="stock_detail_section") as executor:
        future_map = {
            executor.submit(_snapshot_row, normalized): "snapshot",
            executor.submit(_research_rows, normalized, report_limit=report_limit, forecast_limit=forecast_limit): "research",
            executor.submit(_intraday_rows, normalized): "intraday",
        }
        for future in as_completed(future_map):
            section = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                LOGGER.warning("stock_detail_job %s failed [%s]: %s", section, normalized, exc)
                continue
            payload["section_statuses"][section] = True
            if section == "snapshot":
                payload["snapshot"] = result
            elif section == "research":
                payload["research"] = result or []
            elif section == "intraday":
                payload["intraday"] = result or []
    return payload


def _target_symbols(
    *,
    symbols: Iterable[str] | None = None,
    markets: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    if symbols:
        output = []
        seen: set[str] = set()
        for item in symbols:
            symbol = normalize_symbol(item)
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            output.append(symbol)
        return output
    return list_cached_symbols(markets=markets or ("A", "HK"), limit=limit)


def _checkpoint_signature(
    target_symbols: list[str],
    *,
    report_limit: int,
    forecast_limit: int,
) -> str:
    payload = {
        "symbols": target_symbols,
        "report_limit": report_limit,
        "forecast_limit": forecast_limit,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _load_checkpoint(signature: str) -> int:
    if not CHECKPOINT_PATH.exists():
        return 0
    try:
        payload = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("stock_detail_job checkpoint load failed [%s]: %s", CHECKPOINT_PATH, exc)
        return 0
    if str(payload.get("signature") or "") != signature:
        return 0
    try:
        next_index = int(payload.get("next_index") or 0)
    except Exception:
        return 0
    return max(0, next_index)


def _save_checkpoint(signature: str, next_index: int, total: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "signature": signature,
        "next_index": max(0, next_index),
        "total": max(0, total),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    CHECKPOINT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clear_checkpoint(signature: str | None = None) -> None:
    if not CHECKPOINT_PATH.exists():
        return
    if signature is None:
        try:
            CHECKPOINT_PATH.unlink()
        except OSError:
            return
        return
    if _load_checkpoint(signature) >= 0:
        try:
            payload = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if str(payload.get("signature") or "") == signature:
            try:
                CHECKPOINT_PATH.unlink()
            except OSError:
                return


def _load_status_map() -> dict[str, dict]:
    if not STATUS_PATH.exists():
        return {}
    try:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("stock_detail_job status load failed [%s]: %s", STATUS_PATH, exc)
        return {}
    items = payload.get("items")
    return items if isinstance(items, dict) else {}


def _save_status_updates(updates: dict[str, dict]) -> None:
    if not updates:
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    merged = _load_status_map()
    merged.update(updates)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "items": merged,
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _is_fresh(value: object, *, max_age_hours: int) -> bool:
    dt = _parse_datetime(value)
    if dt is None:
        return False
    return (datetime.now() - dt).total_seconds() <= max_age_hours * 3600


def _load_snapshot_meta(symbols: list[str]) -> dict[str, dict]:
    target = set(symbols)
    return {
        str(row.get("symbol") or ""): row
        for row in list_stock_live_snapshot_meta()
        if str(row.get("symbol") or "") in target
    }


def _load_intraday_meta(symbols: list[str]) -> dict[str, dict]:
    target = set(symbols)
    return {
        str(row.get("symbol") or ""): row
        for row in list_stock_intraday_meta()
        if str(row.get("symbol") or "") in target
    }


def _research_is_fresh(symbol: str, status_map: dict[str, dict]) -> bool:
    row = status_map.get(symbol) or {}
    if _is_fresh(row.get("research_checked_at"), max_age_hours=RESEARCH_MAX_AGE_HOURS):
        return True
    return False


def _snapshot_is_fresh(symbol: str, snapshot_meta: dict[str, dict], status_map: dict[str, dict]) -> bool:
    if _is_fresh((snapshot_meta.get(symbol) or {}).get("as_of"), max_age_hours=SNAPSHOT_MAX_AGE_HOURS):
        return True
    row = status_map.get(symbol) or {}
    return bool(row.get("snapshot_has_data")) and _is_fresh(
        row.get("snapshot_checked_at"),
        max_age_hours=SNAPSHOT_MAX_AGE_HOURS,
    )


def _intraday_is_fresh(symbol: str, intraday_meta: dict[str, dict], status_map: dict[str, dict]) -> bool:
    meta = intraday_meta.get(symbol) or {}
    try:
        period_count = int(meta.get("period_count") or 0)
    except Exception:
        period_count = 0
    if period_count >= len(INTRADAY_REQUIRED_PERIODS) and _is_fresh(
        meta.get("latest_timestamp"),
        max_age_hours=INTRADAY_MAX_AGE_HOURS,
    ):
        return True
    row = status_map.get(symbol) or {}
    try:
        cached_period_count = int(row.get("intraday_period_count") or 0)
    except Exception:
        cached_period_count = 0
    return cached_period_count >= len(INTRADAY_REQUIRED_PERIODS) and _is_fresh(
        row.get("intraday_checked_at"),
        max_age_hours=INTRADAY_MAX_AGE_HOURS,
    )


def _filter_symbols_for_refresh(target_symbols: list[str]) -> tuple[list[str], int]:
    if not target_symbols:
        return [], 0
    status_map = _load_status_map()
    snapshot_meta = _load_snapshot_meta(target_symbols)
    intraday_meta = _load_intraday_meta(target_symbols)
    refresh_symbols: list[str] = []
    skipped = 0
    for symbol in target_symbols:
        snapshot_fresh = _snapshot_is_fresh(symbol, snapshot_meta, status_map)
        intraday_fresh = _intraday_is_fresh(symbol, intraday_meta, status_map)
        research_fresh = _research_is_fresh(symbol, status_map)
        if snapshot_fresh and intraday_fresh and research_fresh:
            skipped += 1
            continue
        if snapshot_fresh and intraday_fresh and not status_map.get(symbol):
            skipped += 1
            continue
        refresh_symbols.append(symbol)
    return refresh_symbols, skipped


def _status_updates_from_payloads(payloads: list[dict]) -> dict[str, dict]:
    processed_at = datetime.now().isoformat(timespec="seconds")
    updates: dict[str, dict] = {}
    for payload in payloads:
        symbol = normalize_symbol(str(payload.get("symbol") or ""))
        if not symbol:
            continue
        sections = payload.get("section_statuses") or {}
        row = updates.get(symbol, {})
        if sections.get("snapshot"):
            row["snapshot_checked_at"] = processed_at
            row["snapshot_has_data"] = bool(payload.get("snapshot"))
        if sections.get("research"):
            row["research_checked_at"] = processed_at
            row["research_count"] = len(payload.get("research") or [])
        if sections.get("intraday"):
            intraday_rows = payload.get("intraday") or []
            row["intraday_checked_at"] = processed_at
            row["intraday_period_count"] = len({str(item.get("period") or "") for item in intraday_rows if item.get("period")})
        updates[symbol] = row
    return updates


def _flush_batch_rows(snapshot_rows: list[dict], research_rows: list[dict], intraday_rows: list[dict]) -> tuple[int, int, int]:
    snapshot_count = upsert_stock_live_snapshots(snapshot_rows) if snapshot_rows else 0
    research_count = upsert_stock_research_items(research_rows) if research_rows else 0
    intraday_count = upsert_stock_intraday_kline(intraday_rows) if intraday_rows else 0
    return snapshot_count, research_count, intraday_count


def run_stock_detail_job(
    *,
    symbols: Iterable[str] | None = None,
    markets: Iterable[str] | None = None,
    limit: int | None = None,
    report_limit: int = 10,
    forecast_limit: int = 10,
    resume: bool = True,
    reset_progress: bool = False,
    force_refresh: bool = False,
) -> tuple[int, int]:
    target_symbols = _target_symbols(symbols=symbols, markets=markets, limit=limit)
    if not target_symbols:
        return 0, 0
    skipped_symbols = 0
    if not force_refresh:
        target_symbols, skipped_symbols = _filter_symbols_for_refresh(target_symbols)
        if not target_symbols:
            LOGGER.info("stock_detail_job all symbols are fresh; skipped=%s", skipped_symbols)
            return 0, 0
    start = time.perf_counter()
    max_workers = max(1, int(os.getenv("STOCK_DETAIL_JOB_WORKERS", "8")))
    batch_size = max(1, int(os.getenv("STOCK_DETAIL_JOB_BATCH_SIZE", "20")))
    progress_every = max(1, int(os.getenv("STOCK_DETAIL_JOB_PROGRESS_EVERY", "10")))
    signature = _checkpoint_signature(
        target_symbols,
        report_limit=report_limit,
        forecast_limit=forecast_limit,
    )
    if reset_progress:
        _clear_checkpoint()
    start_index = _load_checkpoint(signature) if resume else 0
    if start_index >= len(target_symbols):
        LOGGER.info("stock_detail_job checkpoint already complete symbols=%s", len(target_symbols))
        _clear_checkpoint(signature)
        return 0, 0
    snapshot_count_total = 0
    research_count_total = 0
    intraday_count_total = 0
    LOGGER.info(
        "stock_detail_job start symbols=%s resume_from=%s workers=%s batch_size=%s report_limit=%s forecast_limit=%s",
        len(target_symbols),
        start_index,
        min(max_workers, len(target_symbols)),
        batch_size,
        report_limit,
        forecast_limit,
    )
    if skipped_symbols:
        LOGGER.info("stock_detail_job skipped fresh symbols=%s", skipped_symbols)
    for batch_start in range(start_index, len(target_symbols), batch_size):
        batch_symbols = target_symbols[batch_start : batch_start + batch_size]
        batch_end = batch_start + len(batch_symbols)
        snapshot_rows: list[dict] = []
        research_rows: list[dict] = []
        intraday_rows: list[dict] = []
        completed_payloads: list[dict] = []
        completed_symbols = 0
        LOGGER.info(
            "stock_detail_job batch start symbols=%s-%s/%s",
            batch_start + 1,
            batch_end,
            len(target_symbols),
        )
        with ThreadPoolExecutor(max_workers=min(max_workers, len(batch_symbols))) as executor:
            future_map = {
                executor.submit(
                    _collect_symbol_payload,
                    symbol,
                    report_limit=report_limit,
                    forecast_limit=forecast_limit,
                ): symbol
                for symbol in batch_symbols
            }
            for future in as_completed(future_map):
                symbol = future_map[future]
                completed_symbols += 1
                try:
                    payload = future.result()
                except Exception as exc:
                    LOGGER.warning("stock_detail_job failed [%s]: %s", symbol, exc)
                    continue
                completed_payloads.append(payload)
                snapshot = payload.get("snapshot")
                if snapshot:
                    snapshot_rows.append(snapshot)
                research = payload.get("research") or []
                if research:
                    research_rows.extend(research)
                intraday = payload.get("intraday") or []
                if intraday:
                    intraday_rows.extend(intraday)
                if completed_symbols % progress_every == 0 or completed_symbols == len(batch_symbols):
                    completed_total = batch_start + completed_symbols
                    progress_end = min(batch_end, batch_start + completed_symbols)
                    progress_start = batch_start + 1 if batch_symbols else batch_start
                    LOGGER.info(
                        "stock_detail_job progress symbols=%s/%s current_batch=%s-%s snapshots=%s research=%s intraday=%s",
                        completed_total,
                        len(target_symbols),
                        progress_start,
                        progress_end,
                        len(snapshot_rows),
                        len(research_rows),
                        len(intraday_rows),
                    )
        snapshot_count, research_count, intraday_count = _flush_batch_rows(snapshot_rows, research_rows, intraday_rows)
        snapshot_count_total += snapshot_count
        research_count_total += research_count
        intraday_count_total += intraday_count
        _save_status_updates(_status_updates_from_payloads(completed_payloads))
        if resume:
            _save_checkpoint(signature, batch_end, len(target_symbols))
        LOGGER.info(
            "stock_detail_job batch done symbols=%s-%s/%s snapshots=%s research=%s intraday=%s",
            batch_start + 1,
            batch_end,
            len(target_symbols),
            snapshot_count_total,
            research_count_total,
            intraday_count_total,
        )
    if resume:
        _clear_checkpoint(signature)
    LOGGER.info(
        "stock_detail_job symbols=%s snapshots=%s research=%s intraday=%s cost=%.2fs",
        len(target_symbols),
        snapshot_count_total,
        research_count_total,
        intraday_count_total,
        time.perf_counter() - start,
    )
    return snapshot_count_total, research_count_total
