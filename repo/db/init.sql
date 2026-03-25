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
    time_bucket VARCHAR(32),
    related_symbols TEXT,
    related_sectors TEXT
);

CREATE TABLE IF NOT EXISTS news_related_symbols (
    news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    PRIMARY KEY (news_id, symbol)
);

CREATE TABLE IF NOT EXISTS news_related_sectors (
    news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    sector VARCHAR(64) NOT NULL,
    PRIMARY KEY (news_id, sector)
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

CREATE TABLE IF NOT EXISTS auth_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    password_salt VARCHAR(128) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_verification_codes (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    purpose VARCHAR(32) NOT NULL,
    code_hash VARCHAR(128) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_watch_targets (
    user_id INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS user_bought_targets (
    user_id INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    buy_price DOUBLE PRECISION NOT NULL,
    lots DOUBLE PRECISION NOT NULL,
    buy_date DATE NOT NULL,
    fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    note VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS user_alert_rules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(128) NOT NULL,
    rule_type VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    price_operator VARCHAR(8),
    threshold DOUBLE PRECISION,
    event_type VARCHAR(64),
    research_kind VARCHAR(32),
    lookback_days INTEGER NOT NULL DEFAULT 7,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    note VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_stock_pools (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(128) NOT NULL,
    market VARCHAR(16) NOT NULL DEFAULT 'A',
    symbols_json TEXT NOT NULL DEFAULT '[]',
    note VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_stock_pool_items (
    pool_id INTEGER NOT NULL REFERENCES user_stock_pools(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pool_id, symbol)
);

CREATE TABLE IF NOT EXISTS user_saved_stock_filters (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(128) NOT NULL,
    market VARCHAR(16) NOT NULL DEFAULT 'A',
    keyword VARCHAR(128) NOT NULL DEFAULT '',
    sector VARCHAR(128) NOT NULL DEFAULT '',
    sort VARCHAR(8) NOT NULL DEFAULT 'asc',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
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
);

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
);

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

CREATE TABLE IF NOT EXISTS bond_market_quotes (
    id SERIAL PRIMARY KEY,
    quote_org VARCHAR(128),
    bond_name VARCHAR(128),
    buy_net_price DOUBLE PRECISION,
    sell_net_price DOUBLE PRECISION,
    buy_yield DOUBLE PRECISION,
    sell_yield DOUBLE PRECISION,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS bond_market_trades (
    id SERIAL PRIMARY KEY,
    bond_name VARCHAR(128),
    deal_net_price DOUBLE PRECISION,
    latest_yield DOUBLE PRECISION,
    change DOUBLE PRECISION,
    weighted_yield DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS fx_spot_quotes (
    id SERIAL PRIMARY KEY,
    currency_pair VARCHAR(32),
    bid DOUBLE PRECISION,
    ask DOUBLE PRECISION,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS fx_swap_quotes (
    id SERIAL PRIMARY KEY,
    currency_pair VARCHAR(32),
    one_week DOUBLE PRECISION,
    one_month DOUBLE PRECISION,
    three_month DOUBLE PRECISION,
    six_month DOUBLE PRECISION,
    nine_month DOUBLE PRECISION,
    one_year DOUBLE PRECISION,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS fx_pair_quotes (
    id SERIAL PRIMARY KEY,
    currency_pair VARCHAR(32),
    bid DOUBLE PRECISION,
    ask DOUBLE PRECISION,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS stock_institute_holds (
    id SERIAL PRIMARY KEY,
    quarter VARCHAR(16),
    symbol VARCHAR(32),
    stock_name VARCHAR(128),
    institute_count DOUBLE PRECISION,
    institute_count_change DOUBLE PRECISION,
    holding_ratio DOUBLE PRECISION,
    holding_ratio_change DOUBLE PRECISION,
    float_holding_ratio DOUBLE PRECISION,
    float_holding_ratio_change DOUBLE PRECISION,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS stock_institute_hold_details (
    id SERIAL PRIMARY KEY,
    quarter VARCHAR(16),
    stock_symbol VARCHAR(32),
    institute_type VARCHAR(64),
    institute_code VARCHAR(64),
    institute_name VARCHAR(128),
    institute_full_name VARCHAR(255),
    shares DOUBLE PRECISION,
    latest_shares DOUBLE PRECISION,
    holding_ratio DOUBLE PRECISION,
    latest_holding_ratio DOUBLE PRECISION,
    float_holding_ratio DOUBLE PRECISION,
    latest_float_holding_ratio DOUBLE PRECISION,
    holding_ratio_change DOUBLE PRECISION,
    float_holding_ratio_change DOUBLE PRECISION,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS stock_institute_recommendations (
    id SERIAL PRIMARY KEY,
    category VARCHAR(64),
    symbol VARCHAR(32),
    stock_name VARCHAR(128),
    rating_date DATE,
    rating VARCHAR(64),
    metric_name VARCHAR(64),
    metric_value DOUBLE PRECISION,
    extra_text VARCHAR(255),
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS stock_institute_recommendation_details (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32),
    rating_date DATE,
    institution VARCHAR(128),
    rating VARCHAR(64),
    previous_rating VARCHAR(64),
    target_price DOUBLE PRECISION,
    title VARCHAR(255),
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS stock_report_disclosures (
    id SERIAL PRIMARY KEY,
    market VARCHAR(32),
    period VARCHAR(32),
    symbol VARCHAR(32),
    stock_name VARCHAR(128),
    first_booking DATE,
    first_change DATE,
    second_change DATE,
    third_change DATE,
    actual_disclosure DATE,
    as_of TIMESTAMP,
    source VARCHAR(64),
    raw_json TEXT
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
CREATE INDEX IF NOT EXISTS idx_news_related_symbols_symbol ON news_related_symbols(symbol);
CREATE INDEX IF NOT EXISTS idx_news_related_sectors_sector ON news_related_sectors(sector);
CREATE INDEX IF NOT EXISTS idx_events_symbol ON events(symbol);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth_users(email);
CREATE INDEX IF NOT EXISTS idx_email_verification_codes_email ON email_verification_codes(email);
CREATE INDEX IF NOT EXISTS idx_email_verification_codes_purpose ON email_verification_codes(purpose);
CREATE INDEX IF NOT EXISTS idx_email_verification_codes_expires_at ON email_verification_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_watch_targets_user ON user_watch_targets(user_id);
CREATE INDEX IF NOT EXISTS idx_user_bought_targets_user ON user_bought_targets(user_id);
CREATE INDEX IF NOT EXISTS idx_user_alert_rules_user ON user_alert_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_user_alert_rules_symbol ON user_alert_rules(symbol);
CREATE INDEX IF NOT EXISTS idx_user_alert_rules_type ON user_alert_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_user_stock_pools_user ON user_stock_pools(user_id);
CREATE INDEX IF NOT EXISTS idx_user_stock_pool_items_symbol ON user_stock_pool_items(symbol);
CREATE INDEX IF NOT EXISTS idx_user_stock_pool_items_pool_position ON user_stock_pool_items(pool_id, position);
CREATE INDEX IF NOT EXISTS idx_user_saved_stock_filters_user ON user_saved_stock_filters(user_id);
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
CREATE INDEX IF NOT EXISTS idx_bond_market_quotes_bond_name ON bond_market_quotes(bond_name);
CREATE INDEX IF NOT EXISTS idx_bond_market_quotes_quote_org ON bond_market_quotes(quote_org);
CREATE INDEX IF NOT EXISTS idx_bond_market_quotes_as_of ON bond_market_quotes(as_of);
CREATE INDEX IF NOT EXISTS idx_bond_market_trades_bond_name ON bond_market_trades(bond_name);
CREATE INDEX IF NOT EXISTS idx_bond_market_trades_as_of ON bond_market_trades(as_of);
CREATE INDEX IF NOT EXISTS idx_fx_spot_quotes_pair ON fx_spot_quotes(currency_pair);
CREATE INDEX IF NOT EXISTS idx_fx_swap_quotes_pair ON fx_swap_quotes(currency_pair);
CREATE INDEX IF NOT EXISTS idx_fx_pair_quotes_pair ON fx_pair_quotes(currency_pair);
CREATE INDEX IF NOT EXISTS idx_stock_institute_holds_quarter ON stock_institute_holds(quarter);
CREATE INDEX IF NOT EXISTS idx_stock_institute_holds_symbol ON stock_institute_holds(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_institute_hold_details_quarter ON stock_institute_hold_details(quarter);
CREATE INDEX IF NOT EXISTS idx_stock_institute_hold_details_symbol ON stock_institute_hold_details(stock_symbol);
CREATE INDEX IF NOT EXISTS idx_stock_institute_recommendations_category ON stock_institute_recommendations(category);
CREATE INDEX IF NOT EXISTS idx_stock_institute_recommendations_symbol ON stock_institute_recommendations(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_institute_recommendation_details_symbol ON stock_institute_recommendation_details(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_report_disclosures_market_period ON stock_report_disclosures(market, period);
CREATE INDEX IF NOT EXISTS idx_stock_report_disclosures_symbol ON stock_report_disclosures(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_live_snapshots_as_of ON stock_live_snapshots(as_of);
CREATE INDEX IF NOT EXISTS idx_stock_research_items_symbol ON stock_research_items(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_research_items_type ON stock_research_items(item_type);
CREATE INDEX IF NOT EXISTS idx_stock_research_items_published_at ON stock_research_items(published_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_research_items_identity
ON stock_research_items(symbol, item_type, title, published_at, link);
CREATE INDEX IF NOT EXISTS idx_stock_intraday_kline_symbol_period ON stock_intraday_kline(symbol, period);
CREATE INDEX IF NOT EXISTS idx_stock_intraday_kline_timestamp ON stock_intraday_kline(timestamp);
