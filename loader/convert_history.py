"""
Steam history converter: turns Jerome's downloaded Steam price history
into data for the website and rows for the database.

It reads any of these:
  - Jerome's downloader database, backend/db/steam_history.db
    (table history_items, one saved Steam response per item)
  - his offline export, from  python backend/steam_history.py --export FILE.jsonl
    (one line per item: appid, market_hash_name, response)
  - a single saved Steam response, one .json file per item

A Steam price history response looks like this:

    {"success": true, "price_prefix": "$", "price_suffix": "",
     "prices": [["Aug 14 2014 01: +0", 3.271, "420"], ...]}

Each point is [date, median sale price, number sold]. Older points are one
per day; the last month is one per hour. Steam reports prices in the
account's wallet currency, so anything that isn't US dollars is skipped.

These are SALES (what items sold for), not listings (what sellers ask).
They go in their own table, not in price_observations.lowest_price_minor.

Outputs:
  --site DIR   DIR/history/index.json plus one small file per item, with
               one point per day, for the item page charts
  --csv FILE   every raw point, for the database

Usage:
  python convert_history.py --in ../backend/db/steam_history.db --site ../frontend/public/data --csv steam_rows.csv
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from load_snapshot import GAMES_BY_APP_ID, to_cents

CSV_COLUMNS = ["item_name", "game", "timestamp", "median_price_minor", "volume_sold", "source"]
NAME_KEYS = ("market_hash_name", "name", "item_name", "hash_name", "item")
APP_ID_KEYS = ("appid", "app_id", "appId")
DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")
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


def is_usd(response):
    """Steam marks the currency with a prefix and suffix. US dollars is '$' and ''."""
    prefix = str(response.get("price_prefix", "$")).strip()
    suffix = str(response.get("price_suffix", "")).strip()
    return prefix == "$" and suffix in ("", "USD")


def parse_record(data, fallback_name, default_game="cs2"):
    """
    One item's data -> ((item_name, game, points), None) or (None, reason).
    Accepts a raw Steam response, or a wrapper with the response under "response".
    points: list of (datetime, cents, volume), oldest first.
    """
    if isinstance(data, list):  # just the prices array
        data = {"prices": data}
    if not isinstance(data, dict):
        return None, "not price history"
    response = data["response"] if isinstance(data.get("response"), dict) else data
    if not isinstance(response.get("prices"), list):
        return None, "not price history"
    if not is_usd(response):
        return None, "not US dollars"

    def first(keys, kind):
        for source in (data, response):
            for k in keys:
                if isinstance(source.get(k), kind) and source.get(k) != "":
                    return source[k]
        return None

    name = first(NAME_KEYS, str) or fallback_name
    app_id = first(APP_ID_KEYS, (int, str))
    game = GAMES_BY_APP_ID.get(str(app_id), default_game) if app_id is not None else default_game

    points = []
    for entry in response["prices"]:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        when = parse_steam_date(entry[0])
        cents = to_cents(entry[1])
        volume = int(str(entry[2]).replace(",", "") or 0)
        points.append((when, cents, volume))
    if not points:
        return None, "no price points"
    points.sort(key=lambda p: p[0])
    return (name, game, points), None


def iter_records(path):
    """
    Yield (where, data, fallback_name) for every item in a file.
    where: a label for error messages. data is None when the file can't be read.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in DB_SUFFIXES:
        try:
            conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        except sqlite3.Error:
            yield str(path), None, None
            return
        try:
            rows = conn.execute(
                "SELECT appid, market_hash_name, response_json FROM history_items "
                "WHERE response_json IS NOT NULL ORDER BY appid, market_hash_name"
            )
            for appid, name, raw in rows:
                try:
                    response = json.loads(raw, parse_float=Decimal)
                except ValueError:
                    yield f"{path}: {name}", None, name
                    continue
                yield f"{path}: {name}", {"appid": appid, "market_hash_name": name, "response": response}, name
        except sqlite3.Error:
            yield str(path), None, None  # not Jerome's downloader database
        finally:
            conn.close()
        return

    if suffix == ".jsonl":
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    yield f"{path}:{n}", json.loads(line, parse_float=Decimal), None
                except ValueError:
                    yield f"{path}:{n}", None, None
        return

    try:
        with open(path, "rb") as f:
            yield str(path), json.loads(f.read(), parse_float=Decimal), path.stem
    except ValueError:
        yield str(path), None, path.stem


def read_history_file(path, default_game="cs2"):
    """First item in a file -> (item_name, game, points), or None."""
    for _, data, fallback in iter_records(path):
        if data is None:
            return None
        parsed, _ = parse_record(data, fallback or Path(path).stem, default_game)
        return parsed
    return None


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
def collect_files(inputs):
    files = []
    for p in inputs:
        p = Path(p)
        if p.is_dir():
            for pattern in ("*.json", "*.jsonl", *(f"*{s}" for s in DB_SUFFIXES)):
                files.extend(p.rglob(pattern))
        else:
            files.append(p)
    return sorted({f for f in files if f.name != "index.json"})


def convert(inputs, site_dir=None, csv_path=None, default_game="cs2"):
    index, skipped, total_points, seen = [], [], 0, set()
    writer, csv_file = None, None
    if csv_path:
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
    if site_dir:
        os.makedirs(Path(site_dir) / "history", exist_ok=True)

    try:
        for path in collect_files(inputs):
            for where, data, fallback in iter_records(path):
                if data is None:
                    skipped.append((where, "could not read"))
                    continue
                parsed, reason = parse_record(data, fallback or Path(path).stem, default_game)
                if parsed is None:
                    skipped.append((where, reason))
                    continue
                name, game, points = parsed
                if (game, name) in seen:
                    skipped.append((where, "duplicate item"))
                    continue
                seen.add((game, name))
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

    return {"items": len(seen), "points": total_points, "skipped": skipped}


def main(argv=None):
    p = argparse.ArgumentParser(description="Convert downloaded Steam price history.")
    p.add_argument("--in", dest="inputs", nargs="+", required=True,
                   help="steam_history.db, an export .jsonl, .json files, or folders")
    p.add_argument("--site", help="folder for the website data (frontend/public/data)")
    p.add_argument("--csv", help="write every raw point here for the database")
    p.add_argument("--game", default="cs2", help="game when the data doesn't say (cs2 or dota2)")
    args = p.parse_args(argv)
    if not args.site and not args.csv:
        p.error("give --site, --csv, or both")

    result = convert(args.inputs, args.site, args.csv, args.game)
    print(f"items:   {result['items']:,}")
    print(f"points:  {result['points']:,}")
    if result["skipped"]:
        reasons = {}
        for _, why in result["skipped"]:
            reasons[why] = reasons.get(why, 0) + 1
        print("skipped: " + ", ".join(f"{n} {why}" for why, n in reasons.items()))
    if args.site:
        print(f"site:    {Path(args.site) / 'history' / 'index.json'}")
    if args.csv:
        print(f"csv:     {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
