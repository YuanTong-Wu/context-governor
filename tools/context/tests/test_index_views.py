#!/usr/bin/env python3
"""Verify startup-safe index views are bounded."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from test_common import assert_true, read_json, run_cmd


VIEWS = ["FILE_INDEX_VIEW.csv", "RUNNER_INDEX_VIEW.csv", "CASE_INDEX_VIEW.csv", "EVIDENCE_INDEX_VIEW.csv", "GAP_INDEX_VIEW.csv"]


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return len(list(csv.DictReader(handle)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    run_cmd(["python3", "tools/context/build_index_views.py", "--root", str(root)], root)
    budget = read_json(root / "context/budgets/GLOBAL_CONTEXT_BUDGET.json")
    max_rows = int(budget["index_view_max_rows"])
    max_chars = int(budget["index_view_max_chars"])
    for name in VIEWS:
        path = root / "context/indexes/views" / name
        assert_true(path.exists(), f"view missing: {name}")
        assert_true(csv_rows(path) <= max_rows, f"view too many rows: {name}")
        assert_true(len(path.read_text(encoding="utf-8", errors="replace")) <= max_chars, f"view too many chars: {name}")
    assert_true((root / "context/indexes/views/INDEX_VIEW_MANIFEST.csv").exists(), "view manifest missing")
    assert_true((root / "context/indexes/views/INDEX_SHARD_MANIFEST.csv").exists(), "shard manifest missing")
    print("index views test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

