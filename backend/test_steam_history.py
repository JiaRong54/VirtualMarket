import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import Mock

from steam_history import DownloadError, SteamClient, download, export_jsonl, initialize


def page(start, names, total):
    return {'success': True, 'start': start, 'total_count': total,
            'results': [{'hash_name': name, 'asset_description': {'appid': 730}} for name in names]}


HISTORY = {'success': True, 'price_prefix': '$', 'price_suffix': '',
           'prices': [['Oct 20 2026 01: +0', 1.234, '12']]}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        initialize(self.conn)
        self.addCleanup(self.conn.close)

    def test_actual_page_size_and_no_duplicate_requests_on_resume(self):
        client = Mock()
        client.get.side_effect = [page(0, ['A'], 2), HISTORY, page(1, ['B'], 2), HISTORY]
        download(self.conn, client)
        self.assertEqual(client.get.call_args_list[2].args[1]['start'], 1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM history_items WHERE response_json IS NOT NULL').fetchone()[0], 2)
        download(self.conn, client)
        self.assertEqual(client.get.call_count, 4)

    def test_resume_failed_item_without_redownloading_success(self):
        client = Mock()
        client.get.side_effect = [page(0, ['A', 'B'], 2), HISTORY, DownloadError('429')]
        with self.assertRaises(DownloadError):
            download(self.conn, client)
        resumed = Mock()
        resumed.get.return_value = HISTORY
        download(self.conn, resumed)
        self.assertEqual(resumed.get.call_count, 1)
        self.assertEqual(resumed.get.call_args.args[1]['market_hash_name'], 'B')

    def test_malformed_history_is_not_marked_complete(self):
        client = Mock()
        client.get.side_effect = [page(0, ['A'], 1), {'success': True, 'prices': [['bad']]}]
        with self.assertRaises(DownloadError):
            download(self.conn, client)
        self.assertIsNone(self.conn.execute('SELECT response_json FROM history_items').fetchone()[0])

    def test_export_preserves_precision_and_currency_metadata(self):
        client = Mock()
        client.get.side_effect = [page(0, ['A'], 1), HISTORY]
        download(self.conn, client)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.jsonl'
            export_jsonl(self.conn, path)
            self.assertEqual(json.loads(path.read_text())['response'], HISTORY)
            with self.assertRaises(FileExistsError):
                export_jsonl(self.conn, path)

    def test_http_limit_stops_without_retry_or_cookie_in_error(self):
        client = SteamClient('secret-cookie')
        client.opener = Mock()
        client.opener.open.side_effect = HTTPError('https://steamcommunity.com', 429, 'limited', {'Retry-After': '120'}, None)
        with self.assertRaisesRegex(DownloadError, 'Retry-After: 120') as result:
            client.get('pricehistory', {'appid': 730})
        self.assertNotIn('secret-cookie', str(result.exception))
        self.assertEqual(client.opener.open.call_count, 1)


if __name__ == '__main__':
    unittest.main()
