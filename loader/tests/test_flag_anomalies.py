"""Tests for anomaly detection v1 (flag_anomalies.py). The price series are made up."""

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flag_anomalies as fa  # noqa: E402

START = date(2026, 8, 1)


def series(n=60, base=1000, wiggle=0.01, sold=50, seed=1):
    """n days of a price that drifts by about +/- wiggle per day."""
    rng = random.Random(seed)
    price, points = base, []
    for i in range(n):
        price = max(1, round(price * (1 + rng.uniform(-wiggle, wiggle))))
        points.append([(START + timedelta(days=i)).isoformat(), price, sold])
    return points


def day(i):
    return (START + timedelta(days=i)).isoformat()


def test_quiet_item_has_no_flags():
    flags, scored = fa.score_item(series())
    assert flags == []
    assert len(scored) > 0


def test_spike_is_flagged_with_its_day_and_size():
    points = series()
    points[45][1] = round(points[44][1] * 1.30)  # +30% in one day
    flags, _ = fa.score_item(points)
    assert flags[0]["date"] == day(45)
    assert flags[0]["z"] > 3
    assert flags[0]["change_pct"] == 30.0


def test_drop_is_flagged_with_a_negative_score():
    points = series()
    points[50][1] = round(points[49][1] * 0.75)
    flags, _ = fa.score_item(points)
    assert flags[0]["date"] == day(50) and flags[0]["z"] < -3


def test_thin_day_is_ignored():
    points = series()
    points[45][1] = points[44][1] * 3
    points[45][2] = 1  # one sale: not trusted
    flags, _ = fa.score_item(points)
    assert all(f["date"] != day(45) for f in flags)


def test_needs_enough_history_before_scoring():
    points = series(n=15)
    points[10][1] *= 3
    flags, scored = fa.score_item(points)
    assert flags == [] and scored == []


def test_flat_price_is_not_scored():
    points = [[day(i), 500, 20] for i in range(40)]
    assert fa.score_item(points) == ([], [])


def test_nearest_update_only_counts_updates_on_or_before_the_flag():
    events = [{"date": day(40), "label": "Case drop", "type": "case"},
              {"date": day(46), "label": "Later patch", "type": "minor"}]
    assert fa.nearest_update(day(42), events)["label"] == "Case drop"
    assert fa.nearest_update(day(42), events)["days_after"] == 2
    assert fa.nearest_update(day(44), events) is None  # 4 days later is too far
    assert fa.nearest_update(day(39), events) is None  # before any update


def write_site(tmp_path, items, events):
    folder = tmp_path / "csgo2"
    (folder / "history").mkdir(parents=True)
    index = []
    for i, (name, points) in enumerate(items):
        f = f"f{i}.json"
        (folder / "history" / f).write_text(json.dumps({"item_name": name, "game": "cs2", "source": "steam", "points": points}))
        index.append({"item_name": name, "game": "cs2", "file": f})
    (folder / "history" / "index.json").write_text(json.dumps({"items": index}))
    (folder / "events.json").write_text(json.dumps(events))
    return tmp_path


def test_run_writes_flags_matched_to_updates_and_a_summary(tmp_path):
    spiky = series(seed=2)
    spiky[45][1] = round(spiky[44][1] * 1.4)
    site = write_site(tmp_path, [("Quiet", series(seed=3)), ("Spiky", spiky)],
                      [{"date": day(44), "label": "Case drop", "type": "case"}])
    assert fa.main(["--site", str(site)]) == 0
    out = json.loads((site / "csgo2" / "anomalies.json").read_text())
    top = out["flags"][0]
    assert top["item_name"] == "Spiky" and top["update"]["label"] == "Case drop"
    s = out["summary"]
    assert s["items"] == 2 and s["flags"] >= 1 and s["flags_near_update"] >= 1
    assert 0 < s["share_days_near_update"] < 1
    assert s["ratio"] > 1


def test_game_without_history_is_skipped(tmp_path):
    assert fa.run_game(tmp_path, "dota2") is None
    assert fa.main(["--site", str(tmp_path)]) == 1
