"""
Anomaly detection v1: flag unusual daily price moves and line them up with game updates.

For every item in the website history files, this looks at each day's price change
(today's median sale price vs. the day before). It compares that change with the
item's own last 30 days of changes:

    z = (today's change - average change over the last 30 days) / spread of those changes

A z-score past 3 means the move was more than three times bigger than the item's
normal day-to-day wiggle. Those days get flagged. Days with very few sales are
skipped, because one odd sale can move the median a lot.

Each flag is then matched to the nearest game update from events.json (written by
build_events.py) that went live on the same day or up to 3 days before it.

Output, one file per game, read by the Price Movements page:

    <site>/csgo2/anomalies.json
    <site>/dota2/anomalies.json

The summary in each file also answers a first version of the research question:
what share of flags land near an update, compared with the share of all trading
days that land near an update. A ratio above 1 means flags bunch up after updates.

Usage:
    python loader/build_events.py --csv timeline/update_events.csv --site frontend/public/data
    python loader/flag_anomalies.py --site frontend/public/data
"""

import argparse
import json
import math
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

FOLDERS = {"cs2": "csgo2", "dota2": "dota2"}
WINDOW = 30  # days of history used as "normal" for each item
MIN_HISTORY = 20  # need at least this many prior changes before scoring a day
THRESHOLD = 3.0  # flag when |z| is at or past this
MIN_SOLD = 5  # skip days with fewer sales than this
AFTER_UPDATE = 3  # a flag up to this many days after an update counts as "near" it


def daily_changes(points, min_sold=MIN_SOLD):
    """[[day, cents, sold], ...] -> [(day, prev_cents, cents, sold, log_change)].

    Only days with enough sales are used, and the change is measured from the
    previous day that also had enough sales. Log change is used so a 10% move
    counts the same on a $1 item and a $1,000 item.
    """
    rows = []
    prev = None
    for day, cents, sold in points:
        if not cents or cents <= 0 or (sold or 0) < min_sold:
            continue
        if prev is not None:
            rows.append((day, prev, cents, sold, math.log(cents / prev)))
        prev = cents
    return rows


def score_item(points, window=WINDOW, threshold=THRESHOLD, min_sold=MIN_SOLD):
    """Returns (flags, days_scored). Each flag is a dict with the day, prices and z-score."""
    changes = daily_changes(points, min_sold)
    flags = []
    scored = []
    for i, (day, prev_cents, cents, sold, change) in enumerate(changes):
        history = [c[4] for c in changes[max(0, i - window):i]]
        if len(history) < MIN_HISTORY:
            continue
        spread = statistics.pstdev(history)
        if spread < 1e-4:  # price barely moves at all; any tick would look huge
            continue
        z = (change - statistics.fmean(history)) / spread
        scored.append(day)
        if abs(z) >= threshold:
            flags.append({
                "date": day,
                "before": prev_cents,
                "price": cents,
                "change_pct": round((cents - prev_cents) / prev_cents * 100, 1),
                "z": round(z, 2),
                "sold": sold,
            })
    return flags, scored


def nearest_update(day, events, after=AFTER_UPDATE):
    """The latest update that went live on `day` or up to `after` days before it, or None."""
    d = date.fromisoformat(day)
    best = None
    for e in events:
        gap = (d - date.fromisoformat(e["date"])).days
        if 0 <= gap <= after and (best is None or gap < best[0]):
            best = (gap, e)
    if best is None:
        return None
    gap, e = best
    return {"date": e["date"], "label": e["label"], "type": e.get("type", ""), "days_after": gap}


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run_game(site, game, window=WINDOW, threshold=THRESHOLD, min_sold=MIN_SOLD):
    """Scores every item of one game. Returns the anomalies.json content, or None if no history."""
    folder = Path(site) / FOLDERS[game]
    index = load_json(folder / "history" / "index.json")
    if not index or not index.get("items"):
        return None
    events = load_json(folder / "events.json") or []

    flags = []
    days_scored = 0
    days_near_update = 0
    for entry in index["items"]:
        if entry.get("game", game) != game:
            continue
        hist = load_json(folder / "history" / entry["file"])
        if not hist or not isinstance(hist.get("points"), list):
            continue
        item_flags, scored = score_item(hist["points"], window, threshold, min_sold)
        days_scored += len(scored)
        days_near_update += sum(1 for d in scored if nearest_update(d, events))
        for f in item_flags:
            f["item_name"] = entry["item_name"]
            f["file"] = entry["file"]
            f["update"] = nearest_update(f["date"], events)
            flags.append(f)

    flags.sort(key=lambda f: (-abs(f["z"]), f["date"]))
    near = sum(1 for f in flags if f["update"])
    share_flags = near / len(flags) if flags else 0.0
    share_days = days_near_update / days_scored if days_scored else 0.0
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": {"window_days": window, "threshold": threshold, "min_sold": min_sold, "after_update_days": AFTER_UPDATE},
        "summary": {
            "items": len(index["items"]),
            "days_scored": days_scored,
            "flags": len(flags),
            "flags_near_update": near,
            "share_flags_near_update": round(share_flags, 3),
            "share_days_near_update": round(share_days, 3),
            # How many times more often flags land near updates than ordinary days do.
            "ratio": round(share_flags / share_days, 2) if share_days else None,
        },
        "flags": flags,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", type=Path, required=True, help="website data folder, e.g. frontend/public/data")
    parser.add_argument("--window", type=int, default=WINDOW)
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    parser.add_argument("--min-sold", type=int, default=MIN_SOLD)
    parser.add_argument("--top", type=int, default=10, help="how many flags to print per game")
    args = parser.parse_args(argv)

    wrote = 0
    for game in FOLDERS:
        result = run_game(args.site, game, args.window, args.threshold, args.min_sold)
        if result is None:
            print(f"{game}: no history files, skipped")
            continue
        out = args.site / FOLDERS[game] / "anomalies.json"
        out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        wrote += 1
        s = result["summary"]
        print(f"\n{game}: {s['items']} items, {s['days_scored']} days scored, {s['flags']} flags")
        print(f"  near an update: {s['flags_near_update']} flags ({s['share_flags_near_update']:.0%})"
              f" vs {s['share_days_near_update']:.0%} of all days, ratio {s['ratio']}")
        for f in result["flags"][:args.top]:
            upd = f"after {f['update']['label']} (+{f['update']['days_after']}d)" if f["update"] else "no update nearby"
            print(f"  {f['date']}  z={f['z']:+6.2f}  {f['change_pct']:+6.1f}%  {f['item_name']}  [{upd}]")
    return 0 if wrote else 1


if __name__ == "__main__":
    sys.exit(main())
