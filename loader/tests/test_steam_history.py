"""
Tests for the Steam history converter.

steam_history_sample.json is a made-up file in Steam's price history format:
three daily points from 2014 and four hourly points from October 2026.
"""

import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import steam_history as sh  # noqa: E402

SAMPLE = Path(__file__).with_name("steam_history_sample.json")


def test_steam_dates_parse_as_utc():
    assert sh.parse_steam_date("Aug 14 2014 01: +0") == datetime(2014, 8, 14, 1, tzinfo=timezone.utc)
    assert sh.parse_steam_date("Oct 5 2026 13: +0") == datetime(2026, 10, 5, 13, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        sh.parse_steam_date("2014-08-14")


def test_reads_name_game_and_exact_cents():
    name, game, points = sh.read_history_file(SAMPLE)
    assert name == "AK-47 | Sample Skin (Field-Tested)"
    assert game == "cs2"
    assert len(points) == 7
    cents = [c for _, c, _ in points]
    assert cents[:3] == [327, 311, 29]  # 3.271 -> 327, 3.105 -> 311, 0.29 -> 29
    assert [v for _, _, v in points][:3] == [420, 388, 12]


def test_name_falls_back_to_file_name(tmp_path):
    raw = json.loads(SAMPLE.read_text())
    del raw["market_hash_name"]
    path = tmp_path / "Some Item.json"
    path.write_text(json.dumps(raw))
    name, _, _ = sh.read_history_file(path)
    assert name == "Some Item"


def test_hourly_points_become_one_point_per_day():
    _, _, points = sh.read_history_file(SAMPLE)
    daily = sh.to_daily(points)
    assert [d[0] for d in daily] == ["2014-08-14", "2014-08-15", "2014-08-16", "2026-10-25", "2026-10-26"]
    # Oct 25: (1240*10 + 1260*30 + 1300*0) / 40 = 1255 cents, 40 sold
    assert daily[3] == ["2026-10-25", 1255, 40]
    assert daily[4] == ["2026-10-26", 1111, 5]


def test_non_history_files_are_skipped(tmp_path):
    (tmp_path / "notes.json").write_text('{"hello": "world"}')
    (tmp_path / "broken.json").write_text("{not json")
    shutil.copy(SAMPLE, tmp_path / "item.json")
    result = sh.convert([tmp_path], site_dir=tmp_path / "site")
    assert result["items"] == 1
    assert len(result["skipped"]) == 2


def test_command_line_writes_site_files_and_csv(tmp_path):
    site, rows = tmp_path / "data", tmp_path / "steam_rows.csv"
    assert sh.main(["--in", str(SAMPLE), "--site", str(site), "--csv", str(rows)]) == 0

    index = json.loads((site / "history" / "index.json").read_text())
    entry = index["items"][0]
    assert entry["item_name"] == "AK-47 | Sample Skin (Field-Tested)"
    assert entry["days"] == 5 and entry["first"] == "2014-08-14" and entry["last"] == "2026-10-26"
    assert "|" not in entry["file"]

    item = json.loads((site / "history" / entry["file"]).read_text())
    assert item["source"] == "steam" and len(item["points"]) == 5

    with open(rows, newline="") as f:
        table = list(csv.DictReader(f))
    assert len(table) == 7  # every raw point, not the daily version
    assert table[0]["timestamp"] == "2014-08-14T01:00:00Z"
    assert table[0]["median_price_minor"] == "327"


def test_file_names_are_safe_and_unique():
    a = sh.site_filename("AK-47 | Redline (Field-Tested)")
    b = sh.site_filename("StatTrak™ AK-47 | Redline (Field-Tested)")
    c = sh.site_filename("★ Karambit | Doppler (Factory New)")
    assert a != b
    for name in (a, b, c):
        assert name.endswith(".json") and "|" not in name and "★" not in name
