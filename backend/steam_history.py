"""Download Steam's returned price-history series with resumable discovery.

Standard library only. Run --help or see STEAM_HISTORY.md.
"""
import argparse
import getpass
import json
import math
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_DB = Path(__file__).resolve().parent / 'db' / 'steam_history.db'


class DownloadError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a login cookie to a redirected host.
        return None


class SteamClient:
    def __init__(self, cookie, delay=15):
        self.cookie = cookie
        self.delay = delay
        self.last_request = None
        self.opener = build_opener(NoRedirect())

    def get(self, route, params):
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        request = Request('https://steamcommunity.com/market/' + route + '/?' + urlencode(params),
                          headers={'Cookie': self.cookie, 'Accept': 'application/json',
                                   'User-Agent': 'VirtualMarket-History/1.0'})
        try:
            with self.opener.open(request, timeout=30) as response:
                data = json.load(response)
        except HTTPError as exc:
            if exc.code == 429:
                retry = exc.headers.get('Retry-After', 'not specified')
                raise DownloadError('Steam rate limit (429). Retry-After: {}. Resume later.'.format(retry)) from None
            if exc.code in (401, 403, 302, 301):
                raise DownloadError('Steam denied access or requires login. Refresh your own session and resume.') from None
            raise DownloadError('Steam HTTP {}; progress retained.'.format(exc.code)) from None
        except (URLError, TimeoutError, OSError):
            raise DownloadError('Network request failed; progress retained. Resume later.') from None
        except (ValueError, UnicodeError):
            raise DownloadError('Steam returned invalid JSON; check login/access before resuming.') from None
        if not isinstance(data, dict) or data.get('success') not in (True, 1):
            raise DownloadError('Steam returned an unsuccessful result; check session/item availability and resume.')
        return data


def initialize(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS discovery (
            scope INTEGER PRIMARY KEY, next_start INTEGER NOT NULL DEFAULT 0,
            complete INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS history_items (
            appid INTEGER NOT NULL, market_hash_name TEXT NOT NULL,
            fetched_at TEXT, response_json TEXT,
            PRIMARY KEY(appid, market_hash_name));
    ''')


def download_pending(conn, client, appid):
    sql = 'SELECT appid, market_hash_name FROM history_items WHERE response_json IS NULL'
    params = ()
    if appid:
        sql += ' AND appid=?'
        params = (appid,)
    # Fetch one record at a time; each successful history is its own checkpoint.
    while True:
        item = conn.execute(sql + ' ORDER BY appid, market_hash_name LIMIT 1', params).fetchone()
        if item is None:
            return
        game, name = item
        data = client.get('pricehistory', {'appid': game, 'market_hash_name': name, 'l': 'english'})
        prices = data.get('prices')
        if not isinstance(prices, list):
            raise DownloadError('History response is missing prices; item remains pending.')
        for row in prices:
            if (not isinstance(row, list) or len(row) != 3 or not isinstance(row[0], str)
                    or type(row[1]) not in (int, float) or not math.isfinite(row[1]) or row[1] < 0
                    or not str(row[2]).isdigit()):
                raise DownloadError('Unrecognized history row; item remains pending.')
        with conn:
            conn.execute('UPDATE history_items SET fetched_at=?, response_json=? WHERE appid=? AND market_hash_name=?',
                         (datetime.now(timezone.utc).isoformat(), json.dumps(data, ensure_ascii=False, allow_nan=False), game, name))
        print('Saved: {} / {} ({} history points)'.format(game, name, len(prices)), flush=True)


def download(conn, client, appid=730):
    scope = appid or 0
    with conn:
        conn.execute('INSERT OR IGNORE INTO discovery(scope) VALUES (?)', (scope,))
    while True:
        download_pending(conn, client, appid)
        start, complete = conn.execute('SELECT next_start, complete FROM discovery WHERE scope=?', (scope,)).fetchone()
        if complete:
            print('Finished this search snapshot. Coverage is limited to Steam search results.')
            return
        params = {'query': '', 'start': start, 'count': 100, 'norender': 1,
                  'sort_column': 'name', 'sort_dir': 'asc', 'l': 'english'}
        if appid:
            params['appid'] = appid
        data = client.get('search/render', params)
        rows, total = data.get('results'), data.get('total_count')
        if not isinstance(rows, list) or type(total) is not int or total < 0:
            raise DownloadError('Invalid search response; discovery checkpoint retained.')
        if data.get('start', start) != start or (not rows and start < total):
            raise DownloadError('Search pagination stalled; resume later.')
        items = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('asset_description'), dict):
                raise DownloadError('Invalid search item.')
            game, name = row['asset_description'].get('appid'), row.get('hash_name')
            if type(game) is not int or game <= 0 or not isinstance(name, str) or not name.strip() or (appid and game != appid):
                raise DownloadError('Invalid search item identity; checkpoint retained.')
            items.append((game, name))
        with conn:
            before = conn.total_changes
            conn.executemany('INSERT OR IGNORE INTO history_items(appid, market_hash_name) VALUES (?, ?)', items)
            if rows and conn.total_changes == before and start + len(rows) < total:
                raise DownloadError('Search returned only known items; pagination may be capped or unstable.')
            conn.execute('UPDATE discovery SET next_start=?, complete=? WHERE scope=?',
                         (start + len(rows), int(start + len(rows) >= total), scope))
        print('Discovery: {} / {} search results'.format(start + len(rows), total), flush=True)


def export_jsonl(conn, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        for game, name, fetched, raw in conn.execute('SELECT * FROM history_items WHERE response_json IS NOT NULL ORDER BY appid, market_hash_name'):
            stream.write(json.dumps({'appid': game, 'market_hash_name': name, 'fetched_at': fetched,
                                     'source': 'steam_community_pricehistory', 'response': json.loads(raw)}, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--appid', type=int, default=730)
    scope.add_argument('--all-apps', action='store_true', help='Search the whole market instead of CS2')
    parser.add_argument('--delay', type=float, default=15, help='Seconds between requests (minimum 5; no guarantee against limits)')
    parser.add_argument('--export', type=Path, help='Offline export to a NEW JSONL file; does not download')
    args = parser.parse_args()
    if args.appid <= 0 or not math.isfinite(args.delay) or args.delay < 5:
        parser.error('appid must be positive; delay must be finite and at least 5 seconds')
    try:
        if args.export:
            with sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True) as conn:
                export_jsonl(conn, args.export)
            print('Exported to {}'.format(args.export.resolve()))
            return 0
        cookie = getpass.getpass('Paste your own steamcommunity.com Cookie header (hidden, not saved): ').strip()
        if not cookie or '\r' in cookie or '\n' in cookie:
            raise DownloadError('A valid single-line session Cookie header is required.')
        args.db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(args.db) as conn:
            initialize(conn)
            download(conn, SteamClient(cookie, args.delay), None if args.all_apps else args.appid)
        return 0
    except (DownloadError, OSError, sqlite3.Error, ValueError) as exc:
        print('STOP: {}'.format(exc), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nStopped. Completed items are retained; rerun the same command to resume.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
