"""Collect CS2 on EC2, persist locally on EBS, and publish website JSON.

No S3 or AWS SDK required. Optional cookie file enables authenticated history.
Run under the supplied systemd timer (one batch at a time).
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from steam_history import DownloadError, SteamClient, initialize, validate_history

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loader'))
from load_steam import make_snapshot, read_cloud, read_market, write_snapshot
from convert_history import parse_record, to_daily

GAMES = {730: 'cs2'}


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.isoformat()


def initialize_sync(conn):
    initialize(conn)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS sync_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cloud_market_items (
            appid INTEGER, market_hash_name TEXT, observed_at TEXT,
            requested_currency TEXT, response_json TEXT,
            PRIMARY KEY(appid, market_hash_name));
        CREATE TABLE IF NOT EXISTS steam_search_observations (
            appid INTEGER, market_hash_name TEXT, observed_at TEXT,
            requested_currency TEXT, response_json TEXT,
            PRIMARY KEY(appid, market_hash_name, observed_at));
        CREATE TABLE IF NOT EXISTS sync_history_attempts (
            appid INTEGER, market_hash_name TEXT, retry_at TEXT,
            PRIMARY KEY(appid, market_hash_name));
    ''')


def get_state(conn, key, default=''):
    row = conn.execute('SELECT value FROM sync_state WHERE key=?', (key,)).fetchone()
    return row[0] if row else default


def set_state(conn, key, value):
    conn.execute('INSERT INTO sync_state VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                 (key, str(value)))


def fetch_page(conn, client, appid, current):
    if appid not in GAMES:
        raise ValueError(f'App ID {appid} is not enabled for this run; enabled app IDs: {sorted(GAMES)}')
    prefix = str(appid)
    if get_state(conn, prefix + ':after') > stamp(current):
        return 0
    start = int(get_state(conn, prefix + ':start', '0'))
    data = client.get('search/render', dict(appid=appid, query='', start=start, count=100,
                      norender=1, sort_column='name', sort_dir='asc', currency=1, country='US', l='english'))
    rows, total = data.get('results'), data.get('total_count')
    if (not isinstance(rows, list) or type(total) is not int or total < 0
            or data.get('start', start) != start or (not rows and start < total)):
        raise DownloadError('Invalid search pagination')
    names = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('asset_description'), dict)
                or row['asset_description'].get('appid') != appid
                or not isinstance(row.get('hash_name'), str) or not row['hash_name'].strip()):
            raise DownloadError('Unexpected game or invalid search item')
        names.append(row['hash_name'])
    signature = hashlib.sha256(json.dumps(names).encode()).hexdigest()
    if rows and start and signature == get_state(conn, prefix + ':signature'):
        # Restart the pass after cooling down; a capped page must not block all
        # future refreshes of earlier items. Coverage is still not guaranteed.
        with conn:
            set_state(conn, prefix + ':start', 0)
            set_state(conn, prefix + ':after', stamp(current + timedelta(hours=1)))
        raise DownloadError('Search repeated a page; scan will restart after cooldown')
    values = [(appid, name, stamp(current), 'USD', json.dumps(row, ensure_ascii=False))
              for name, row in zip(names, rows)]
    with conn:
        conn.executemany('''INSERT INTO cloud_market_items VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(appid, market_hash_name) DO UPDATE SET observed_at=excluded.observed_at,
            requested_currency=excluded.requested_currency, response_json=excluded.response_json''', values)
        conn.executemany('INSERT OR IGNORE INTO steam_search_observations VALUES (?, ?, ?, ?, ?)', values)
        conn.executemany('INSERT OR IGNORE INTO history_items(appid, market_hash_name) VALUES (?, ?)',
                         [(appid, name) for name in names])
        end = start + len(rows)
        set_state(conn, prefix + ':start', 0 if end >= total else end)
        set_state(conn, prefix + ':signature', signature)
        set_state(conn, prefix + ':reported_total', total)
        set_state(conn, prefix + ':after', stamp(current + timedelta(hours=1)) if end >= total else '')
    return len(rows)


def batch(conn, client, history_enabled=False, limit=10):
    current = now()
    if get_state(conn, 'cooldown') > stamp(current):
        return {'status': 'cooldown', 'until': get_state(conn, 'cooldown')}
    result = {'status': 'ok', 'search_items': 0, 'histories': 0,
              'history_enabled': history_enabled, 'page_errors': []}
    try:
        for appid in GAMES:
            try:
                result['search_items'] += fetch_page(conn, client, appid, now())
            except DownloadError as exc:
                if exc.kind != 'item':
                    raise
                with conn:
                    set_state(conn, str(appid) + ':after', stamp(now() + timedelta(hours=1)))
                result['page_errors'].append(appid)
        if history_enabled:
            cutoff = stamp(current - timedelta(days=1))
            # Alternate the first game each run; neither game's histories should
            # be starved by the other game's pending catalog.
            games = list(GAMES)
            if get_state(conn, 'first_game', '730') == '570':
                games.reverse()
            with conn:
                set_state(conn, 'first_game', games[-1])
            groups = []
            for appid in games:
                groups.append(conn.execute('''SELECT h.appid, h.market_hash_name
                    FROM history_items h LEFT JOIN sync_history_attempts a
                    ON a.appid=h.appid AND a.market_hash_name=h.market_hash_name
                    WHERE h.appid=? AND (h.fetched_at IS NULL OR julianday(h.fetched_at)<=julianday(?))
                    AND (a.retry_at IS NULL OR a.retry_at<=?)
                    ORDER BY COALESCE(h.fetched_at,''),h.market_hash_name LIMIT ?''',
                    (appid, cutoff, stamp(current), limit)).fetchall())
            selected = []
            for i in range(limit):
                for group in groups:
                    if i < len(group):
                        selected.append(group[i])
            failures = 0
            for appid, name in selected[:limit]:
                try:
                    data = client.get('pricehistory', dict(appid=appid, market_hash_name=name, l='english'))
                    validate_history(data)
                except DownloadError as exc:
                    if exc.kind != 'item':
                        raise
                    with conn:
                        conn.execute('''INSERT INTO sync_history_attempts VALUES (?, ?, ?)
                            ON CONFLICT(appid, market_hash_name) DO UPDATE SET retry_at=excluded.retry_at''',
                            (appid, name, stamp(now() + timedelta(days=1))))
                    failures += 1
                    if failures >= 3:
                        raise DownloadError('History unavailable; check session', kind='unavailable')
                    continue
                failures = 0
                with conn:
                    conn.execute('UPDATE history_items SET fetched_at=?,response_json=? WHERE appid=? AND market_hash_name=?',
                                 (stamp(now()), json.dumps(data, ensure_ascii=False, allow_nan=False), appid, name))
                    conn.execute('DELETE FROM sync_history_attempts WHERE appid=? AND market_hash_name=?', (appid, name))
                result['histories'] += 1
        if result['page_errors']:
            result['status'] = 'partial'
    except DownloadError as exc:
        until = stamp(now() + timedelta(seconds=max(3600, exc.retry_after)))
        with conn:
            set_state(conn, 'cooldown', until)
        result.update(status='paused', reason=exc.kind, until=until)
    return result


def publish(db, market_db, web_data):
    records, skipped = read_cloud(db)
    if market_db and market_db.is_file():
        records.extend(read_market(market_db))
    snapshot = make_snapshot([record for record in records if record['appid'] in GAMES], skipped)
    write_snapshot(snapshot, web_data / 'steam-latest.json')
    history_dir = web_data / 'history'
    history_dir.mkdir(parents=True, exist_ok=True)
    history_dir.chmod(0o755)
    index = []
    with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        for appid, name, raw in conn.execute('SELECT appid,market_hash_name,response_json FROM history_items WHERE response_json IS NOT NULL AND appid=?', (next(iter(GAMES)),)):
            try:
                data = json.loads(raw, parse_float=Decimal)
                if data.get('price_prefix') != '$' or data.get('price_suffix', '').strip() not in ('', 'USD'):
                    continue
                parsed, _ = parse_record({'appid': appid, 'market_hash_name': name, 'response': data}, name)
                if parsed is None:
                    continue
                _, game, points = parsed
                daily = to_daily(points)
                payload = dict(item_name=name, game=game, source='steam', points=daily)
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                filename = game + '-' + digest + '.json'
                target = web_data / 'history' / filename
                if not target.exists():
                    write_snapshot(payload, target)
                index.append(dict(item_name=name, game=game, file=filename, days=len(daily), first=daily[0][0], last=daily[-1][0]))
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                continue
    # New item files exist before the index references them. A failed run cannot
    # expose partial JSON. An empty index removes any previously published Dota entries.
    write_snapshot(dict(generated_at=stamp(now()), items=sorted(index, key=lambda r: (r['game'], r['item_name']))),
                   web_data / 'history' / 'index.json')
    return {'website_items': snapshot['item_count'], 'website_histories': len(index)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--market-db', type=Path)
    parser.add_argument('--web-data', type=Path, required=True)
    parser.add_argument('--cookie-file', type=Path)
    parser.add_argument('--history-limit', type=int, default=10)
    parser.add_argument('--delay', type=float, default=15)
    parser.add_argument('--publish-only', action='store_true')
    parser.add_argument('--game', choices=['cs2', 'dota2'], default='cs2')
    args = parser.parse_args()
    if args.game == 'dota2':
        GAMES.clear()
        GAMES[570] = 'dota2'
    if not 5 <= args.delay <= 3600 or not 0 <= args.history_limit <= 100:
        parser.error('delay must be 5..3600; history-limit must be 0..100')
    # A separate process cannot overlap this job, even when launched manually.
    import fcntl
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with (args.db.parent / 'steam-sync.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('{"status":"already_running"}')
            return
        cookie = ''
        if args.cookie_file and args.cookie_file.is_file():
            cookie = args.cookie_file.read_text().strip()
            if '\n' in cookie or '\r' in cookie:
                raise ValueError('Invalid session cookie file')
        with closing(sqlite3.connect(args.db)) as conn:
            initialize_sync(conn)
            result = {'status': 'publish_only'} if args.publish_only else batch(conn, SteamClient(cookie, args.delay), bool(cookie), args.history_limit)
        result.update(publish(args.db, args.market_db, args.web_data))
        result['checked_at'] = stamp(now())
        write_snapshot(result, args.web_data / 'steam-status.json')
        print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        sys.exit(1)
