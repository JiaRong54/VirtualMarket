CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    appid INTEGER NOT NULL CHECK (appid > 0),
    market_hash_name TEXT NOT NULL CHECK (length(trim(market_hash_name)) > 0),
    UNIQUE(appid, market_hash_name)
);
CREATE TABLE IF NOT EXISTS price_observations (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id),
    observed_at TEXT NOT NULL,
    lowest_price_minor INTEGER NOT NULL CHECK (lowest_price_minor >= 0),
    currency TEXT NOT NULL CHECK (currency = 'USD'),
    listing_count INTEGER CHECK (listing_count >= 0),
    source TEXT NOT NULL,
    is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1)),
    UNIQUE(item_id, observed_at, source, currency, is_demo)
);
-- Optional metrics extend, rather than replace, the proposal's core record.
CREATE TABLE IF NOT EXISTS observation_metrics (
    observation_id INTEGER PRIMARY KEY REFERENCES price_observations(id),
    volume_24h INTEGER NOT NULL CHECK (volume_24h >= 0)
);
CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY);
CREATE INDEX IF NOT EXISTS idx_observation_history
    ON price_observations(item_id, source, currency, is_demo, observed_at);
