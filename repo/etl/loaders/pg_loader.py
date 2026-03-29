from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Iterable

from sqlalchemy import bindparam, text
from datetime import date

from etl.config.loader import load_config
from etl.utils.logging import get_logger
from etl.utils.db_pool import get_engine

LOGGER = get_logger(__name__)
_FUTURES_COLUMNS_READY = False
_FUTURES_WEEKLY_COLUMNS_READY = False
_SECTOR_EXPOSURE_TABLES_READY = False
_NEWS_COLUMNS_READY = False
_STOCK_DETAIL_TABLES_READY = False
_LOADER_LOCK = Lock()
_LOADER = None
_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yml"


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


def _clip_text(value: object, max_length: int, *, default: str = "") -> str:
    text = str(value or "").strip()
    text = " ".join(text.split())
    if not text:
        return default
    if len(text) <= max_length:
        return text
    return text[:max_length].strip()


def _sanitize_stock_rows(rows: Iterable[dict]) -> list[dict]:
    output: list[dict] = []
    for row in rows:
        symbol = _clip_text(row.get("symbol"), 32)
        if not symbol:
            continue
        name = _clip_text(row.get("name"), 128, default=symbol)
        market = _clip_text(row.get("market"), 16)
        sector = _clip_text(row.get("sector"), 64, default="Unknown")
        output.append(
            {
                **row,
                "symbol": symbol,
                "name": name,
                "market": market,
                "sector": sector,
            }
        )
    return output


def _normalize_news_relation_values(values: object, *, max_length: int = 64) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = values.split(",")
    elif isinstance(values, Iterable):
        raw_values = list(values)
    else:
        raw_values = [values]
    seen: set[str] = set()
    output: list[str] = []
    for raw in raw_values:
        text = _clip_text(raw, max_length)
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _join_news_relation_values(values: object, *, max_length: int = 64) -> str | None:
    normalized = _normalize_news_relation_values(values, max_length=max_length)
    return ",".join(normalized) if normalized else None


def _replace_news_relation_rows(conn, table_name: str, column_name: str, news_id: int, values: object) -> None:
    normalized = _normalize_news_relation_values(values)
    conn.execute(
        text(f"DELETE FROM {table_name} WHERE news_id = :news_id"),
        {"news_id": news_id},
    )
    if not normalized:
        return
    conn.execute(
        text(
            f"""
            INSERT INTO {table_name} (news_id, {column_name})
            VALUES (:news_id, :value)
            ON CONFLICT (news_id, {column_name}) DO NOTHING
            """
        ),
        [{"news_id": news_id, "value": value} for value in normalized],
    )


def _sync_news_relation_rows(conn, news_id: int, *, related_symbols: object, related_sectors: object) -> None:
    _replace_news_relation_rows(conn, "news_related_symbols", "symbol", news_id, related_symbols)
    _replace_news_relation_rows(conn, "news_related_sectors", "sector", news_id, related_sectors)


class PgLoader:
    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        execution_options: dict | None = None,
    ):
        """
        初始化 PgLoader。
        
        优化：使用共享的数据库引擎，避免重复创建连接池。
        
        Args:
            database_url: 数据库连接字符串
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
            execution_options: 执行选项
        """
        # 使用共享引擎，避免重复创建连接池
        self.engine = get_engine(
            database_url,
            pool_size=pool_size or 5,
            max_overflow=max_overflow or 5,
        )
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

    def execute(self, sql: str, params: dict | None = None) -> None:
        try:
            with self.engine.begin() as conn:
                conn.execute(text(sql), params or {})
        except Exception as exc:
            LOGGER.exception("PgLoader execute failed: %s", exc, exc_info=exc)
            raise


def _get_loader() -> PgLoader:
    config_path = Path(__file__).resolve().parents[1] / "config" / "settings.yml"
    config = load_config(config_path)
    if not config.postgres_url:
        raise ValueError("postgres_url is not configured")
    return PgLoader(
        config.postgres_url,
        pool_size=getattr(config, "postgres_pool_size", None),
        max_overflow=getattr(config, "postgres_max_overflow", None),
    )


