BEGIN;

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

COMMIT;
