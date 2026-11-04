import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from backend.history_api import create_app


class HistoryApiTests(unittest.TestCase):
    def test_history_and_missing_states(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.db"
            prices = [["Feb 06 2024 01: +0", 3.25, "12"]]
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE history_items (appid INTEGER,market_hash_name TEXT,fetched_at TEXT,response_json TEXT)")
                db.executemany("INSERT INTO history_items VALUES (?,?,?,?)", [
                    (730, "AK-47 | Redline (Field-Tested)", "2026-11-03", json.dumps({"prices": prices, "price_prefix": "€", "price_suffix": ""})),
                    (730, "pending", None, None),
                    (730, "broken", None, "not json"),
                    (570, "dota only", None, "{}"),
                ])
            db.close()
            with TestClient(create_app(path)) as client:
                result = client.get("/api/price-history", params={"market_hash_name": "AK-47 | Redline (Field-Tested)"})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["prices"], prices)
                self.assertEqual(result.json()["price_prefix"], "€")
                for name in ("pending", "missing", "dota only", "' OR 1=1 --"):
                    self.assertEqual(client.get("/api/price-history", params={"market_hash_name": name}).status_code, 404)
                self.assertEqual(client.get("/api/price-history", params={"market_hash_name": "broken"}).status_code, 500)
                self.assertEqual(client.get("/api/price-history").status_code, 422)
            missing = Path(folder) / "absent.db"
            with TestClient(create_app(missing)) as client:
                self.assertEqual(client.get("/api/price-history", params={"market_hash_name": "x"}).status_code, 503)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
