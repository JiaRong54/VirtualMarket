import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from load_steam import make_snapshot, read_cloud, read_market, write_snapshot


def observation(**changes):
    return dict(dict(appid=730, market_hash_name='A', observed_at='2026-11-03T12:00:00Z',
                     lowest_price_minor=29, listing_count=None, currency='USD',
                     source='steam_community_overview'), **changes)


class SteamSnapshotTests(unittest.TestCase):
    def test_latest_per_game_and_item_and_unknown_count(self):
        result = make_snapshot([observation(), observation(lowest_price_minor=115, observed_at='2026-11-03T08:30:00-04:00'),
                                observation(appid=570)])
        self.assertEqual(result['item_count'], 2)
        cs2 = next(r for r in result['rows'] if r['game'] == 'cs2')
        self.assertEqual(cs2['lowest_price_minor'], 115)
        self.assertIsNone(cs2['listing_count'])

    def test_rejects_other_sources_currency_history_and_invalid_data(self):
        result = make_snapshot([observation(source='skinport'), observation(source='steam_community_pricehistory'),
                                observation(currency='EUR'), observation(lowest_price_minor=1.15),
                                observation(appid=440), observation(observed_at='2026-11-03'),
                                observation(listing_count=-1)])
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['skipped_records'], 7)

    def test_prefers_known_count_on_same_timestamp(self):
        result = make_snapshot([observation(listing_count=30, source='steam_community_search'), observation()])
        self.assertEqual(result['rows'][0]['listing_count'], 30)

    def test_cloud_search_requires_matching_dollar_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cloud.db'
            with sqlite3.connect(path) as conn:
                conn.execute('CREATE TABLE cloud_market_items(appid, market_hash_name, observed_at, requested_currency, response_json)')
                for name, price, text in [('A', 29, '$0.29'), ('B', 115, '$1.14'), ('C', 100, '1.00 EUR')]:
                    conn.execute('INSERT INTO cloud_market_items VALUES (?, ?, ?, ?, ?)',
                                 (730, name, '2026-11-03T12:00:00Z', 'USD',
                                  json.dumps(dict(sell_price=price, sell_price_text=text, sell_listings=12))))
            conn.close()
            records, skipped = read_cloud(path)
            self.assertEqual(skipped, 2)
            result = make_snapshot(records)
            self.assertEqual(result['rows'][0]['lowest_price_minor'], 29)
            self.assertEqual(result['rows'][0]['listing_count'], 12)

    def test_database_excludes_demo_and_other_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'market.db'
            with sqlite3.connect(path) as conn:
                conn.executescript('''CREATE TABLE items(id, appid, market_hash_name);
                    CREATE TABLE price_observations(item_id, observed_at, lowest_price_minor,
                    listing_count, currency, source, is_demo);
                    INSERT INTO items VALUES (1,730,'A');''')
                for source, demo in [('steam_community_search', 0), ('steam_community_search', 1), ('skinport', 0)]:
                    conn.execute('INSERT INTO price_observations VALUES (1, ?, 29, 12, ?, ?, ?)',
                                 ('2026-11-03T12:00:00Z', 'USD', source, demo))
            conn.close()
            self.assertEqual(len(read_market(path)), 1)

    def test_atomic_output_and_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'steam-latest.json'
            result = make_snapshot([observation()])
            write_snapshot(result, path)
            self.assertEqual(json.loads(path.read_text()), result)
            missing = Path(directory) / 'missing.db'
            with self.assertRaises(sqlite3.OperationalError):
                read_market(missing)
            self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
