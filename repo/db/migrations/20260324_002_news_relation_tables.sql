BEGIN;

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

CREATE INDEX IF NOT EXISTS idx_news_related_symbols_symbol
ON news_related_symbols(symbol);

CREATE INDEX IF NOT EXISTS idx_news_related_sectors_sector
ON news_related_sectors(sector);

INSERT INTO news_related_symbols (news_id, symbol)
SELECT n.id, BTRIM(value) AS symbol
FROM news AS n
CROSS JOIN LATERAL regexp_split_to_table(COALESCE(n.related_symbols, ''), '\s*,\s*') AS value
WHERE NULLIF(BTRIM(value), '') IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO news_related_sectors (news_id, sector)
SELECT n.id, BTRIM(value) AS sector
FROM news AS n
CROSS JOIN LATERAL regexp_split_to_table(COALESCE(n.related_sectors, ''), '\s*,\s*') AS value
WHERE NULLIF(BTRIM(value), '') IS NOT NULL
ON CONFLICT DO NOTHING;

COMMIT;
