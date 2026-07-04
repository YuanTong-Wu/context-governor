#!/usr/bin/env python3
"""Verify recursive entry detector catches non-allowlisted startup variants."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from test_common import assert_true, run_cmd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    repo = Path(args.root).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="context-governor-recursive-") as tmp:
        tmp_root = Path(tmp)
        (tmp_root / "context").mkdir(parents=True, exist_ok=True)
        (tmp_root / "BOOT_FOR_BOOT.md").write_text("# recursive entry\n", encoding="utf-8")
        (tmp_root / "context/RECURSIVE_ENTRY_ALLOWLIST.json").write_text('{"allowed_paths":[]}\n', encoding="utf-8")
        proc = run_cmd(["python3", str(repo / "tools/context/recursive_entry_detector.py"), "--root", str(tmp_root)], repo, expect=None)
        assert_true(proc.returncode != 0, "recursive entry detector should fail fixture")
        assert_true((tmp_root / "var/context_governor_2026_06_24/audit/recursive_entry_scan.csv").exists(), "recursive scan missing")
    print("recursive entry detector test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