def _build_loader() -> PgLoader:
    config = load_config(_CONFIG_PATH)
    if not config.postgres_url:
        raise ValueError("postgres_url is not configured")
    return PgLoader(
        config.postgres_url,
        pool_size=getattr(config, "postgres_pool_size", None),
        max_overflow=getattr(config, "postgres_max_overflow", None),
    )


def _get_loader() -> PgLoader:
    global _LOADER
    if _LOADER is not None:
        return _LOADER
    with _LOADER_LOCK:
        if _LOADER is None:
            _LOADER = _build_loader()
        return _LOADER


def _reset_loader_cache(*, dispose_engine: bool = True) -> None:
    global _LOADER
    with _LOADER_LOCK:
        if _LOADER is not None and dispose_engine:
            _LOADER.engine.dispose()
        _LOADER = None


def upsert_stocks(rows: Iterable[dict]) -> int:
    sql = """
    INSERT INTO stocks (symbol, name, market, sector)
    VALUES (:symbol, :name, :market, :sector)
    ON CONFLICT (symbol)
    DO UPDATE SET name = EXCLUDED.name, market = EXCLUDED.market, sector = EXCLUDED.sector
    """
    payload = _sanitize_stock_rows(_validate_rows(rows, ["symbol"], "stocks"))
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
    _ensure_news_columns()
    payload = _validate_rows(rows, ["symbol", "title", "published_at"], "news")
    if not payload:
        return 0
    insert_sql = text(
        """
        INSERT INTO news (
            symbol, title, sentiment, published_at, link, source,
            source_site, source_category, topic_category, time_bucket,
            related_symbols, related_sectors,
            event_type, event_tags, themes, impact_direction,
            nlp_confidence, nlp_version, keywords
        )
        VALUES (
            :symbol, :title, :sentiment, :published_at, :link, :source,
            :source_site, :source_category, :topic_category, :time_bucket,
            :related_symbols, :related_sectors,
            :event_type, :event_tags, :themes, :impact_direction,
            :nlp_confidence, :nlp_version, :keywords
        )
        RETURNING id
        """
    )
    loader = _get_loader()
    total = 0
    try:
        with loader.engine.begin() as conn:
            for row in payload:
                related_symbols = _normalize_news_relation_values(row.get("related_symbols"))
                related_sectors = _normalize_news_relation_values(row.get("related_sectors"))
                event_tags = _normalize_news_relation_values(row.get("event_tags"))
                themes = _normalize_news_relation_values(row.get("themes"))
                keywords = _normalize_news_relation_values(row.get("keywords"), max_length=128)
                params = {
                    **row,
                    "related_symbols": ",".join(related_symbols) if related_symbols else None,
                    "related_sectors": ",".join(related_sectors) if related_sectors else None,
                    "event_tags": ",".join(event_tags) if event_tags else None,
                    "themes": ",".join(themes) if themes else None,
                    "keywords": ",".join(keywords) if keywords else None,
                }
                news_id = conn.execute(insert_sql, params).scalar()
                if news_id is not None:
                    _sync_news_relation_rows(
                        conn,
                        int(news_id),
                        related_symbols=related_symbols,
                        related_sectors=related_sectors,
                    )
                total += 1
    except Exception as exc:
        LOGGER.exception("PgLoader batch write failed: %s", exc, exc_info=exc)
        raise
    return total


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
    _ensure_sector_exposure_tables()
    sql = """
    INSERT INTO sector_exposure_daily (date, market, basis, sector, value, weight, symbol_count)
    VALUES (:date, :market, :basis, :sector, :value, :weight, :symbol_count)
    ON CONFLICT (date, market, basis, sector)
    DO UPDATE SET
        value = EXCLUDED.value,
        weight = EXCLUDED.weight,
        symbol_count = EXCLUDED.symbol_count
    """
    payload = _validate_rows(rows, ["date", "market", "basis", "sector"], "sector_exposure")
    return _get_loader().execute_many(sql, payload)


