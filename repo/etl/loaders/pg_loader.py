from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy import bindparam, create_engine, text
from datetime import date

from etl.config.loader import load_config
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _validate_rows(rows: Iterable[dict], required: Iterable[str], context: str) -> list[dict]:
    required_list = list(required)
    output: list[dict] = []
    for row in rows:
        if not row:
            continue
        missing = [key for key in required_list if row.get(key) is None]
        if missing:
            LOGGER.warning("[%s] 缺少字段 %s: %s", context, missing, row)
            continue
        output.append(row)
    return output


class PgLoader:
    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        execution_options: dict | None = None,
    ):
        engine_kwargs = {"pool_pre_ping": True}
        if pool_size is not None:
            engine_kwargs["pool_size"] = pool_size
        if max_overflow is not None:
            engine_kwargs["max_overflow"] = max_overflow
        self.engine = create_engine(database_url, **engine_kwargs)
        self.execution_options = execution_options or {"stream_results": True}

    @staticmethod
    def _chunk(rows: list[dict], chunk_size: int) -> Iterable[list[dict]]:
        for idx in range(0, len(rows), chunk_size):
            yield rows[idx : idx + chunk_size]

    def execute_many(self, sql: str, rows: Iterable[dict], *, chunk_size: int = 500) -> int:
        payload = [row for row in rows if row]
        if not payload:
            LOGGER.info("PgLoader received empty payload")
            return 0

        total = 0
        try:
            with self.engine.begin() as conn:
                for chunk in self._chunk(payload, chunk_size):
                    conn.execute(text(sql), chunk)
                    total += len(chunk)
        except Exception as exc:
            LOGGER.exception("PgLoader batch write failed: %s", exc, exc_info=exc)
            raise
        return total

    def query_all(self, sql: str, params: dict | None = None) -> list[dict]:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                return [dict(row._mapping) for row in result]
        except Exception as exc:
            LOGGER.exception("PgLoader query failed: %s", exc, exc_info=exc)
            raise

    def query_all_text(self, statement, params: dict | None = None) -> list[dict]:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(statement, params or {})
                return [dict(row._mapping) for row in result]
        except Exception as exc:
            LOGGER.exception("PgLoader query failed: %s", exc, exc_info=exc)
            raise


def _get_loader() -> PgLoader:
    config_path = Path(__file__).resolve().parents[1] / "config" / "settings.yml"
    config = load_config(config_path)
    if not config.postgres_url:
        raise ValueError("postgres_url 未配置")
    return PgLoader(
        config.postgres_url,
        pool_size=getattr(config, "postgres_pool_size", None),
        max_overflow=getattr(config, "postgres_max_overflow", None),
    )


