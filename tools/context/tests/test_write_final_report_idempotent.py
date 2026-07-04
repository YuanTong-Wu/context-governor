#!/usr/bin/env python3
from pathlib import Path

from test_common import assert_true, read_json, run_cmd


def stable_summary(root: Path) -> tuple[object, object, object, object]:
    summary = read_json(root / "var/context_control_2026_06_23/summary.json")
    return (
        summary.get("final_verdict"),
        summary.get("integrity_verdict"),
        summary.get("integrity_source_path"),
        summary.get("hard_blocker"),
    )


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    run_cmd(["python3", "tools/context/context_integrity_check.py", "--root", str(root)], root, timeout=120)

    run_cmd(["python3", "tools/context/write_final_report.py", "--root", str(root)], root, timeout=120)
    first = stable_summary(root)
    run_cmd(["python3", "tools/context/write_final_report.py", "--root", str(root)], root, timeout=120)
    second = stable_summary(root)

    assert_true(first == second, "write_final_report should be idempotent for stable fields")
    assert_true(first[2] == "var/context_control_2026_06_23/audit/context_integrity_verdict.json", "integrity source should be audit verdict")
    assert_true(str(first[1]).startswith("CONTEXT_INTEGRITY_"), "integrity verdict should come from integrity audit")
    assert_true(first[3] is False, "final report should not introduce hard blocker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
