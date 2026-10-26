"""Transactional local storage for source-separated USD observations."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'market.db'
SCHEMA_PATH = ROOT / 'schema.sql'

@contextmanager
def connect_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize_db(db_path=DB_PATH):
    with connect_db(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding='utf-8-sig'))
        legacy = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prices_observe'").fetchone()
        migrated = conn.execute("SELECT 1 FROM schema_migrations WHERE name='legacy_prices_observe'").fetchone()
        if legacy and not migrated:
            rows = conn.execute('''SELECT i.appid, i.market_hash_name, p.observed_at,
                p.lowest_price_minor, p.currency, p.listing_count, p.source, p.is_demo
                FROM prices_observe p JOIN items i ON i.id=p.item_id''').fetchall()
            for row in rows:
                record = dict(row)
                record['is_demo'] = bool(record['is_demo'])
                _save_records(conn, [record])
            conn.execute("INSERT INTO schema_migrations(name) VALUES ('legacy_prices_observe')")

def normalize_time(value):
    if not isinstance(value, str):
        raise ValueError('Time must be an ISO 8601 string')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Time must include timezone')
    return dt.astimezone(timezone.utc).isoformat(timespec='microseconds')

def validate_record(record):
    required = {'appid', 'market_hash_name', 'source', 'observed_at', 'currency',
                'lowest_price_minor', 'listing_count', 'is_demo'}
    if not isinstance(record, dict) or not required <= record.keys():
        raise ValueError('Observation is missing required fields')
    if type(record['appid']) is not int or record['appid'] <= 0:
        raise ValueError('appid must be a positive integer')
    for field in ('market_hash_name', 'source'):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(field + ' must be a non-empty string')
    for field in ('lowest_price_minor', 'listing_count', 'volume_24h'):
        value = record.get(field)
        if value is None and field != 'lowest_price_minor':
            continue
        if type(value) is not int or not 0 <= value <= 9223372036854775807:
            raise ValueError(field + ' must be a nonnegative SQLite integer')
    if record['currency'] != 'USD':
        raise ValueError('Only verified USD observations are supported')
    if type(record['is_demo']) is not bool:
        raise ValueError('is_demo must be a boolean')
    normalize_time(record['observed_at'])

def _save_records(conn, records):
    inserted = duplicates = 0
    for record in records:
        validate_record(record)
        conn.execute('''INSERT INTO items(appid, market_hash_name) VALUES (?, ?)
            ON CONFLICT(appid, market_hash_name) DO NOTHING''',
            (record['appid'], record['market_hash_name']))
        item = conn.execute('SELECT id FROM items WHERE appid=? AND market_hash_name=?',
                            (record['appid'], record['market_hash_name'])).fetchone()
        key = (item['id'], normalize_time(record['observed_at']), record['source'],
               record['currency'], int(record['is_demo']))
        values = (record['lowest_price_minor'], record['listing_count'])
        existing = conn.execute('''SELECT id, lowest_price_minor, listing_count
            FROM price_observations WHERE item_id=? AND observed_at=? AND source=? AND currency=? AND is_demo=?''', key).fetchone()
        if existing:
            volume = conn.execute('SELECT volume_24h FROM observation_metrics WHERE observation_id=?', (existing['id'],)).fetchone()
            if tuple(existing)[1:] != values or (volume[0] if volume else None) != record.get('volume_24h'):
                raise ValueError('Conflicting duplicate observation; existing data was not overwritten')
            duplicates += 1
            continue
        cursor = conn.execute('''INSERT INTO price_observations
            (item_id, observed_at, source, currency, is_demo, lowest_price_minor, listing_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', key + values)
        if record.get('volume_24h') is not None:
            conn.execute('INSERT INTO observation_metrics(observation_id, volume_24h) VALUES (?, ?)',
                         (cursor.lastrowid, record['volume_24h']))
        inserted += 1
    return {'inserted': inserted, 'duplicates': duplicates}

def save_observations(records, db_path=DB_PATH):
    """Save the entire batch atomically; identical repeats are idempotent."""
    with connect_db(db_path) as conn:
        return _save_records(conn, records)

def get_items(db_path=DB_PATH):
    with connect_db(db_path) as conn:
        return [dict(row) for row in conn.execute(
            'SELECT id, appid, market_hash_name FROM items ORDER BY appid, market_hash_name')]

def get_price_history(item_id, source, is_demo, start=None, end=None, db_path=DB_PATH):
    if type(is_demo) is not bool:
        raise ValueError('is_demo must be a boolean')
    start = normalize_time(start) if start else None
    end = normalize_time(end) if end else None
    if start and end and start > end:
        raise ValueError('Start time must be before end time')
    sql = '''SELECT p.observed_at, p.lowest_price_minor, p.listing_count, p.currency,
        p.source, p.is_demo, m.volume_24h FROM price_observations p
        LEFT JOIN observation_metrics m ON m.observation_id=p.id
        WHERE p.item_id=? AND p.source=? AND p.is_demo=? AND p.currency='USD' '''
    params = [item_id, source, int(is_demo)]
    if start:
        sql += ' AND p.observed_at >= ?'
        params.append(start)
    if end:
        sql += ' AND p.observed_at <= ?'
        params.append(end)
    sql += ' ORDER BY p.observed_at'
    with connect_db(db_path) as conn:
        return [dict(row) for row in conn.execute(sql, params)]

initilize_db = initialize_db
save_observe = save_observations
