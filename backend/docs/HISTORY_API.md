# SQLite price-history API

Run from the repository root (Python 3.10+):

```bash
python3 -m venv .venv-api
.venv-api/bin/python -m pip install -r backend/requirements-api.txt
export STEAM_HISTORY_DB="$PWD/backend/db/steam_cloud.db"
.venv-api/bin/python -m uvicorn backend.api.history_api:app --host 127.0.0.1 --port 8000
```

In another AWS terminal:

```bash
curl --get http://127.0.0.1:8000/api/price-history \
  --data-urlencode 'market_hash_name=AK-47 | Redline (Field-Tested)'
```

The endpoint reads CS2 (appid 730) from `history_items` with a parameterized query
and a read-only SQLite connection. It does not fetch Steam or need a Cookie.
Set STEAM_HISTORY_DB to steam_history.db to use the earlier downloader database.
Missing items or uncollected histories return 404; unavailable databases return
503; invalid stored responses return 500; invalid query input returns 422.

200 response contains market_hash_name, appid, source, fetched_at, point_count,
price_prefix, price_suffix and prices. Each prices entry retains the stored
Steam tuple `[date_text, median_sale_price, volume_string]`. Prices remain in
their original currency and units; prefix/suffix are not a verified ISO currency
code. No conversion, aggregation or interpolation is performed. Empty collected
histories return 200 with an empty prices array. Steam's historical buckets are
not individual transactions. The frontend's existing static JSON is unchanged.

This command runs in the foreground on loopback for verification. It is not yet
a persistent publicly deployed API. For production, run via systemd and proxy
`/api/` through the existing Nginx server to 127.0.0.1:8000. Do not expose the DB.

Tests (install httpx in the same environment first):

```bash
.venv-api/bin/python -m pip install httpx==0.28.1
.venv-api/bin/python -m unittest backend.tests.test_history_api
```
