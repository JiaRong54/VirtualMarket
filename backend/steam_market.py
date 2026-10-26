"""Fetch Steam Market prices into the existing SQLite schema and export stored data.

Examples (from the project root):
  python backend/steam_market.py fetch --name "AK-47 | Redline (Field-Tested)"
  python backend/steam_market.py export --output exports/steam_market.csv

Uses Python's standard library. The community priceoverview endpoint does not
require a Web API key, but it is undocumented and may reject requests with 429.
Stored history consists of our own observations, not Steam's historical sales.
"""

import argparse
import csv
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

try:
    from .db.db import DB_PATH, connect_db, initialize_db, save_observations
except ImportError:
    from db.db import DB_PATH, connect_db, initialize_db, save_observations

SOURCE = 'steam_community_overview'
FIELDS = ('appid', 'market_hash_name', 'observed_at', 'lowest_price_minor',
          'currency', 'listing_count', 'volume_24h', 'source', 'is_demo')


class SteamMarketError(RuntimeError):
    pass


def fetch_price(appid, name):
    """Return one normalized USD observation without writing to the database."""
    #Connecting Steam Market API
    if type(appid) is not int or appid <= 0 or not isinstance(name, str) or not name.strip():
        raise ValueError('Provide a positive appid and an exact market item name.')
    query = urlencode({'appid': appid, 'market_hash_name': name,
                       'currency': 1, 'country': 'US', 'l': 'english'})
    request = Request('https://steamcommunity.com/market/priceoverview/?' + query,
                      headers={'Accept': 'application/json', 'User-Agent': 'VirtualMarket/1.0'})
    #Error handling for Steam API request
    try:
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise SteamMarketError('HTTP 429: Steam rate limited or blocked the request. Wait before retrying; no data was saved.') from None
        raise SteamMarketError('Steam returned HTTP {}. No data was saved.'.format(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise SteamMarketError('Network/TLS connection failed or timed out. No data was saved.') from None
    except (ValueError, UnicodeError):
        raise SteamMarketError('Steam returned invalid JSON. No data was saved.') from None
    if not isinstance(data, dict) or data.get('success') not in (True, 1):
        raise SteamMarketError('Steam returned no successful result. Check the exact item name or try later.')
    #Validate the returned price and volume formats, and convert to normalized record.
    price = data.get('lowest_price')
    if not isinstance(price, str) or not re.fullmatch(r'\$(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}', price):
        raise SteamMarketError('No recognized USD lowest price returned. No data was saved.')
    volume = data.get('volume')
    if volume is not None:
        if not isinstance(volume, str) or not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)', volume):
            raise SteamMarketError('Unrecognized volume format. No data was saved.')
        volume = int(volume.replace(',', ''))
    return {'appid': appid, 'market_hash_name': name,
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'lowest_price_minor': int(Decimal(price[1:].replace(',', '')) * 100),
            'currency': 'USD', 'listing_count': None, 'volume_24h': volume,
            'source': SOURCE, 'is_demo': False}


def fetch_and_save(appid, name, db_path=DB_PATH):
    record = fetch_price(appid, name)
    initialize_db(db_path)
    saved = save_observations([record], db_path)
    return {'status': 'saved', 'database': str(Path(db_path).resolve()),
            **saved, 'observation': record}


def read_saved(db_path=DB_PATH):
    """Return real overview/search observations, excluding demo/other sources."""
    if not Path(db_path).is_file():
        raise ValueError('Database does not exist yet. Run fetch successfully first.')
    with connect_db(db_path) as connection:
        rows = connection.execute('''SELECT i.appid, i.market_hash_name, p.observed_at,
            p.lowest_price_minor, p.currency, p.listing_count, m.volume_24h, p.source, p.is_demo
            FROM price_observations p JOIN items i ON i.id=p.item_id
            LEFT JOIN observation_metrics m ON m.observation_id=p.id
            WHERE p.source IN (?, ?) AND p.is_demo=0
            ORDER BY p.observed_at, i.appid, i.market_hash_name''', (SOURCE, 'steam_community_search')).fetchall()
    return [dict(row) for row in rows]


def import_search(input_path, output, db_path=DB_PATH):
    """Import a saved live USD search receipt; preserve image URLs in its export.

    This imports an existing response, and does not itself prove a new connection.
    The receipt must contain fetched_at, requested_currency, and response.
    """
    # Validate the receipt and extract the observed_at timestamp, then normalize it.
    receipt = json.loads(Path(input_path).read_text(encoding='utf-8-sig'))
    data = receipt.get('response', {})
    if receipt.get('requested_currency') != 'USD' or data.get('success') not in (True, 1):
        raise ValueError('Expected a successful USD market search receipt.')
    rows = data.get('results')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Search receipt contains no market items.')
    records, exported = [], []
    # Validate each row and convert to a normalized record, preserving the image URL for export.
    for row in rows:
        asset = row.get('asset_description', {})
        price, text = row.get('sell_price'), row.get('sell_price_text')
        if (type(price) is not int or price < 0 or not isinstance(text, str)
                or not re.fullmatch(r'\$(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}', text)
                or int(Decimal(text[1:].replace(',', '')) * 100) != price):
            raise ValueError('Search price is missing or not consistent with USD cents.')
        record = {'appid': asset.get('appid'), 'market_hash_name': row.get('hash_name'),
                  'observed_at': receipt.get('fetched_at'), 'lowest_price_minor': price,
                  'currency': 'USD', 'listing_count': row.get('sell_listings'),
                  'volume_24h': None, 'source': 'steam_community_search', 'is_demo': False}
        icon = asset.get('icon_url')
        image_url = 'https://steamcommunity.com/economy/image/' + quote(icon, safe='') if isinstance(icon, str) and icon else None
        records.append(record)
        exported.append(dict(record, lowest_price_display=text, image_url=image_url))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to replace either source data or a previous export.
    with output.open('x', encoding='utf-8') as stream:
        initialize_db(db_path)
        saved = save_observations(records, db_path)
        result = {'status': 'saved_and_exported', 'input_receipt': str(Path(input_path).resolve()),
                  'database': str(Path(db_path).resolve()), **saved,
                  'note': 'Search listing counts are not sales volume. Image URLs are preserved in this export, not the price schema.',
                  'items': exported}
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return {'status': result['status'], **saved, 'file': str(output.resolve())}


def export_saved(output, db_path=DB_PATH):
    # Export all saved observations to a new CSV or JSON file, excluding demo/other sources.
    output = Path(output)
    if output.suffix.lower() not in ('.csv', '.json'):
        raise ValueError('Export path must end in .csv or .json.')
    if output.resolve() == Path(db_path).resolve():
        raise ValueError('Export must not overwrite the database.')
    rows = read_saved(db_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids accidentally replacing an existing export/source file.
    with output.open('x', encoding='utf-8-sig' if output.suffix.lower() == '.csv' else 'utf-8', newline='') as stream:
        if output.suffix.lower() == '.json':
            json.dump(rows, stream, ensure_ascii=False, indent=2)
        else:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return {'status': 'exported', 'rows': len(rows), 'file': str(output.resolve())}


def main():
    # Set up the available commands and their options.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    # Fetch needs a game ID and an exact item name.
    fetch = commands.add_parser('fetch', help='Fetch a live price and save it to SQLite')
    fetch.add_argument('--appid', type=int, default=730, help='730 = CS2; 570 = Dota 2')
    fetch.add_argument('--name', required=True, help='Exact market_hash_name, including wear condition')
    # Show reads the database; export writes its data to a file.
    show = commands.add_parser('show', help='Read saved observations without calling Steam')
    export = commands.add_parser('export', help='Export saved observations to a new CSV or JSON file')
    export.add_argument('--output', required=True, type=Path)
    # Import uses an existing search response and creates a new result file.
    search_import = commands.add_parser('import-search', help='Save a captured live USD search receipt and export image links')
    search_import.add_argument('--input', required=True, type=Path)
    search_import.add_argument('--output', required=True, type=Path)
    # Allow every command to choose a database file.
    for command in (fetch, show, export, search_import):
        command.add_argument('--db', type=Path, default=DB_PATH)
    # Read the command and options entered in the terminal.
    args = parser.parse_args()
    try:
        # Run the function that matches the selected command.
        if args.command == 'fetch':
            result = fetch_and_save(args.appid, args.name, args.db)
        elif args.command == 'show':
            result = read_saved(args.db)
        elif args.command == 'import-search':
            result = import_search(args.input, args.output, args.db)
        else:
            result = export_saved(args.output, args.db)
        # Display the result and return a success exit code.
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SteamMarketError, ValueError, OSError, sqlite3.Error) as exc:
        # Display the error and return a failure exit code.
        print('FAIL: {}'.format(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
