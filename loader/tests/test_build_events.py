"""Tests for the update timeline converter (build_events.py). The rows are made up."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_events as be  # noqa: E402

HEADER = "date,game,title,type,link\n"


def write(tmp_path, body):
    p = tmp_path / "events.csv"
    p.write_text(HEADER + body, encoding="utf-8")
    return p


def test_splits_by_game_and_sorts_by_date(tmp_path):
    csv_path = write(tmp_path, (
        "2026-10-20,cs2,Second update,minor,https://example.com/b\n"
        "2026-10-01,CS2,First update,case,https://example.com/a\n"
        "2026-10-05,dota2,Balance patch,balance,https://example.com/c\n"
    ))
    counts = be.write_site(be.read_events(csv_path), tmp_path / "site")
    assert counts == {"cs2": 2, "dota2": 1}
    cs2 = json.loads((tmp_path / "site" / "csgo2" / "events.json").read_text())
    assert [e["date"] for e in cs2] == ["2026-10-01", "2026-10-20"]
    assert cs2[0] == {"date": "2026-10-01", "label": "First update", "type": "case", "link": "https://example.com/a"}
    dota = json.loads((tmp_path / "site" / "dota2" / "events.json").read_text())
    assert dota[0]["label"] == "Balance patch"


@pytest.mark.parametrize("row, message", [
    ("10/01/2026,cs2,X,minor,https://e.com\n", "date"),
    ("2026-10-01,tf2,X,minor,https://e.com\n", "game"),
    ("2026-10-01,cs2,,minor,https://e.com\n", "title"),
    ("2026-10-01,cs2,X,huge,https://e.com\n", "type"),
    ("2026-10-01,cs2,X,minor,see discord\n", "link"),
])
def test_bad_rows_name_the_line(tmp_path, row, message):
    with pytest.raises(ValueError, match=rf"line 2: {message}"):
        be.read_events(write(tmp_path, row))


def test_empty_csv_writes_empty_files(tmp_path):
    assert be.main(["--csv", str(write(tmp_path, "")), "--site", str(tmp_path / "site")]) == 0
    assert json.loads((tmp_path / "site" / "csgo2" / "events.json").read_text()) == []
