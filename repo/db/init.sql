-- 初始化表结构与索引（PostgreSQL）

CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(128),
    market VARCHAR(16),
    sector VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS indices (
    symbol VARCHAR(32) NOT NULL,
    date DATE NOT NULL,
    close DOUBLE PRECISION,
    change DOUBLE PRECISION,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS daily_prices (
    symbol VARCHAR(32) NOT NULL,
    date DATE NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS financials (
    symbol VARCHAR(32) NOT NULL,
    period VARCHAR(32) NOT NULL,
    revenue DOUBLE PRECISION,
    net_income DOUBLE PRECISION,
    cash_flow DOUBLE PRECISION,
    roe DOUBLE PRECISION,
    debt_ratio DOUBLE PRECISION,
    PRIMARY KEY (symbol, period)
);

CREATE TABLE IF NOT EXISTS fundamental_score (
    symbol VARCHAR(32) PRIMARY KEY,
    score DOUBLE PRECISION,
    summary TEXT,
    updated_at TIMESTAMP
);

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
    time_bucket VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32),
    type VARCHAR(64),
    title TEXT,
    date DATE,
    link TEXT,
    source VARCHAR(128)
);

CREATE TABLE IF NOT EXISTS user_portfolio (
    user_id INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    avg_cost DOUBLE PRECISION,
    shares DOUBLE PRECISION,
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS macro (
    key VARCHAR(64) NOT NULL,
    date DATE NOT NULL,
    value DOUBLE PRECISION,
    score DOUBLE PRECISION,
    PRIMARY KEY (key, date)
);

CREATE TABLE IF NOT EXISTS buyback (
    symbol VARCHAR(32) NOT NULL,
    date DATE NOT NULL,
    amount DOUBLE PRECISION,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS insider_trade (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32),
    date DATE,
    type VARCHAR(32),
    shares DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS index_constituents (
    index_symbol VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    date DATE NOT NULL,
    weight DOUBLE PRECISION,
    PRIMARY KEY (index_symbol, symbol, date)
);

CREATE TABLE IF NOT EXISTS sector_exposure_daily (
    date DATE NOT NULL,
    market VARCHAR(16) NOT NULL,
    basis VARCHAR(32) NOT NULL,
    sector VARCHAR(64) NOT NULL,
    value DOUBLE PRECISION,
    weight DOUBLE PRECISION,
    symbol_count INTEGER,
    PRIMARY KEY (date, market, basis, sector)
);

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
);

CREATE TABLE IF NOT EXISTS stock_valuation_snapshots (
    symbol VARCHAR(32) NOT NULL,
    date DATE NOT NULL,
    market_cap DOUBLE PRECISION,
    float_market_cap DOUBLE PRECISION,
    source VARCHAR(64),
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS fund_holdings (
    fund_code VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    report_date DATE NOT NULL,
    shares DOUBLE PRECISION,
    market_value DOUBLE PRECISION,
    weight DOUBLE PRECISION,
    PRIMARY KEY (fund_code, symbol, report_date)
);

CREATE TABLE IF NOT EXISTS futures_prices (
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
);

CREATE TABLE IF NOT EXISTS futures_weekly_prices (
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
);

CREATE INDEX IF NOT EXISTS idx_indices_date ON indices(date);
CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(date);
CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol ON daily_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol_date ON daily_prices(symbol, date);
CREATE INDEX IF NOT EXISTS idx_financials_symbol ON financials(symbol);
CREATE INDEX IF NOT EXISTS idx_news_symbol ON news(symbol);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at);
CREATE INDEX IF NOT EXISTS idx_news_source_site ON news(source_site);
CREATE INDEX IF NOT EXISTS idx_news_source_category ON news(source_category);
CREATE INDEX IF NOT EXISTS idx_news_topic_category ON news(topic_category);
CREATE INDEX IF NOT EXISTS idx_news_time_bucket ON news(time_bucket);
CREATE INDEX IF NOT EXISTS idx_events_symbol ON events(symbol);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_macro_key ON macro(key);
CREATE INDEX IF NOT EXISTS idx_macro_date ON macro(date);
CREATE INDEX IF NOT EXISTS idx_buyback_symbol_date ON buyback(symbol, date);
CREATE INDEX IF NOT EXISTS idx_insider_trade_symbol ON insider_trade(symbol);
CREATE INDEX IF NOT EXISTS idx_insider_trade_date ON insider_trade(date);
CREATE INDEX IF NOT EXISTS idx_index_constituents_index ON index_constituents(index_symbol);
CREATE INDEX IF NOT EXISTS idx_index_constituents_symbol ON index_constituents(symbol);
CREATE INDEX IF NOT EXISTS idx_fund_holdings_fund_code ON fund_holdings(fund_code);
CREATE INDEX IF NOT EXISTS idx_fund_holdings_symbol ON fund_holdings(symbol);
CREATE INDEX IF NOT EXISTS idx_fund_holdings_report_date ON fund_holdings(report_date);
CREATE INDEX IF NOT EXISTS idx_futures_prices_date ON futures_prices(date);
CREATE INDEX IF NOT EXISTS idx_futures_prices_symbol ON futures_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_futures_weekly_prices_date ON futures_weekly_prices(date);
CREATE INDEX IF NOT EXISTS idx_futures_weekly_prices_symbol ON futures_weekly_prices(symbol);