def upsert_stocks(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO stocks (symbol, name, market, sector)
    VALUES (:symbol, :name, :market, :sector)
    ON CONFLICT (symbol)
    DO UPDATE SET name = EXCLUDED.name, market = EXCLUDED.market, sector = EXCLUDED.sector
    """
    payload = _validate_rows(rows, ["symbol"], "stocks")
    return _get_loader().execute_many(sql, payload)


def upsert_indices(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO indices (symbol, date, close, change)
    VALUES (:symbol, :date, :close, :change)
    ON CONFLICT (symbol, date)
    DO UPDATE SET close = EXCLUDED.close, change = EXCLUDED.change
    """
    payload = _validate_rows(rows, ["symbol", "date"], "indices")
    return _get_loader().execute_many(sql, payload)


def upsert_daily_prices(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO daily_prices (symbol, date, open, high, low, close, volume)
    VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
    ON CONFLICT (symbol, date)
    DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high,
        low = EXCLUDED.low, close = EXCLUDED.close, volume = EXCLUDED.volume
    """
    payload = _validate_rows(rows, ["symbol", "date"], "daily_prices")
    return _get_loader().execute_many(sql, payload)


def upsert_financials(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO financials (symbol, period, revenue, net_income, cash_flow, roe, debt_ratio)
    VALUES (:symbol, :period, :revenue, :net_income, :cash_flow, :roe, :debt_ratio)
    ON CONFLICT (symbol, period)
    DO UPDATE SET revenue = EXCLUDED.revenue, net_income = EXCLUDED.net_income,
        cash_flow = EXCLUDED.cash_flow, roe = EXCLUDED.roe, debt_ratio = EXCLUDED.debt_ratio
    """
    payload = _validate_rows(rows, ["symbol", "period"], "financials")
    return _get_loader().execute_many(sql, payload)


def upsert_fundamental_score(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO fundamental_score (symbol, score, summary, updated_at)
    VALUES (:symbol, :score, :summary, :updated_at)
    ON CONFLICT (symbol)
    DO UPDATE SET score = EXCLUDED.score, summary = EXCLUDED.summary, updated_at = EXCLUDED.updated_at
    """
    payload = _validate_rows(rows, ["symbol", "updated_at"], "fundamental_score")
    return _get_loader().execute_many(sql, payload)


def upsert_news(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO news (symbol, title, sentiment, published_at, link, source)
    VALUES (:symbol, :title, :sentiment, :published_at, :link, :source)
    """
    payload = _validate_rows(rows, ["symbol", "title", "published_at"], "news")
    return _get_loader().execute_many(sql, payload)


def upsert_events(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO events (symbol, type, title, date, link, source)
    VALUES (:symbol, :type, :title, :date, :link, :source)
    """
    payload = _validate_rows(rows, ["symbol", "title", "date"], "events")
    return _get_loader().execute_many(sql, payload)


def upsert_buyback(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO buyback (symbol, date, amount)
    VALUES (:symbol, :date, :amount)
    ON CONFLICT (symbol, date)
    DO UPDATE SET amount = EXCLUDED.amount
    """
    payload = _validate_rows(rows, ["symbol", "date"], "buyback")
    return _get_loader().execute_many(sql, payload)


def upsert_insider_trade(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO insider_trade (symbol, date, type, shares)
    VALUES (:symbol, :date, :type, :shares)
    """
    payload = _validate_rows(rows, ["symbol", "date"], "insider_trade")
    return _get_loader().execute_many(sql, payload)


def upsert_index_constituents(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO index_constituents (index_symbol, symbol, date, weight)
    VALUES (:index_symbol, :symbol, :date, :weight)
    ON CONFLICT (index_symbol, symbol, date)
    DO UPDATE SET weight = EXCLUDED.weight
    """
    payload = _validate_rows(rows, ["index_symbol", "symbol", "date"], "index_constituents")
    return _get_loader().execute_many(sql, payload)


def upsert_sector_exposure(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO sector_exposure (sector, market, value)
    VALUES (:sector, :market, :value)
    ON CONFLICT (sector, market)
    DO UPDATE SET value = EXCLUDED.value
    """
    payload = _validate_rows(rows, ["sector", "market"], "sector_exposure")
    return _get_loader().execute_many(sql, payload)


def upsert_macro(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO macro (key, date, value, score)
    VALUES (:key, :date, :value, :score)
    ON CONFLICT (key, date)
    DO UPDATE SET value = EXCLUDED.value, score = EXCLUDED.score
    """
    payload = _validate_rows(rows, ["key", "date"], "macro")
    return _get_loader().execute_many(sql, payload)


def upsert_futures_prices(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO futures_prices (symbol, name, date, open, high, low, close, volume, source)
    VALUES (:symbol, :name, :date, :open, :high, :low, :close, :volume, :source)
    ON CONFLICT (symbol, date)
    DO UPDATE SET
        name = EXCLUDED.name,
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume,
        source = EXCLUDED.source
    """
    payload = _validate_rows(rows, ["symbol", "date"], "futures_prices")
    return _get_loader().execute_many(sql, payload)


def list_daily_price_rows(as_of: date) -> list[dict]:
    sql = """
    SELECT symbol, date, open, high, low, close, volume
    FROM daily_prices
    WHERE date = :as_of
    ORDER BY symbol ASC
    """
    return _get_loader().query_all(sql, {"as_of": as_of})


def list_latest_macro_rows() -> list[dict]:
    sql = """
    SELECT m.key, m.date, m.value, m.score
    FROM macro AS m
    INNER JOIN (
        SELECT key, MAX(date) AS date
        FROM macro
        GROUP BY key
    ) AS latest
        ON latest.key = m.key
       AND latest.date = m.date
    ORDER BY m.key ASC
    """
    return _get_loader().query_all(sql)


def count_latest_macro_rows() -> int:
    sql = """
    SELECT COUNT(*) AS total
    FROM (
        SELECT key, MAX(date) AS date
        FROM macro
        GROUP BY key
    ) AS latest
    """
    rows = _get_loader().query_all(sql)
    if not rows:
        return 0
    return int(rows[0].get("total") or 0)


def delete_macro_before(cutoff: date) -> int:
    sql = "DELETE FROM macro WHERE date < :cutoff"
    return _get_loader().execute_many(sql, [{"cutoff": cutoff}])


def delete_news_before(cutoff: date) -> int:
    sql = "DELETE FROM news WHERE published_at::date < :cutoff"
    return _get_loader().execute_many(sql, [{"cutoff": cutoff}])


def delete_events_before(cutoff: date) -> int:
    sql = "DELETE FROM events WHERE date < :cutoff"
    return _get_loader().execute_many(sql, [{"cutoff": cutoff}])


def delete_buyback_before(cutoff: date) -> int:
    sql = "DELETE FROM buyback WHERE date < :cutoff"
    return _get_loader().execute_many(sql, [{"cutoff": cutoff}])


def delete_insider_trade_before(cutoff: date) -> int:
    sql = "DELETE FROM insider_trade WHERE date < :cutoff"
    return _get_loader().execute_many(sql, [{"cutoff": cutoff}])


def delete_index_constituents_before(cutoff: date) -> int:
    sql = "DELETE FROM index_constituents WHERE date < :cutoff"
    return _get_loader().execute_many(sql, [{"cutoff": cutoff}])


def upsert_fund_holdings(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO fund_holdings (fund_code, symbol, report_date, shares, market_value, weight)
    VALUES (:fund_code, :symbol, :report_date, :shares, :market_value, :weight)
    ON CONFLICT (fund_code, symbol, report_date)
    DO UPDATE SET shares = EXCLUDED.shares, market_value = EXCLUDED.market_value, weight = EXCLUDED.weight
    """
    payload = _validate_rows(rows, ["fund_code", "symbol", "report_date"], "fund_holdings")
    return _get_loader().execute_many(sql, payload)


def list_stock_rows(*, limit: int | None = None) -> list[dict]:
    sql = "SELECT symbol, name, market, sector FROM stocks ORDER BY symbol ASC"
    if limit is not None and limit > 0:
        sql += " LIMIT :limit"
        return _get_loader().query_all(sql, {"limit": limit})
    return _get_loader().query_all(sql)


def get_latest_financial_periods(symbols: Iterable[str] | None = None) -> dict[str, str]:
    base_sql = "SELECT symbol, MAX(period) AS period FROM financials"
    params: dict = {}
    if symbols:
        normalized = [str(symbol) for symbol in symbols if str(symbol).strip()]
        if normalized:
            statement = text(f"{base_sql} WHERE symbol IN :symbols GROUP BY symbol").bindparams(
                bindparam("symbols", expanding=True)
            )
            rows = _get_loader().query_all_text(statement, {"symbols": normalized})
            return {
                str(row["symbol"]): str(row["period"])
                for row in rows
                if row.get("symbol") and row.get("period")
            }
    rows = _get_loader().query_all(f"{base_sql} GROUP BY symbol", params)
    return {
        str(row["symbol"]): str(row["period"])
        for row in rows
        if row.get("symbol") and row.get("period")
    }