def upsert_sector_exposure_summary(rows: Iterable[dict]) -> int:
    _ensure_sector_exposure_tables()
    sql = """
    INSERT INTO sector_exposure_summary (
        date, market, basis, total_value, total_symbol_count, covered_symbol_count,
        classified_symbol_count, unknown_symbol_count, unknown_value, coverage
    )
    VALUES (
        :date, :market, :basis, :total_value, :total_symbol_count, :covered_symbol_count,
        :classified_symbol_count, :unknown_symbol_count, :unknown_value, :coverage
    )
    ON CONFLICT (date, market, basis)
    DO UPDATE SET
        total_value = EXCLUDED.total_value,
        total_symbol_count = EXCLUDED.total_symbol_count,
        covered_symbol_count = EXCLUDED.covered_symbol_count,
        classified_symbol_count = EXCLUDED.classified_symbol_count,
        unknown_symbol_count = EXCLUDED.unknown_symbol_count,
        unknown_value = EXCLUDED.unknown_value,
        coverage = EXCLUDED.coverage
    """
    payload = _validate_rows(rows, ["date", "market", "basis"], "sector_exposure_summary")
    return _get_loader().execute_many(sql, payload)


def upsert_stock_valuation_snapshots(rows: Iterable[dict]) -> int:
    _ensure_sector_exposure_tables()
    sql = """
    INSERT INTO stock_valuation_snapshots (symbol, date, market_cap, float_market_cap, source)
    VALUES (:symbol, :date, :market_cap, :float_market_cap, :source)
    ON CONFLICT (symbol, date)
    DO UPDATE SET
        market_cap = EXCLUDED.market_cap,
        float_market_cap = EXCLUDED.float_market_cap,
        source = EXCLUDED.source
    """
    payload = _validate_rows(rows, ["symbol", "date"], "stock_valuation_snapshots")
    return _get_loader().execute_many(sql, payload)


def upsert_stock_live_snapshots(rows: Iterable[dict]) -> int:
    _ensure_stock_detail_tables()
    sql = """
    INSERT INTO stock_live_snapshots (
        symbol, as_of, current, change, percent, open, high, low, last_close,
        volume, amount, turnover_rate, amplitude, quote_timestamp,
        pe_ttm, pb, ps_ttm, pcf, market_cap, float_market_cap, dividend_yield,
        volume_ratio, lot_size, pankou_diff, pankou_ratio, pankou_timestamp,
        pankou_bids_json, pankou_asks_json, source
    )
    VALUES (
        :symbol, :as_of, :current, :change, :percent, :open, :high, :low, :last_close,
        :volume, :amount, :turnover_rate, :amplitude, :quote_timestamp,
        :pe_ttm, :pb, :ps_ttm, :pcf, :market_cap, :float_market_cap, :dividend_yield,
        :volume_ratio, :lot_size, :pankou_diff, :pankou_ratio, :pankou_timestamp,
        :pankou_bids_json, :pankou_asks_json, :source
    )
    ON CONFLICT (symbol)
    DO UPDATE SET
        as_of = EXCLUDED.as_of,
        current = EXCLUDED.current,
        change = EXCLUDED.change,
        percent = EXCLUDED.percent,
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        last_close = EXCLUDED.last_close,
        volume = EXCLUDED.volume,
        amount = EXCLUDED.amount,
        turnover_rate = EXCLUDED.turnover_rate,
        amplitude = EXCLUDED.amplitude,
        quote_timestamp = EXCLUDED.quote_timestamp,
        pe_ttm = EXCLUDED.pe_ttm,
        pb = EXCLUDED.pb,
        ps_ttm = EXCLUDED.ps_ttm,
        pcf = EXCLUDED.pcf,
        market_cap = EXCLUDED.market_cap,
        float_market_cap = EXCLUDED.float_market_cap,
        dividend_yield = EXCLUDED.dividend_yield,
        volume_ratio = EXCLUDED.volume_ratio,
        lot_size = EXCLUDED.lot_size,
        pankou_diff = EXCLUDED.pankou_diff,
        pankou_ratio = EXCLUDED.pankou_ratio,
        pankou_timestamp = EXCLUDED.pankou_timestamp,
        pankou_bids_json = EXCLUDED.pankou_bids_json,
        pankou_asks_json = EXCLUDED.pankou_asks_json,
        source = EXCLUDED.source
    """
    payload = _validate_rows(rows, ["symbol"], "stock_live_snapshots")
    return _get_loader().execute_many(sql, payload)


