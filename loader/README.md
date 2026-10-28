# Snapshot loader

Turns one raw Skinport snapshot from S3 into price rows for the database and the website.

```
S3 snapshot (.json.br)  ->  decode Brotli  ->  dollars to exact cents  ->  rows.csv   (database import)
                                                                      ->  latest.json (website)
```

Every row has the record shape we locked, plus where the price came from:

| column | example | notes |
| --- | --- | --- |
| `item_name` | `AK-47 \| Redline (Field-Tested)` | Skinport `market_hash_name` |
| `game` | `cs2` | from S3 metadata `app_id`, else the key prefix |
| `timestamp` | `2026-10-20T14:00:12Z` | from S3 metadata `collected_at`, else the key |
| `lowest_price_minor` | `1240` | whole cents, from Skinport `min_price` |
| `listing_count` | `1842` | Skinport `quantity` |
| `source` | `skinport` | |

Items with no listings have no lowest price. They are skipped and counted, not stored with an empty price.

## Why cents need care

Plain float math loses cents: `int(0.29 * 100)` is `28`, and `int(1.15 * 100)` is `114`. The loader parses the JSON with Python's `Decimal`, so a price is never a float, and rounds half up to whole cents. The tests check both cases.

## Run it

```bash
cd loader
pip install -r requirements.txt

# Tests (no AWS needed)
python -m pytest -v tests

# Newest snapshot in the bucket, written for the database and the website
export BUCKET=skin-market-snapshots
python load_snapshot.py --latest --csv rows.csv --json ../frontend/public/data/latest.json

# A specific snapshot
python load_snapshot.py --key cs2/2026/10/20/140012.json.br --csv rows.csv
```

S3 runs use your normal AWS credentials (`aws configure`). The IAM user needs `s3:ListBucket` on the bucket and `s3:GetObject` on its objects.

Writing `latest.json` into `frontend/public/data/` makes the dashboard table show those rows on the next page load.

## Steam price history (from Jerome's downloader)

Jerome's `backend/steam_history.py` downloads Steam price history into `backend/db/steam_history.db`. `convert_history.py` turns that into chart data for the site and rows for the database. Each point is a date, the median sale price, and the number sold. These are sales, not listings, so they get their own table instead of `price_observations`.

From the repo root:

```bash
python3 loader/convert_history.py --in backend/db/steam_history.db --site frontend/public/data --csv loader/steam_rows.csv
```

It reads any of these:

- the downloader database (`history_items`; items not downloaded yet are skipped)
- the downloader's export: `python3 backend/steam_history.py --export exports/steam_history.jsonl`
- single saved Steam responses, one `.json` file per item

Outputs:

- `--site` writes `history/index.json` plus one small file per item, one point per day. Each item then gets a chart on the site, and the Price Movements page lists them.
- `--csv` writes every raw point (`item_name, game, timestamp, median_price_minor, volume_sold, source`) for the database.

Steam reports prices in the account's wallet currency. Anything that isn't US dollars is skipped and counted. The database file is git-ignored, so it moves between laptops by sharing the file or the export.

## Next

- Agree the import with Jerome: his tables use an item id, so his side matches `item_name` to the items table and inserts the price rows.
- Run the loader automatically: an S3 trigger starts it each time the collector saves a new snapshot.
