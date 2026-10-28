"""
Tests for the snapshot loader.

sample_snapshot.json is a made-up snapshot in Skinport's exact format
(same fields, same types). It includes prices that break naive float
math and one item with no listings.
"""

import csv
import json
import os
import sys
from pathlib import Path

import brotli
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import load_snapshot as loader  # noqa: E402

SAMPLE = Path(__file__).with_name("sample_snapshot.json")
KEY = "cs2/2026/10/20/140012.json.br"


@pytest.fixture
def raw_br():
    """The sample, Brotli compressed, like the Lambda stores it."""
    return brotli.compress(SAMPLE.read_bytes())


def by_name(rows):
    return {r["item_name"]: r for r in rows}


def test_prices_become_exact_cents(raw_br):
    rows, _ = loader.snapshot_to_rows(raw_br, key=KEY)
    cents = {name: r["lowest_price_minor"] for name, r in by_name(rows).items()}
    assert cents == {
        "AK-47 | Redline (Field-Tested)": 1240,
        "Sticker | Sample Team (Holo)": 29,
        "MP9 | Storm (Minimal Wear)": 115,
        "P250 | Sand Dune (Field-Tested)": 3,
        "Karambit | Doppler (Factory New)": 110500,
    }


def test_float_math_would_get_cents_wrong():
    # The bug this loader avoids: plain float math loses a cent.
    assert int(0.29 * 100) == 28
    assert int(1.15 * 100) == 114
    # Exact decimals keep it.
    assert loader.to_cents(json.loads("0.29", parse_float=loader.Decimal)) == 29
    assert loader.to_cents(json.loads("1.15", parse_float=loader.Decimal)) == 115


def test_items_without_listings_are_skipped(raw_br):
    rows, skipped = loader.snapshot_to_rows(raw_br, key=KEY)
    assert skipped == 1
    assert "Souvenir Package Sample" not in by_name(rows)
    assert len(rows) == 5


def test_every_row_has_the_locked_shape(raw_br):
    rows, _ = loader.snapshot_to_rows(raw_br, key=KEY)
    for r in rows:
        assert list(r.keys()) == loader.COLUMNS
        assert isinstance(r["lowest_price_minor"], int)
        assert isinstance(r["listing_count"], int)
    assert by_name(rows)["AK-47 | Redline (Field-Tested)"]["listing_count"] == 1842


def test_time_and_game_come_from_the_key(raw_br):
    rows, _ = loader.snapshot_to_rows(raw_br, key=KEY)
    assert {r["timestamp"] for r in rows} == {"2026-10-20T14:00:12Z"}
    assert {r["game"] for r in rows} == {"cs2"}
    assert {r["source"] for r in rows} == {"skinport"}


def test_s3_metadata_wins_over_the_key(raw_br):
    meta = {"source": "skinport", "app_id": "570", "collected_at": "2026-10-20T10:00:12.531+00:00"}
    rows, _ = loader.snapshot_to_rows(raw_br, key=KEY, metadata=meta)
    assert {r["game"] for r in rows} == {"dota2"}
    assert {r["timestamp"] for r in rows} == {"2026-10-20T10:00:12Z"}


def test_plain_json_also_works():
    rows, skipped = loader.snapshot_to_rows(SAMPLE.read_bytes(), key=KEY)
    assert len(rows) == 5 and skipped == 1


def test_missing_timestamp_is_an_error(raw_br):
    with pytest.raises(ValueError):
        loader.snapshot_to_rows(raw_br, key="not-a-snapshot-key")


def test_command_line_writes_csv_and_json(raw_br, tmp_path):
    snap = tmp_path / "cs2_2026_10_20_140012.json.br"
    snap.write_bytes(raw_br)
    out_csv, out_json = tmp_path / "rows.csv", tmp_path / "site" / "latest.json"

    assert loader.main(["--file", str(snap), "--csv", str(out_csv), "--json", str(out_json)]) == 0

    with open(out_csv, newline="") as f:
        table = list(csv.DictReader(f))
    assert len(table) == 5
    assert table[0].keys() == set(loader.COLUMNS)

    payload = json.loads(out_json.read_text())
    assert payload["item_count"] == 5
    assert payload["skipped_no_listings"] == 1
    assert payload["collected_at"] == "2026-10-20T14:00:12Z"


def test_latest_key_picks_the_newest():
    class FakePaginator:
        def paginate(self, **_):
            yield {"Contents": [{"Key": "cs2/2026/10/19/230012.json.br"}]}
            yield {"Contents": [{"Key": "cs2/2026/10/20/140012.json.br"},
                                {"Key": "cs2/2026/10/20/090012.json.br"}]}

    class FakeS3:
        def get_paginator(self, _):
            return FakePaginator()

    assert loader.latest_key(FakeS3(), "bucket") == "cs2/2026/10/20/140012.json.br"
