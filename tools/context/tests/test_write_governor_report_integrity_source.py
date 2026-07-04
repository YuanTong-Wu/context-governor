#!/usr/bin/env python3
import csv
from pathlib import Path

from test_common import assert_true, read_json, run_cmd


def rows_by_check(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["check_id"]: row for row in csv.DictReader(handle)}


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    run_cmd(["python3", "tools/context/context_integrity_check.py", "--root", str(root)], root, timeout=120)
    run_cmd(["python3", "tools/context/write_final_report.py", "--root", str(root)], root, timeout=120)
    run_cmd(
        [
            "python3",
            "tools/context/write_governor_report.py",
            "--root",
            str(root),
            "--project-id",
            "default",
        ],
        root,
        expect=None,
        timeout=120,
    )

    checks = rows_by_check(root / "var/context_governor_2026_06_24/audit/governor_final_checks.csv")
    integrity = checks["context_integrity_non_blocking"]
    microkernel = checks["context_microkernel_final_verdict_written"]
    audit = read_json(root / "var/context_control_2026_06_23/audit/context_integrity_verdict.json")

    assert_true(
        integrity.get("path") == "var/context_control_2026_06_23/audit/context_integrity_verdict.json",
        "governor should read integrity verdict from audit path",
    )
    assert_true("audit/context_integrity_verdict.json" in integrity.get("notes", ""), "integrity notes should name audit source")
    assert_true(integrity.get("observed") == audit.get("verdict"), "governor should report audit integrity verdict")
    assert_true(
        microkernel.get("path") == "var/context_control_2026_06_23/verdict.json",
        "microkernel final verdict should remain a separate source",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
