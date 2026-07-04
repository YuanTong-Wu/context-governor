#!/usr/bin/env python3
"""Verify full indexes are accessed through query script."""

from __future__ import annotations

import argparse
from pathlib import Path

from test_common import assert_true, run_cmd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    proc = run_cmd(
        [
            "python3",
            "tools/context/query_index.py",
            "--root",
            str(root),
            "--index",
            "file",
            "--project",
            "default",
            "--path-contains",
            "tools/context",
            "--limit",
            "5",
        ],
        root,
    )
    assert_true("path" in proc.stdout.splitlines()[0], "query output missing path header")
    assert_true((root / "context/read_logs/INDEX_QUERY_LOG.jsonl").exists(), "index query log missing")
    print("query index test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

