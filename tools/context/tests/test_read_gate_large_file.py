#!/usr/bin/env python3
"""Verify read gate blocks unbounded large reads and holdout-like paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from test_common import assert_true, run_cmd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    large = root / "var/context_governor_2026_06_24/audit/test_large_file.txt"
    holdout = root / "var/context_governor_2026_06_24/audit/holdout_test.txt"
    large.parent.mkdir(parents=True, exist_ok=True)
    large.write_text("x" * 31000, encoding="utf-8")
    holdout.write_text("sealed", encoding="utf-8")
    try:
        denied = run_cmd(["python3", "tools/context/read_gate/read_context_file.py", str(large), "--root", str(root)], root, expect=None)
        assert_true(denied.returncode != 0 and "LARGE_FILE_REQUIRES_REASON" in denied.stdout, "large read without reason should be denied")
        allowed = run_cmd(
            [
                "python3",
                "tools/context/read_gate/read_context_file.py",
                str(large),
                "--root",
                str(root),
                "--reason",
                "bounded test read",
                "--max-chars",
                "1000",
            ],
            root,
        )
        body = json.loads(allowed.stdout)
        assert_true(body.get("allowed") is True, "bounded large read should be allowed")
        assert_true(len(body.get("content", "")) <= 1000, "bounded large read returned too much content")
        blocked = run_cmd(["python3", "tools/context/read_gate/read_context_file.py", str(holdout), "--root", str(root), "--reason", "test", "--max-chars", "10"], root, expect=None)
        assert_true(blocked.returncode != 0 and "HOLDOUT_CONTENT_READ_DENIED" in blocked.stdout, "holdout-like read should be denied")
    finally:
        large.unlink(missing_ok=True)
        holdout.unlink(missing_ok=True)
    print("read gate large file test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

