#!/usr/bin/env python3
from pathlib import Path

from test_common import assert_true, read_json, run_cmd


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    for _ in range(2):
        run_cmd(["bash", "tools/context/run_context_control_all.sh", "--root", str(root)], root, timeout=240)

    summary_path = root / "var/context_control_2026_06_23/summary.json"
    verdict_path = root / "var/context_control_2026_06_23/verdict.json"
    assert_true(summary_path.exists(), "summary.json should exist after repeated control runs")
    assert_true(verdict_path.exists(), "verdict.json should exist after repeated control runs")

    summary = read_json(summary_path)
    verdict = read_json(verdict_path)
    expected_source = "var/context_control_2026_06_23/audit/context_integrity_verdict.json"
    assert_true(summary.get("integrity_source_path") == expected_source, "summary should use audit integrity source")
    assert_true(verdict.get("integrity_source_path") == expected_source, "verdict should use audit integrity source")
    assert_true(verdict.get("hard_blocker") is False, "control verdict should not have hard blocker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