def upsert_stock_research_items(rows: Iterable[dict]) -> int:
    _ensure_stock_detail_tables()
    sql = """
    INSERT INTO stock_research_items (
        symbol, item_type, title, published_at, link, summary, institution, rating, source
    )
    VALUES (
        :symbol, :item_type, :title, :published_at, :link, :summary, :institution, :rating, :source
    )
    ON CONFLICT (symbol, item_type, title, published_at, link)
    DO UPDATE SET
        summary = EXCLUDED.summary,
        institution = EXCLUDED.institution,
        rating = EXCLUDED.rating,
        source = EXCLUDED.source
    """
    payload = _validate_rows(rows, ["symbol", "item_type", "title"], "stock_research_items")
    return _get_loader().execute_many(sql, payload)


def upsert_stock_intraday_kline(rows: Iterable[dict]) -> int:
    _ensure_stock_detail_tables()
    sql = """
    INSERT INTO stock_intraday_kline (symbol, period, timestamp, open, high, low, close, volume)
    VALUES (:symbol, :period, :timestamp, :open, :high, :low, :close, :volume)
    ON CONFLICT (symbol, period, timestamp)
    DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume
    """
    payload = _validate_rows(rows, ["symbol", "period", "timestamp"], "stock_intraday_kline")
    return _get_loader().execute_many(sql, payload)


def list_stock_live_snapshot_meta() -> list[dict]:
    _ensure_stock_detail_tables()
    sql = """
    SELECT symbol, as_of
    FROM stock_live_snapshots
    """
    return _get_loader().query_all(sql)


def list_stock_intraday_meta() -> list[dict]:
    _ensure_stock_detail_tables()
    sql = """
    SELECT symbol, MAX(timestamp) AS latest_timestamp, COUNT(DISTINCT period) AS period_count
    FROM stock_intraday_kline
    GROUP BY symbol
    """
    return _get_loader().query_all(sql)


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
    _ensure_futures_price_columns("futures_prices", weekly=False)
    sql = """
    INSERT INTO futures_prices (
        symbol, name, date, contract_month, open, high, low, close,
        settlement, open_interest, turnover, volume, source
    )
    VALUES (
        :symbol, :name, :date, :contract_month, :open, :high, :low, :close,
        :settlement, :open_interest, :turnover, :volume, :source
    )
    ON CONFLICT (symbol, date)
    DO UPDATE SET
        name = EXCLUDED.name,
        contract_month = EXCLUDED.contract_month,
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        settlement = EXCLUDED.settlement,
        open_interest = EXCLUDED.open_interest,
        turnover = EXCLUDED.turnover,
        volume = EXCLUDED.volume,
        source = EXCLUDED.source
    """
    payload = _validate_rows(rows, ["symbol", "date"], "futures_prices")
    return _get_loader().execute_many(sql, payload)


def upsert_futures_weekly_prices(rows: Iterable[dict]) -> int:
    _ensure_futures_price_columns("futures_weekly_prices", weekly=True)
    sql = """
    INSERT INTO futures_weekly_prices (
        symbol, name, date, contract_month, open, high, low, close,
        settlement, open_interest, turnover, volume, source
    )
    VALUES (
        :symbol, :name, :date, :contract_month, :open, :high, :low, :close,
        :settlement, :open_interest, :turnover, :volume, :source
    )
    ON CONFLICT (symbol, date)
    DO UPDATE SET
        name = EXCLUDED.name,
        contract_month = EXCLUDED.contract_month,
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        settlement = EXCLUDED.settlement,
        open_interest = EXCLUDED.open_interest,
        turnover = EXCLUDED.turnover,
        volume = EXCLUDED.volume,
        source = EXCLUDED.source
    """
    payload = _validate_rows(rows, ["symbol", "date"], "futures_weekly_prices")
    return _get_loader().execute_many(sql, payload)


