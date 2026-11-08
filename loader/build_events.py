"""
Update timeline -> chart markers.

Reads timeline/update_events.csv (one row per game update, filled in by hand from
the official patch notes) and writes the events.json files the item charts read:

    <site>/events.json         CS2 updates
    <site>/dota2/events.json   Dota 2 updates

CSV columns:
    date   2026-10-01 (the day the update went live, UTC)
    game   cs2 or dota2
    title  short name shown on the chart, e.g. "Operation release"
    type   major, case, operation, balance, or minor (used later by the correlation study)
    link   URL of the patch notes, so every row can be checked

Usage:
    python loader/build_events.py --csv timeline/update_events.csv --site frontend/public/data
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

GAMES = ("cs2", "dota2")
TYPES = ("major", "case", "operation", "balance", "minor")


def read_events(csv_path):
    """CSV rows -> list of clean dicts. Raises ValueError naming the bad line."""
    events = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = {"date", "game", "title", "type", "link"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, start=2):
            day = (row["date"] or "").strip()
            game = (row["game"] or "").strip().lower()
            title = (row["title"] or "").strip()
            kind = (row["type"] or "").strip().lower()
            link = (row["link"] or "").strip()
            try:
                date.fromisoformat(day)
            except ValueError:
                raise ValueError(f"line {line}: date must look like 2026-10-01, got {day!r}") from None
            if game not in GAMES:
                raise ValueError(f"line {line}: game must be cs2 or dota2, got {game!r}")
            if not title:
                raise ValueError(f"line {line}: title is empty")
            if kind not in TYPES:
                raise ValueError(f"line {line}: type must be one of {', '.join(TYPES)}, got {kind!r}")
            if not link.startswith("http"):
                raise ValueError(f"line {line}: link should be the patch notes URL")
            events.append({"date": day, "game": game, "label": title, "type": kind, "link": link})
    events.sort(key=lambda e: (e["date"], e["game"], e["label"]))
    return events


def write_site(events, site_dir):
    """Writes one events.json per game. Returns {game: count}."""
    counts = {}
    for game in GAMES:
        out = Path(site_dir) / ("events.json" if game == "cs2" else "dota2/events.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [{k: e[k] for k in ("date", "label", "type", "link")} for e in events if e["game"] == game]
        out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
        counts[game] = len(rows)
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, default=Path("timeline/update_events.csv"))
    parser.add_argument("--site", type=Path, required=True, help="website data folder, e.g. frontend/public/data")
    args = parser.parse_args(argv)
    try:
        events = read_events(args.csv)
    except ValueError as e:
        print(f"{args.csv}: {e}", file=sys.stderr)
        return 1
    counts = write_site(events, args.site)
    print(json.dumps({"events": len(events), **counts}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
