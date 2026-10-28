"""
Snapshot loader: turns one raw Skinport snapshot from S3 into price rows.

The collector Lambda saves Skinport's response byte for byte, Brotli
compressed, under keys like  cs2/2026/10/20/140012.json.br
This script reads one of those snapshots and writes rows in our locked
record shape, plus the source:

    item_name, game, timestamp, lowest_price_minor, listing_count, source

Prices become whole cents (12.40 -> 1240). The JSON is parsed with exact
decimals, so a price never passes through a float. Float math gets cents
wrong: 0.29 * 100 is 28.999999999999996, which int() turns into 28.

Outputs:
  --csv   one row per item, ready for a database bulk import
  --json  the same rows plus snapshot info, for the website

Usage:
  python load_snapshot.py --latest --csv rows.csv --json latest.json
  python load_snapshot.py --key cs2/2026/10/20/140012.json.br --csv rows.csv
  python load_snapshot.py --file sample.json.br --json latest.json

Bucket comes from --bucket or the BUCKET environment variable.
Needs:  pip install boto3 brotli
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

import brotli

COLUMNS = ["item_name", "game", "timestamp", "lowest_price_minor", "listing_count", "source"]
GAMES_BY_APP_ID = {"730": "cs2", "570": "dota2"}
KEY_PATTERN = re.compile(r"^(?P<game>[a-z0-9]+)/(?P<y>\d{4})/(?P<m>\d{2})/(?P<d>\d{2})/(?P<t>\d{6})")


# ------------------------------------------------------------------ helpers
def to_cents(price):
    """Exact dollars to whole cents. Decimal('12.4') -> 1240."""
    if price is None:
        return None
    return int((Decimal(str(price)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def decode_body(raw):
    """Snapshots are stored Brotli compressed. Accept plain JSON too."""
    try:
        return brotli.decompress(raw)
    except brotli.error:
        return raw


def info_from_key(key):
    """cs2/2026/10/20/140012.json.br -> ('cs2', '2026-10-20T14:00:12Z')"""
    match = KEY_PATTERN.match(key or "")
    if not match:
        return None, None
    g = match.groupdict()
    t = g["t"]
    stamp = f"{g['y']}-{g['m']}-{g['d']}T{t[0:2]}:{t[2:4]}:{t[4:6]}Z"
    return g["game"], stamp


# ------------------------------------------------------------------ core
def snapshot_to_rows(raw, key=None, metadata=None):
    """
    Raw snapshot bytes -> (rows, skipped).

    Items with no listings have no lowest price, so they are skipped and
    counted rather than stored with an empty price.
    """
    metadata = metadata or {}
    key_game, key_stamp = info_from_key(key)

    game = GAMES_BY_APP_ID.get(metadata.get("app_id", ""), key_game) or "cs2"
    stamp = metadata.get("collected_at") or key_stamp
    if stamp is None:
        raise ValueError("No timestamp: pass an S3 key like cs2/2026/10/20/140012.json.br")
    stamp = normalize_stamp(stamp)
    source = metadata.get("source", "skinport")

    items = json.loads(decode_body(raw), parse_float=Decimal)
    if not isinstance(items, list):
        raise ValueError(f"Expected a list of items, got {type(items).__name__}")

    rows, skipped = [], 0
    for item in items:
        name = item.get("market_hash_name")
        cents = to_cents(item.get("min_price"))
        if not name or cents is None:
            skipped += 1
            continue
        rows.append(
            {
                "item_name": name,
                "game": game,
                "timestamp": stamp,
                "lowest_price_minor": cents,
                "listing_count": int(item.get("quantity") or 0),
                "source": source,
            }
        )
    return rows, skipped


def normalize_stamp(stamp):
    """Any ISO time -> UTC like 2026-10-20T14:00:12Z."""
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ S3
def latest_key(s3, bucket, prefix="cs2/"):
    """Keys are zero padded dates, so the largest key is the newest."""
    newest = None
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if newest is None or obj["Key"] > newest:
                newest = obj["Key"]
    if newest is None:
        raise SystemExit(f"No snapshots under s3://{bucket}/{prefix}")
    return newest


def read_from_s3(bucket, key):
    import boto3  # only needed for S3 runs

    s3 = boto3.client("s3")
    if key is None:
        key = latest_key(s3, bucket)
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read(), key, obj.get("Metadata", {})


# ------------------------------------------------------------------ output
def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows, path, key, skipped):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    payload = {
        "snapshot_key": key,
        "collected_at": rows[0]["timestamp"] if rows else None,
        "item_count": len(rows),
        "skipped_no_listings": skipped,
        "rows": rows,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def main(argv=None):
    p = argparse.ArgumentParser(description="Turn one S3 snapshot into price rows.")
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--latest", action="store_true", help="newest snapshot in the bucket")
    where.add_argument("--key", help="a specific S3 key")
    where.add_argument("--file", help="a local snapshot file instead of S3")
    p.add_argument("--bucket", default=os.environ.get("BUCKET", "").strip())
    p.add_argument("--csv", help="write rows here for the database")
    p.add_argument("--json", help="write rows here for the website")
    args = p.parse_args(argv)

    if args.file:
        with open(args.file, "rb") as f:
            raw = f.read()
        key, metadata = guess_key_from_filename(args.file), {}
    else:
        if not args.bucket:
            p.error("set --bucket or the BUCKET environment variable")
        raw, key, metadata = read_from_s3(args.bucket, args.key)

    rows, skipped = snapshot_to_rows(raw, key=key, metadata=metadata)
    print(f"snapshot: {key}")
    print(f"rows:     {len(rows):,}  (skipped {skipped:,} with no listings)")
    if rows:
        print(f"time:     {rows[0]['timestamp']}")

    if args.csv:
        write_csv(rows, args.csv)
        print(f"csv:      {args.csv}")
    if args.json:
        write_json(rows, args.json, key, skipped)
        print(f"json:     {args.json}")
    if not args.csv and not args.json:
        print("(no --csv or --json given, nothing written)")
    return 0


def guess_key_from_filename(path):
    """Lets a local copy named like cs2_2026_10_20_140012.json.br keep its time."""
    name = os.path.basename(path)
    match = re.match(r"([a-z0-9]+)[_/](\d{4})[_/](\d{2})[_/](\d{2})[_/](\d{6})", name)
    if match:
        return "/".join(match.groups())
    return name


if __name__ == "__main__":
    sys.exit(main())