def _ensure_futures_price_columns(table_name: str, *, weekly: bool) -> None:
    global _FUTURES_COLUMNS_READY, _FUTURES_WEEKLY_COLUMNS_READY
    if weekly and _FUTURES_WEEKLY_COLUMNS_READY:
        return
    if not weekly and _FUTURES_COLUMNS_READY:
        return
    loader = _get_loader()
    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            symbol VARCHAR(32) NOT NULL,
            name VARCHAR(128),
            date DATE NOT NULL,
            contract_month VARCHAR(16),
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            settlement DOUBLE PRECISION,
            open_interest DOUBLE PRECISION,
            turnover DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            source VARCHAR(64),
            PRIMARY KEY (symbol, date)
        )
        """,
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS contract_month VARCHAR(16)",
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS settlement DOUBLE PRECISION",
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS open_interest DOUBLE PRECISION",
        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS turnover DOUBLE PRECISION",
    ]
    for statement in statements:
        loader.execute(statement)
    if weekly:
        _FUTURES_WEEKLY_COLUMNS_READY = True
    else:
        _FUTURES_COLUMNS_READY = True


def _ensure_sector_exposure_tables() -> None:
    global _SECTOR_EXPOSURE_TABLES_READY
    if _SECTOR_EXPOSURE_TABLES_READY:
        return
    loader = _get_loader()
    statements = [
        """
        CREATE TABLE IF NOT EXISTS sector_exposure_daily (
            date DATE NOT NULL,
            market VARCHAR(16) NOT NULL,
            basis VARCHAR(32) NOT NULL,
            sector VARCHAR(64) NOT NULL,
            value DOUBLE PRECISION,
            weight DOUBLE PRECISION,
            symbol_count INTEGER,
            PRIMARY KEY (date, market, basis, sector)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sector_exposure_summary (
            date DATE NOT NULL,
            market VARCHAR(16) NOT NULL,
            basis VARCHAR(32) NOT NULL,
            total_value DOUBLE PRECISION,
            total_symbol_count INTEGER,
            covered_symbol_count INTEGER,
            classified_symbol_count INTEGER,
            unknown_symbol_count INTEGER,
            unknown_value DOUBLE PRECISION,
            coverage DOUBLE PRECISION,
            PRIMARY KEY (date, market, basis)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS stock_valuation_snapshots (
            symbol VARCHAR(32) NOT NULL,
            date DATE NOT NULL,
            market_cap DOUBLE PRECISION,
            float_market_cap DOUBLE PRECISION,
            source VARCHAR(64),
            PRIMARY KEY (symbol, date)
        )
        """,
    ]
    for statement in statements:
        loader.execute(statement)
    _SECTOR_EXPOSURE_TABLES_READY = True


def _ensure_news_columns() -> None:
    global _NEWS_COLUMNS_READY
    if _NEWS_COLUMNS_READY:
        return
    loader = _get_loader()
    statements = [
        """
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(32),
            title TEXT,
            sentiment VARCHAR(32),
            published_at TIMESTAMP,
            link TEXT,
            source VARCHAR(128),
            source_site VARCHAR(128),
            source_category VARCHAR(64),
            topic_category VARCHAR(64),
            time_bucket VARCHAR(32),
            related_symbols TEXT,
            related_sectors TEXT,
            event_type VARCHAR(64),
            event_tags TEXT,
            themes TEXT,
            impact_direction VARCHAR(32),
            nlp_confidence DOUBLE PRECISION,
            nlp_version VARCHAR(32),
            keywords TEXT
        )
        """,
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS source_site VARCHAR(128)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS source_category VARCHAR(64)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS topic_category VARCHAR(64)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS time_bucket VARCHAR(32)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS related_symbols TEXT",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS related_sectors TEXT",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS event_type VARCHAR(64)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS event_tags TEXT",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS themes TEXT",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS impact_direction VARCHAR(32)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS nlp_confidence DOUBLE PRECISION",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS nlp_version VARCHAR(32)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS keywords TEXT",
        """
        CREATE TABLE IF NOT EXISTS news_related_symbols (
            news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
            symbol VARCHAR(32) NOT NULL,
            PRIMARY KEY (news_id, symbol)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS news_related_sectors (
            news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
            sector VARCHAR(64) NOT NULL,
            PRIMARY KEY (news_id, sector)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_news_related_symbols_symbol ON news_related_symbols(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_news_related_sectors_sector ON news_related_sectors(sector)",
    ]
    for statement in statements:
        loader.execute(statement)
    _NEWS_COLUMNS_READY = True


def _ensure_stock_detail_tables() -> None:
    global _STOCK_DETAIL_TABLES_READY
    if _STOCK_DETAIL_TABLES_READY:
        return
    loader = _get_loader()
    statements = [
        """
        CREATE TABLE IF NOT EXISTS stock_live_snapshots (
            symbol VARCHAR(32) PRIMARY KEY,
            as_of TIMESTAMP,
            current DOUBLE PRECISION,
            change DOUBLE PRECISION,
            percent DOUBLE PRECISION,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            last_close DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            turnover_rate DOUBLE PRECISION,
            amplitude DOUBLE PRECISION,
            quote_timestamp TIMESTAMP,
            pe_ttm DOUBLE PRECISION,
            pb DOUBLE PRECISION,
            ps_ttm DOUBLE PRECISION,
            pcf DOUBLE PRECISION,
            market_cap DOUBLE PRECISION,
            float_market_cap DOUBLE PRECISION,
            dividend_yield DOUBLE PRECISION,
            volume_ratio DOUBLE PRECISION,
            lot_size DOUBLE PRECISION,
            pankou_diff DOUBLE PRECISION,
            pankou_ratio DOUBLE PRECISION,
            pankou_timestamp TIMESTAMP,
            pankou_bids_json TEXT,
            pankou_asks_json TEXT,
            source VARCHAR(64)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS stock_research_items (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(32),
            item_type VARCHAR(32),
            title TEXT,
            published_at TIMESTAMP,
            link TEXT,
            summary TEXT,
            institution VARCHAR(128),
            rating VARCHAR(128),
            source VARCHAR(128)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS stock_intraday_kline (
            symbol VARCHAR(32) NOT NULL,
            period VARCHAR(16) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            PRIMARY KEY (symbol, period, timestamp)
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_research_items_identity ON stock_research_items(symbol, item_type, title, published_at, link)",
    ]
    for statement in statements:
        loader.execute(statement)
    _STOCK_DETAIL_TABLES_READY = True


def list_news_rows(
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    _ensure_news_columns()
    sql = """
    SELECT id, symbol, title, sentiment, published_at, link, source,
           source_site, source_category, topic_category, time_bucket,
           related_symbols, related_sectors,
           event_type, event_tags, themes, impact_direction,
           nlp_confidence, nlp_version, keywords
    FROM news
    WHERE 1 = 1
    """
    params: dict[str, object] = {}
    if start is not None:
        sql += " AND published_at >= :start"
        params["start"] = start
    if end is not None:
        sql += " AND published_at <= :end"
        params["end"] = end
    sql += " ORDER BY published_at DESC, id DESC"
    if limit is not None and limit > 0:
        sql += " LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = max(0, offset)
    return _get_loader().query_all(sql, params)


def update_news_metadata(rows: Iterable[dict]) -> int:
    _ensure_news_columns()
    payload = _validate_rows(rows, ["id"], "news.metadata")
    if not payload:
        return 0
    update_sql = text(
        """
        UPDATE news
        SET source_site = :source_site,
            source_category = :source_category,
            topic_category = :topic_category,
            time_bucket = :time_bucket,
            related_symbols = :related_symbols,
            related_sectors = :related_sectors,
            event_type = :event_type,
            event_tags = :event_tags,
            themes = :themes,
            impact_direction = :impact_direction,
            nlp_confidence = :nlp_confidence,
            nlp_version = :nlp_version,
            keywords = :keywords
        WHERE id = :id
        """
    )
    loader = _get_loader()
    total = 0
    try:
        with loader.engine.begin() as conn:
            for row in payload:
                related_symbols = _normalize_news_relation_values(row.get("related_symbols"))
                related_sectors = _normalize_news_relation_values(row.get("related_sectors"))
                event_tags = _normalize_news_relation_values(row.get("event_tags"))
                themes = _normalize_news_relation_values(row.get("themes"))
                keywords = _normalize_news_relation_values(row.get("keywords"), max_length=128)
                conn.execute(
                    update_sql,
                    {
                        **row,
                        "related_symbols": ",".join(related_symbols) if related_symbols else None,
                        "related_sectors": ",".join(related_sectors) if related_sectors else None,
                        "event_tags": ",".join(event_tags) if event_tags else None,
                        "themes": ",".join(themes) if themes else None,
                        "keywords": ",".join(keywords) if keywords else None,
                    },
                )
                _sync_news_relation_rows(
                    conn,
                    int(row["id"]),
                    related_symbols=related_symbols,
                    related_sectors=related_sectors,
                )
                total += 1
    except Exception as exc:
        LOGGER.exception("PgLoader batch write failed: %s", exc, exc_info=exc)
        raise
    return total


def update_news_sentiment(rows: Iterable[dict]) -> int:
    _ensure_news_columns()
    sql = """
    UPDATE news
    SET sentiment = :sentiment
    WHERE id = :id
    """
    payload = _validate_rows(rows, ["id", "sentiment"], "news.sentiment")
    return _get_loader().execute_many(sql, payload)


def list_daily_price_rows(as_of: date) -> list[dict]:
    sql = """
    SELECT symbol, date, open, high, low, close, volume
    FROM daily_prices
    WHERE date = :as_of
    ORDER BY symbol ASC
    """
    return _get_loader().query_all(sql, {"as_of": as_of})


def list_latest_macro_rows(key_like: str | None = None) -> list[dict]:
    sql = """
    SELECT m.key, m.date, m.value, m.score
    FROM macro AS m
    INNER JOIN (
        SELECT key, MAX(date) AS date
        FROM macro
        WHERE (:key_like IS NULL OR key LIKE :key_like)
        GROUP BY key
    ) AS latest
        ON latest.key = m.key
       AND latest.date = m.date
    ORDER BY m.key ASC
    """
    return _get_loader().query_all(sql, {"key_like": key_like})


def count_latest_macro_rows(key_like: str | None = None) -> int:
    sql = """
    SELECT COUNT(*) AS total
    FROM (
        SELECT key, MAX(date) AS date
        FROM macro
        WHERE (:key_like IS NULL OR key LIKE :key_like)
        GROUP BY key
    ) AS latest
    """
    rows = _get_loader().query_all(sql, {"key_like": key_like})
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


def list_stock_valuation_rows(as_of: date) -> list[dict]:
    _ensure_sector_exposure_tables()
    sql = """
    SELECT symbol, date, market_cap, float_market_cap, source
    FROM stock_valuation_snapshots
    WHERE date = :as_of
    ORDER BY symbol ASC
    """
    return _get_loader().query_all(sql, {"as_of": as_of})


def get_latest_financial_periods(symbols: Iterable[str] | None = None) -> dict[str, str]:
    base_sql = """
    SELECT symbol, MAX(period) AS period
    FROM financials
    WHERE
        (
            COALESCE(revenue, 0) <> 0
            OR COALESCE(net_income, 0) <> 0
            OR COALESCE(cash_flow, 0) <> 0
            OR COALESCE(roe, 0) <> 0
            OR COALESCE(debt_ratio, 0) <> 0
        )
    """
    params: dict = {}
    if symbols:
        normalized = [str(symbol) for symbol in symbols if str(symbol).strip()]
        if normalized:
            statement = text(f"{base_sql} AND symbol IN :symbols GROUP BY symbol").bindparams(
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
