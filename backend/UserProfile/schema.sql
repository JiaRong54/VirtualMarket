PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL DEFAULT 'User',
    icon TEXT, -- Reserved for a future managed avatar storage key; NULL uses the default icon.
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

-- One saved item per account and game. Prices are whole USD cents; NULL means
-- no price was available when added. Keep the original timestamp and price
-- when reading the list after login (do not recreate entries on login).
CREATE TABLE IF NOT EXISTS watchlist_items (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game TEXT NOT NULL CHECK (game IN ('cs2', 'dota2')),
    item_name TEXT NOT NULL CHECK (length(trim(item_name)) > 0),
    added_at TEXT NOT NULL CHECK (length(trim(added_at)) > 0), -- ISO 8601 UTC, matching the frontend
    added_price_minor INTEGER CHECK (
        added_price_minor IS NULL OR (
            typeof(added_price_minor) = 'integer' AND added_price_minor >= 0
        )
    ),
    PRIMARY KEY (user_id, game, item_name)
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS login_attempts (
    email TEXT PRIMARY KEY,
    failures INTEGER NOT NULL,
    window_start INTEGER NOT NULL
);
