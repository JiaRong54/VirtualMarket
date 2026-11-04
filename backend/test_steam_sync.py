import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from steam_sync import batch, fetch_page, get_state, initialize_sync, now, publish
from steam_history import DownloadError


def page(appid, names, total=None, start=0):
    return dict(success=True, start=start, total_count=len(names) if total is None else total,
                results=[dict(hash_name=n, asset_description=dict(appid=appid),
                              sell_price=29, sell_price_text='$0.29', sell_listings=12) for n in names])


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        initialize_sync(self.conn)

    def test_only_cs2_and_no_history_without_cookie(self):
        client = Mock()
        client.get.side_effect = [page(730, ['A']), page(570, ['B'])]
        result = batch(self.conn, client)
        self.assertEqual(result['search_items'], 1)
        self.assertEqual([c.args[1]['appid'] for c in client.get.call_args_list], [730])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM steam_search_observations').fetchone()[0], 1)

    def test_wrong_game_does_not_advance_cursor_or_save(self):
        client = Mock()
        client.get.return_value = page(440, ['TF2'])
        with self.assertRaises(DownloadError):
            fetch_page(self.conn, client, 730, now())
        self.assertEqual(get_state(self.conn, '730:start', '0'), '0')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM history_items').fetchone()[0], 0)

    def test_limit_cools_all_requests_across_batches(self):
        client = Mock()
        client.get.side_effect = DownloadError('limit', 'rate_limit', 7200)
        self.assertEqual(batch(self.conn, client)['status'], 'paused')
        self.assertEqual(batch(self.conn, client)['status'], 'cooldown')
        self.assertEqual(client.get.call_count, 1)

    def test_history_only_cs2_and_preserves_raw(self):
        history = dict(success=True, price_prefix='$', price_suffix='', prices=[['Nov 02 2026 01: +0', 0.29, '5']])
        client = Mock()
        client.get.side_effect = [page(730, ['A','B']), history, history]
        result = batch(self.conn, client, history_enabled=True, limit=2)
        self.assertEqual(result['histories'], 2)
        self.assertEqual([c.args[1]['appid'] for c in client.get.call_args_list[1:]], [730, 730])
        self.assertEqual(json.loads(self.conn.execute('SELECT response_json FROM history_items WHERE response_json IS NOT NULL LIMIT 1').fetchone()[0]), history)

    def test_publish_prices_and_history_without_using_sales_as_asks(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder)/'cloud.db'
            conn = sqlite3.connect(db)
            initialize_sync(conn)
            client = Mock()
            client.get.return_value = page(730, ['A'])
            fetch_page(conn, client, 730, now())
            with conn:
                conn.execute('UPDATE history_items SET response_json=?',
                             (json.dumps(dict(price_prefix='$',price_suffix='',prices=[['Nov 02 2026 01: +0',9.99,'5']])),))
            conn.close()
            dest = Path(folder)/'data'
            result = publish(db, None, dest)
            self.assertEqual(result,dict(website_items=1,website_histories=1))
            self.assertEqual(json.loads((dest/'steam-latest.json').read_text())['rows'][0]['lowest_price_minor'],29)
            index=json.loads((dest/'history/index.json').read_text())
            self.assertEqual(json.loads((dest/'history'/index['items'][0]['file']).read_text())['points'][0][1],999)

    def test_dota_is_preserved_in_database_but_removed_from_website(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder)/'cloud.db'
            conn = sqlite3.connect(db)
            initialize_sync(conn)
            with conn:
                conn.execute('INSERT INTO cloud_market_items VALUES (570, ?, ?, ?, ?)',
                             ('Dota item', now().isoformat(), 'USD', json.dumps(dict(sell_price=29, sell_price_text='$0.29', sell_listings=2))))
                conn.execute('INSERT INTO history_items VALUES (570, ?, ?, ?)',
                             ('Dota item', now().isoformat(), json.dumps(dict(price_prefix='$',price_suffix='',prices=[['Nov 02 2026 01: +0',9.99,'5']]))))
            conn.close()
            dest = Path(folder)/'data'
            self.assertEqual(publish(db, None, dest), dict(website_items=0,website_histories=0))
            self.assertEqual(json.loads((dest/'steam-latest.json').read_text())['rows'], [])
            self.assertEqual(json.loads((dest/'history/index.json').read_text())['items'], [])
            conn=sqlite3.connect(db)
            self.assertEqual(conn.execute('SELECT count(*) FROM history_items WHERE appid=570').fetchone()[0], 1)
            conn.close()

    def test_dota_mode_publishes_only_dota(self):
        import steam_sync
        with tempfile.TemporaryDirectory() as folder, patch.dict(steam_sync.GAMES, {570: 'dota2'}, clear=True):
            db = Path(folder) / 'dota.db'
            conn = sqlite3.connect(db)
            initialize_sync(conn)
            client = Mock()
            client.get.return_value = page(570, ['Dota item'])
            self.assertEqual(batch(conn, client)['search_items'], 1)
            self.assertEqual(client.get.call_args.args[1]['appid'], 570)
            with conn:
                conn.execute('UPDATE history_items SET response_json=?', (json.dumps(dict(price_prefix='$',price_suffix='',prices=[['Nov 02 2026 01: +0',1.25,'3']])),))
            conn.close()
            dest = Path(folder) / 'data'
            self.assertEqual(publish(db, None, dest), dict(website_items=1, website_histories=1))
            self.assertEqual(json.loads((dest/'steam-latest.json').read_text())['rows'][0]['game'], 'dota2')
            self.assertEqual(json.loads((dest/'history/index.json').read_text())['items'][0]['game'], 'dota2')
