#!/usr/bin/env python3
"""Validate that the active project's startup bundle stays within budget."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import char_count, line_count, read_csv, read_json, relpath, utc_now, write_csv, write_json
from governor_common import (
    GOVERNOR_AUDIT_DIR_REL,
    append_governor_blocked,
    ensure_default_registry,
    ensure_governor_dirs,
    get_active_project,
    load_budget,
    project_abs_path,
)


CHECK_FIELDS = ["check_id", "status", "severity", "path", "observed", "expected", "notes"]
FULL_INDEX_PATHS = [
    "context/indexes/FILE_INDEX.csv",
    "context/indexes/RUNNER_INDEX.csv",
    "context/indexes/CASE_INDEX.csv",
    "context/indexes/EVIDENCE_INDEX.csv",
    "context/indexes/GAP_INDEX.csv",
]
VIEW_PATHS = [
    "context/indexes/views/FILE_INDEX_VIEW.csv",
    "context/indexes/views/RUNNER_INDEX_VIEW.csv",
    "context/indexes/views/GAP_INDEX_VIEW.csv",
]
RAW_PATTERNS = [
    re.compile(r"\.source_cache/"),
    re.compile(r"raw evidence content", re.I),
    re.compile(r"原始证据正文"),
]
REPORT_PATTERNS = [re.compile(r"full project history", re.I), re.compile(r"完整项目历史")]
RESULT_PATTERNS = [re.compile(r"results table", re.I), re.compile(r"结果表")]
HOLDOUT_PATTERNS = [re.compile(r"holdout.*UNLOCKED", re.I), re.compile(r"封存样本内容")]


def add(checks: list[dict[str, str]], check_id: str, ok: bool, severity: str, path: str, observed: Any, expected: str, notes: str = "") -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "PASS" if ok else "FAIL",
            "severity": severity,
            "path": path,
            "observed": str(observed),
            "expected": expected,
            "notes": notes,
        }
    )


def classify(checks: list[dict[str, str]]) -> str:
    failures = [row for row in checks if row["status"] == "FAIL"]
    if not failures:
        return "STARTUP_BUDGET_PASS"
    ids = {row["check_id"] for row in failures}
    if any("full_index" in item for item in ids):
        return "STARTUP_BUDGET_FAIL_FULL_INDEX_INCLUDED"
    if any("raw_evidence" in item for item in ids):
        return "STARTUP_BUDGET_FAIL_RAW_EVIDENCE_INCLUDED"
    if any("holdout" in item for item in ids):
        return "STARTUP_BUDGET_FAIL_HOLDOUT_RISK"
    if "current_runner_present" in ids:
        return "STARTUP_BUDGET_FAIL_MISSING_CURRENT_RUNNER"
    if any("size" in item or "rows" in item or "chars" in item for item in ids):
        return "STARTUP_BUDGET_FAIL_TOO_LARGE"
    return "STARTUP_BUDGET_FAIL_UNKNOWN"


def run(root: Path) -> dict[str, Any]:
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_active_project(root)
    budget = load_budget(root, project)
    project_id = project["project_id"]
    bundle = root / f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md"
    manifest = root / f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE_MANIFEST.csv"
    boot = project_abs_path(root, project, project["boot_path"])
    state_path = project_abs_path(root, project, project["state_path"])
    task = read_json(state_path, {})
    current_runner = str(task.get("current_runner", ""))
    text = bundle.read_text(encoding="utf-8", errors="replace") if bundle.exists() else ""
    manifest_rows = read_csv(manifest)

    checks: list[dict[str, str]] = []
    add(checks, "boot_line_limit", boot.exists() and line_count(boot) <= budget["boot_max_lines"], "HIGH", relpath(root, boot), line_count(boot), f"<= {budget['boot_max_lines']}")
    add(checks, "boot_char_limit", boot.exists() and char_count(boot) <= budget["boot_max_chars"], "HIGH", relpath(root, boot), char_count(boot), f"<= {budget['boot_max_chars']}")
    add(checks, "startup_bundle_exists", bundle.exists(), "HIGH", relpath(root, bundle), "exists" if bundle.exists() else "missing", "exists")
    add(checks, "startup_bundle_chars", bundle.exists() and len(text) <= budget["startup_bundle_max_chars"], "HIGH", relpath(root, bundle), len(text), f"<= {budget['startup_bundle_max_chars']}")
    add(checks, "startup_bundle_files", len(manifest_rows) <= budget["startup_bundle_max_files"], "HIGH", relpath(root, manifest), len(manifest_rows), f"<= {budget['startup_bundle_max_files']}")

    for full_path in FULL_INDEX_PATHS:
        in_manifest = any(row.get("path") == full_path for row in manifest_rows)
        in_text = full_path in text
        add(checks, f"no_full_index_{Path(full_path).stem.lower()}", not in_manifest and not in_text, "HIGH", relpath(root, bundle), "present" if in_manifest or in_text else "absent", "absent")

    for view_path in VIEW_PATHS:
        add(checks, f"view_used_{Path(view_path).stem.lower()}", view_path in text, "HIGH", relpath(root, bundle), "present" if view_path in text else "absent", "present")

    for view_path in sorted((root / "context/indexes/views").glob("*_VIEW.csv")):
        rows = read_csv(view_path)
        add(checks, f"view_rows_{view_path.stem.lower()}", len(rows) <= budget["index_view_max_rows"], "HIGH", relpath(root, view_path), len(rows), f"<= {budget['index_view_max_rows']}")
        add(checks, f"view_chars_{view_path.stem.lower()}", char_count(view_path) <= budget["index_view_max_chars"], "MEDIUM", relpath(root, view_path), char_count(view_path), f"<= {budget['index_view_max_chars']}")

    add(checks, "current_runner_present", bool(current_runner) and current_runner in text, "HIGH", relpath(root, bundle), current_runner or "missing", "current runner path in bundle")
    add(checks, "next_action_present", "Next action:" in text or "下一步" in text, "HIGH", relpath(root, bundle), "present" if ("Next action:" in text or "下一步" in text) else "absent", "present")

    add(checks, "no_raw_evidence_content", not any(pattern.search(text) for pattern in RAW_PATTERNS), "HIGH", relpath(root, bundle), "present" if any(pattern.search(text) for pattern in RAW_PATTERNS) else "absent", "absent")
    add(checks, "no_long_report_content", not any(pattern.search(text) for pattern in REPORT_PATTERNS), "MEDIUM", relpath(root, bundle), "present" if any(pattern.search(text) for pattern in REPORT_PATTERNS) else "absent", "absent")
    add(checks, "no_results_table", not any(pattern.search(text) for pattern in RESULT_PATTERNS), "HIGH", relpath(root, bundle), "present" if any(pattern.search(text) for pattern in RESULT_PATTERNS) else "absent", "absent")
    add(checks, "holdout_locked", str(task.get("holdout_status", "LOCKED")).upper() == "LOCKED" and not any(pattern.search(text) for pattern in HOLDOUT_PATTERNS), "HIGH", relpath(root, bundle), task.get("holdout_status", ""), "LOCKED")

    verdict = classify(checks)
    failures = [row for row in checks if row["status"] == "FAIL"]
    if failures:
        append_governor_blocked(
            root,
            {
                "phase": "startup_budget_test",
                "project_id": project_id,
                "artifact_path": relpath(root, bundle),
                "reason": verdict,
                "severity": "HIGH",
                "next_action": "rebuild views and startup bundle, then rerun startup_budget_test.py",
                "notes": "; ".join(row["check_id"] for row in failures[:8]),
            },
        )

    check_path = root / GOVERNOR_AUDIT_DIR_REL / "startup_budget_check.csv"
    summary_path = root / GOVERNOR_AUDIT_DIR_REL / "startup_budget_summary.json"
    verdict_path = root / GOVERNOR_AUDIT_DIR_REL / "startup_budget_verdict.json"
    write_csv(check_path, CHECK_FIELDS, checks)
    summary = {
        "project_id": project_id,
        "checks": len(checks),
        "failures": len(failures),
        "bundle_chars": len(text),
        "bundle_files": len(manifest_rows),
        "updated_at_utc": utc_now(),
    }
    write_json(summary_path, summary)
    body = {"project_id": project_id, "verdict": verdict, "hard_blocker": bool(failures), "updated_at_utc": utc_now()}
    write_json(verdict_path, body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    result = run(Path(args.root).expanduser().resolve())
    print(f"startup budget verdict: {result['verdict']}")
    return 0 if result["verdict"] in {"STARTUP_BUDGET_PASS", "STARTUP_BUDGET_PASS_WITH_WARNINGS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
