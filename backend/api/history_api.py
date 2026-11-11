"""Read-only API for the history_items table populated by steam_sync.py."""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from backend.steam.steam_history import DownloadError, validate_history


def create_app(db_path=None):
    app = FastAPI(title="VirtualMarket price history")
    database = Path(db_path or os.environ.get("STEAM_HISTORY_DB", Path(__file__).resolve().parents[1] / "db" / "steam_cloud.db"))

    @app.get("/api/price-history")
    def price_history(market_hash_name: str = Query(min_length=1, max_length=512)):
        try:
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
                row = conn.execute(
                    "SELECT fetched_at,response_json FROM history_items WHERE appid=? AND market_hash_name=?",
                    (730, market_hash_name),
                ).fetchone()
        except sqlite3.Error:
            raise HTTPException(503, "History database unavailable") from None
        if row is None:
            raise HTTPException(404, "Item not found")
        fetched_at, raw = row
        if raw is None:
            raise HTTPException(404, "History not collected yet")
        try:
            data = json.loads(raw)
            prices = validate_history(data)
        except (ValueError, TypeError, AttributeError, DownloadError):
            raise HTTPException(500, "Stored history is invalid") from None
        return {
            "appid": 730, "market_hash_name": market_hash_name,
            "source": "Steam Market", "fetched_at": fetched_at,
            "price_prefix": data.get("price_prefix"),
            "price_suffix": data.get("price_suffix"),
            "point_count": len(prices), "prices": prices,
        }

    return app


app = create_app()
