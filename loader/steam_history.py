"""
Steam history converter: turns saved Steam price history files into
data for the website and rows for the database.

Steam's market price history response looks like this:

    {"success": true, "price_prefix": "$", "price_suffix": "",
     "prices": [["Aug 14 2014 01: +0", 3.271, "420"], ...]}

Each point is [date, median sale price, number sold]. Older points are one
per day; the last month is one per hour. The response does not include the
item's name, so the name is read from the file if it has one
(market_hash_name, name, item_name or hash_name), else from the file name.

These are SALES (what items sold for), not listings (what sellers ask).
They go in their own table, not in the listing table's lowest price column.

Outputs:
  --site DIR   DIR/history/index.json plus one small file per item, with
               one point per day, for the item page charts
  --csv FILE   every raw point, for the database

Usage:
  python steam_history.py --in steam_data/ --site ../frontend/public/data --csv steam_rows.csv
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from load_snapshot import GAMES_BY_APP_ID, to_cents

CSV_COLUMNS = ["item_name", "game", "timestamp", "median_price_minor", "volume_sold", "source"]
NAME_KEYS = ("market_hash_name", "name", "item_name", "hash_name", "item")
APP_ID_KEYS = ("appid", "app_id", "appId")
STEAM_DATE = re.compile(r"^([A-Z][a-z]{2}) (\d{1,2}) (\d{4}) (\d{1,2}):")
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


# ------------------------------------------------------------------ parsing
def parse_steam_date(text):
    """'Aug 14 2014 01: +0' -> datetime(2014, 8, 14, 1, tzinfo=UTC)"""
    match = STEAM_DATE.match(text.strip())
    if not match:
        raise ValueError(f"Unrecognized Steam date: {text!r}")
    mon, day, year, hour = match.groups()
    return datetime(int(year), MONTHS[mon], int(day), int(hour), tzinfo=timezone.utc)


def read_history_file(path, default_game="cs2"):
    """
    One saved file -> (item_name, game, points) or None if it isn't price history.
    points: list of (datetime, cents, volume), oldest first.
    """
    with open(path, "rb") as f:
        try:
            data = json.loads(f.read(), parse_float=Decimal)
        except ValueError:
            return None

    if isinstance(data, list):  # just the prices array
        data = {"prices": data}
    if not isinstance(data, dict) or not isinstance(data.get("prices"), list):
        return None

    name = next((data[k] for k in NAME_KEYS if isinstance(data.get(k), str) and data[k]), None)
    if name is None:
        name = Path(path).stem
    app_id = next((str(data[k]) for k in APP_ID_KEYS if data.get(k) is not None), None)
    game = GAMES_BY_APP_ID.get(app_id, default_game)

    points = []
    for entry in data["prices"]:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        when = parse_steam_date(entry[0])
        cents = to_cents(entry[1])
        volume = int(str(entry[2]).replace(",", "") or 0)
        points.append((when, cents, volume))
    points.sort(key=lambda p: p[0])
    return name, game, points


# ------------------------------------------------------------------ shaping
def to_daily(points):
    """
    Hourly points (the last month) -> one point per day, so the chart has
    one point per day everywhere. Price is the volume-weighted average of
    that day's medians, in cents; volume is the day's total.
    """
    days = OrderedDict()
    for when, cents, volume in points:
        days.setdefault(when.date().isoformat(), []).append((cents, volume))

    daily = []
    for day, entries in days.items():
        sold = sum(v for _, v in entries)
        if sold > 0:
            weighted = sum(Decimal(c) * v for c, v in entries) / sold
        else:
            weighted = sum(Decimal(c) for c, _ in entries) / len(entries)
        daily.append([day, to_cents(weighted / 100), sold])
    return daily


def site_filename(name):
    """Safe, unique file name for an item. Names contain | and ★, which files can't."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "item"
    return f"{slug}-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]}.json"


# ------------------------------------------------------------------ output
def convert(inputs, site_dir=None, csv_path=None, default_game="cs2"):
    files = []
    for p in inputs:
        p = Path(p)
        files.extend(sorted(p.rglob("*.json")) if p.is_dir() else [p])

    index, skipped, total_points = [], [], 0
    writer, csv_file = None, None
    if csv_path:
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
    if site_dir:
        os.makedirs(Path(site_dir) / "history", exist_ok=True)

    try:
        for path in files:
            if path.name == "index.json":
                continue
            parsed = read_history_file(path, default_game)
            if parsed is None or not parsed[2]:
                skipped.append(str(path))
                continue
            name, game, points = parsed
            total_points += len(points)

            if writer:
                for when, cents, volume in points:
                    writer.writerow({
                        "item_name": name,
                        "game": game,
                        "timestamp": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "median_price_minor": cents,
                        "volume_sold": volume,
                        "source": "steam",
                    })

            if site_dir:
                daily = to_daily(points)
                filename = site_filename(name)
                payload = {"item_name": name, "game": game, "source": "steam", "points": daily}
                with open(Path(site_dir) / "history" / filename, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
                index.append({
                    "item_name": name,
                    "game": game,
                    "file": filename,
                    "days": len(daily),
                    "first": daily[0][0],
                    "last": daily[-1][0],
                })
    finally:
        if csv_file:
            csv_file.close()

    if site_dir:
        index.sort(key=lambda e: e["item_name"].lower())
        with open(Path(site_dir) / "history" / "index.json", "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "items": index,
            }, f, ensure_ascii=False, indent=1)

    return {"items": len(index) if site_dir else len(files) - len(skipped),
            "points": total_points, "skipped": skipped}


def main(argv=None):
    p = argparse.ArgumentParser(description="Convert saved Steam price history files.")
    p.add_argument("--in", dest="inputs", nargs="+", required=True, help="files or folders")
    p.add_argument("--site", help="folder for the website data (frontend/public/data)")
    p.add_argument("--csv", help="write every raw point here for the database")
    p.add_argument("--game", default="cs2", help="game when a file doesn't say (cs2 or dota2)")
    args = p.parse_args(argv)
    if not args.site and not args.csv:
        p.error("give --site, --csv, or both")

    result = convert(args.inputs, args.site, args.csv, args.game)
    print(f"items:   {result['items']:,}")
    print(f"points:  {result['points']:,}")
    if result["skipped"]:
        print(f"skipped: {len(result['skipped'])} files that weren't price history")
    if args.site:
        print(f"site:    {Path(args.site) / 'history' / 'index.json'}")
    if args.csv:
        print(f"csv:     {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
