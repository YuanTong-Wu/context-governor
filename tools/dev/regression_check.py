#!/usr/bin/env python3
"""Run lightweight local regressions for context-control changes."""

from __future__ import annotations

import subprocess

from dev_common import add_check, read_json, resolve_root, root_arg, write_check_outputs


def run_cmd(root, check_id: str, cmd: list[str], checks: list[dict[str, str]], severity: str = "HIGH") -> None:
    proc = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    observed = f"exit={proc.returncode}"
    notes = (proc.stdout + "\n" + proc.stderr).strip().splitlines()
    add_check(
        checks,
        check_id,
        "regression",
        "PASS" if proc.returncode == 0 else "FAIL",
        severity,
        " ".join(cmd),
        observed,
        "exit=0",
        notes[-1] if notes else "",
    )


def main() -> int:
    parser = root_arg()
    args = parser.parse_args()
    root = resolve_root(args.root)
    checks: list[dict[str, str]] = []

    run_cmd(root, "context_integrity", ["python3", "tools/context/context_integrity_check.py", "--root", str(root)], checks)
    run_cmd(root, "recursive_entry_detector", ["python3", "tools/context/recursive_entry_detector.py", "--root", str(root)], checks)

    bundle = root / "context/generated/startup_bundles/default_STARTUP_BUNDLE.md"
    if bundle.exists():
        run_cmd(root, "startup_budget", ["python3", "tools/context/startup_budget_test.py", "--root", str(root)], checks)
    else:
        add_check(checks, "startup_budget", "regression", "WARN", "MEDIUM", str(bundle), "missing", "generated before final governor run")

    verdict = read_json(root / "var/context_control_2026_06_23/audit/context_integrity_verdict.json", {})
    add_check(checks, "holdout_locked_after_regression", "regression", "PASS" if not verdict.get("hard_blocker", False) else "FAIL", "HIGH", "var/context_control_2026_06_23/audit/context_integrity_verdict.json", str(verdict.get("verdict", "")), "non-blocking")

    summary = write_check_outputs(root, "regression_check", checks)
    print(summary["verdict"])
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
