"""Export verified Steam listing observations as the website's price snapshot.

Standard library only. History sale medians are never used as listing prices.
Optional --name fetches live prices using the existing backend before exporting.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES = {730: 'cs2', 570: 'dota2'}
SOURCES = ('steam_community_overview', 'steam_community_search')
USD_PRICE = re.compile(r'\$(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}')


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Observation timestamp must include a timezone')
    return dt.astimezone(timezone.utc).isoformat()


def read_market(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute('''
            SELECT i.appid, i.market_hash_name, p.observed_at,
                   p.lowest_price_minor, p.listing_count, p.currency, p.source
            FROM price_observations p JOIN items i ON i.id=p.item_id
            WHERE p.is_demo=0 AND p.currency='USD' AND p.source IN (?, ?)
        ''', SOURCES)]


def read_cloud(path):
    """Read raw search rows produced by aws_collector; verify USD text/cents."""
    records = []
    skipped = 0
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        for appid, name, observed, currency, raw in conn.execute('''
                SELECT appid, market_hash_name, observed_at, requested_currency,
                       response_json FROM cloud_market_items'''):
            try:
                row = json.loads(raw)
                price, text = row.get('sell_price'), row.get('sell_price_text')
                if (currency != 'USD' or type(price) is not int or price < 0
                        or not isinstance(text, str) or not USD_PRICE.fullmatch(text)
                        or int(Decimal(text[1:].replace(',', '')) * 100) != price):
                    raise ValueError('Unverified USD price')
                records.append(dict(appid=appid, market_hash_name=name, observed_at=observed,
                                    currency='USD', lowest_price_minor=price,
                                    listing_count=row.get('sell_listings'), source=SOURCES[1]))
            except (ValueError, TypeError, AttributeError):
                skipped += 1
    return records, skipped


def make_snapshot(records, skipped=0):
    latest = {}
    for record in records:
        try:
            game = GAMES[record['appid']]
            name, price, listings = record['market_hash_name'], record['lowest_price_minor'], record['listing_count']
            if (record['source'] not in SOURCES or record['currency'] != 'USD'
                    or not isinstance(name, str) or not name.strip()
                    or type(price) is not int or not 0 <= price <= 2**53 - 1
                    or (listings is not None and (type(listings) is not int or not 0 <= listings <= 2**53 - 1))):
                raise ValueError('Invalid Steam listing observation')
            row = dict(item_name=name, game=game, timestamp=utc(record['observed_at']),
                       lowest_price_minor=price, listing_count=listings, source=record['source'])
            key = (game, name)
            old = latest.get(key)
            # Normalize times before comparison; prefer a known listing count on ties.
            if old is None or (row['timestamp'], row['listing_count'] is not None) > (old['timestamp'], old['listing_count'] is not None):
                latest[key] = row
        except (KeyError, ValueError, TypeError, AttributeError):
            skipped += 1
    rows = sorted(latest.values(), key=lambda r: (r['game'], r['item_name']))
    return dict(source='steam', currency='USD', snapshot_key=None,
                collected_at=max((r['timestamp'] for r in rows), default=None),
                generated_at=datetime.now(timezone.utc).isoformat(),
                item_count=len(rows), skipped_no_listings=0, skipped_records=skipped, rows=rows)


def write_snapshot(snapshot, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically so the web server never serves a half-written JSON file.
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                         suffix='.tmp', delete=False) as stream:
            temp = Path(stream.name)
            json.dump(snapshot, stream, ensure_ascii=False, allow_nan=False)
        os.chmod(temp, 0o644)
        os.replace(temp, output)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, help='Existing market.db; default if --cloud-db is absent')
    parser.add_argument('--cloud-db', type=Path, help='Cloud collector DB containing cloud_market_items')
    parser.add_argument('--json', type=Path, default=ROOT / 'frontend/public/data/csgo2/steam-latest.json')
    parser.add_argument('--name', action='append', default=[], help='Fetch this exact item name before exporting; repeatable')
    parser.add_argument('--appid', type=int, choices=GAMES, default=730)
    parser.add_argument('--delay', type=float, default=15)
    args = parser.parse_args()
    if not 5 <= args.delay <= 3600:
        parser.error('delay must be between 5 and 3600 seconds')
    db = args.db or (ROOT / 'backend/db/market.db' if not args.cloud_db or args.name else None)
    for source in (db, args.cloud_db):
        if source and args.json.resolve() == source.resolve():
            parser.error('JSON output must not overwrite an input database')
    if args.name:
        sys.path.insert(0, str(ROOT))
        from backend.steam.steam_market import fetch_and_save
        for index, name in enumerate(args.name):
            if index:
                time.sleep(args.delay)
            fetch_and_save(args.appid, name, db)
    records = read_market(db) if db else []
    skipped = 0
    if args.cloud_db:
        cloud, skipped = read_cloud(args.cloud_db)
        records.extend(cloud)
    snapshot = make_snapshot(records, skipped)
    if not snapshot['rows']:
        raise ValueError('No valid Steam listing prices; existing website data was not replaced')
    write_snapshot(snapshot, args.json)
    print(json.dumps({'items': snapshot['item_count'], 'skipped': snapshot['skipped_records'], 'output': str(args.json)}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
        print('ERROR: {}'.format(exc), file=sys.stderr)
        sys.exit(1)
