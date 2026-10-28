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

## Steam price history (Jerome's files)

`steam_history.py` converts saved Steam price history files: the `{"prices": [["Aug 14 2014 01: +0", 3.271, "420"], ...]}` response, one file per item. Each point is a date, the median sale price, and the number sold. These are sales, not listings, so they get their own table.

```bash
python steam_history.py --in path/to/steam_files --site ../frontend/public/data --csv steam_rows.csv
```

- `--site` writes `history/index.json` plus one small file per item, one point per day. Each item then gets a chart on the site, and the Price Movements page lists them.
- `--csv` writes every raw point (`item_name, game, timestamp, median_price_minor, volume_sold, source`) for the database.

The item name comes from `market_hash_name`, `name`, `item_name` or `hash_name` in the file, else the file name. Files that aren't price history are skipped and counted. Steam reports prices in the account's currency, so check `price_prefix` is `$`.

## Next

- Agree the import with Jerome: his tables use an item id, so his side matches `item_name` to the items table and inserts the price rows.
- Run the loader automatically: an S3 trigger starts it each time the collector saves a new snapshot.
