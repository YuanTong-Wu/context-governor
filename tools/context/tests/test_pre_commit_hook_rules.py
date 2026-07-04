#!/usr/bin/env python3
"""Verify hook/local checks cover the required governor rules."""

from __future__ import annotations

import argparse
from pathlib import Path

from test_common import assert_true, run_cmd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    hook = root / "tools/context/hooks/pre_commit_context_check.sh"
    installer = root / "tools/context/hooks/install_context_hooks.sh"
    local = root / "tools/context/check_before_change.sh"
    for path in [hook, installer, local]:
        assert_true(path.exists(), f"missing hook/check script: {path}")
    hook_text = hook.read_text(encoding="utf-8")
    for token in ["context_integrity_check.py", "recursive_entry_detector.py", "startup_budget_test.py", "holdout"]:
        assert_true(token in hook_text, f"pre-commit hook missing rule token: {token}")
    preflight = run_cmd(
        [
            "python3",
            "tools/dev/preflight_change.py",
            "--root",
            str(root),
            "--changed-file",
            "context/SYSTEM_INVARIANTS.json",
            "--changed-file",
            "context/schemas/demo.json",
        ],
        root,
    )
    assert_true("RISK" in preflight.stdout or (root / "var/dev_change_control_2026_06_24/preflight_change_summary.json").exists(), "preflight did not run")
    print("pre-commit hook rules test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
