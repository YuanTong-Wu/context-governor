#!/usr/bin/env python3
"""Check that the context microkernel stays small, pointed, and safe."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from context_common import (
    AUDIT_DIR_REL,
    CONTROL_DIR_REL,
    append_blocked,
    append_gap,
    char_count,
    ensure_dirs,
    line_count,
    read_csv,
    read_json,
    relpath,
    utc_now,
    write_csv,
    write_json,
    write_json_with_self_sha,
    write_script_audit,
)


CHECK_FIELDS = ["check_id", "category", "status", "severity", "path", "observed", "expected", "notes"]

RECURSIVE_ENTRY_NAMES = {
    "BOOT_FOR_BOOT.md",
    "START_HERE_FOR_START_HERE.md",
    "README_FOR_BOOT.md",
    "ENTRYPOINT_SUMMARY_OF_ENTRYPOINT.md",
}

BAD_BOOT_PATTERNS = [
    ("boot_sample_detail", re.compile(r"(?i)\b(sample_id|entity_key\s*\||case_id\s*\|)\b")),
    ("boot_results_or_metrics", re.compile(r"(?i)\b(metrics table|performance table|results table)\b|结果表|指标表")),
    ("boot_old_long_history", re.compile(r"(?i)\b(full project history|complete project history|long project history)\b")),
    ("boot_full_gap_list", re.compile(r"(?i)\b(full gap queue|complete gap list|all gaps)\b")),
    ("boot_raw_source_body", re.compile(r"(?i)\b(raw evidence content|verbatim source|full source text)\b")),
]

BAD_SEMANTIC_DRIFT = [
    ("boot_claims_project_summary", re.compile(r"(?i)\bBOOT\.md\s+is\s+(?:a\s+|the\s+)?(?:full\s+|complete\s+)?project\s+(?:summary|report)")),
]


def load_forbidden_claims(invariants: dict[str, Any]) -> tuple[list[tuple[str, re.Pattern[str]]], list[str]]:
    """Read project-specific drift claims from SYSTEM_INVARIANTS.json.

    Each entry of "forbidden_claims" is {"id": ..., "pattern": <regex>}. A claim
    that matches BOOT.md is reported as semantic drift. Invalid entries are
    returned as errors so the audit can fail on them.
    """
    claims: list[tuple[str, re.Pattern[str]]] = []
    errors: list[str] = []
    entries = invariants.get("forbidden_claims", []) if isinstance(invariants, dict) else []
    for idx, entry in enumerate(entries if isinstance(entries, list) else []):
        claim_id = str(entry.get("id") or f"claim_{idx}") if isinstance(entry, dict) else f"claim_{idx}"
        pattern = entry.get("pattern") if isinstance(entry, dict) else None
        try:
            claims.append((f"claim_{claim_id}", re.compile(str(pattern))))
        except (re.error, TypeError):
            errors.append(claim_id)
    return claims, errors


def authority_number(row: dict[str, Any]) -> int:
    try:
        return int(str(row.get("authority_level", "0") or "0"))
    except ValueError:
        return 0


def authority_winner(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return max(rows, key=authority_number)


def add_check(
    checks: list[dict[str, str]],
    check_id: str,
    category: str,
    status: str,
    severity: str,
    path: str,
    observed: str,
    expected: str,
    notes: str = "",
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "status": status,
            "severity": severity,
            "path": path,
            "observed": observed,
            "expected": expected,
            "notes": notes,
        }
    )


def json_parse_check(root: Path, checks: list[dict[str, str]], rel: str) -> Any:
    path = root / rel
    try:
        data = read_json(path, {})
        add_check(checks, f"json_parse_{Path(rel).stem}", "schema", "PASS", "HIGH", rel, "valid", "valid_json")
        return data
    except Exception as exc:
        add_check(checks, f"json_parse_{Path(rel).stem}", "schema", "FAIL", "HIGH", rel, str(exc), "valid_json")
        return {}


def find_recursive_entry_files(root: Path) -> list[Path]:
    found: list[Path] = []
    skip = {".git", "__pycache__", "node_modules"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if "context/quarantine" in relpath(root, path):
            continue
        if path.name in RECURSIVE_ENTRY_NAMES:
            found.append(path)
    return found


def classify_verdict(checks: list[dict[str, str]]) -> str:
    failures = [row for row in checks if row["status"] == "FAIL"]
    warnings = [row for row in checks if row["status"] == "WARN"]
    if not failures:
        return "CONTEXT_INTEGRITY_PASS" if not warnings else "CONTEXT_INTEGRITY_PASS_WITH_WARNINGS"
    ids = {row["check_id"] for row in failures}
    categories = {row["category"] for row in failures}
    if "boot_line_limit" in ids or "boot_char_limit" in ids:
        return "CONTEXT_INTEGRITY_FAIL_BOOT_TOO_LARGE"
    if "recursive_entry_files_absent" in ids or "boot_no_recursive_entry_reference" in ids:
        return "CONTEXT_INTEGRITY_FAIL_RECURSIVE_ENTRY"
    if "task_state_line_limit" in ids or "current_verdict_line_limit" in ids:
        return "CONTEXT_INTEGRITY_FAIL_STATE_TOO_LARGE"
    if "holdout_locked" in ids:
        return "CONTEXT_INTEGRITY_FAIL_HOLDOUT_RISK"
    if "semantic" in categories or "boot_content" in categories:
        return "CONTEXT_INTEGRITY_FAIL_SEMANTIC_DRIFT"
    if "pointer" in categories or "schema" in categories:
        return "CONTEXT_INTEGRITY_FAIL_MISSING_POINTER"
    if "authority" in categories:
        return "CONTEXT_INTEGRITY_FAIL_SEMANTIC_DRIFT"
    return "CONTEXT_INTEGRITY_FAIL_UNKNOWN"


def run_checks(root: Path) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    ensure_dirs(root)
    checks: list[dict[str, str]] = []

    boot_path = root / "BOOT.md"
    boot_text = boot_path.read_text(encoding="utf-8", errors="replace") if boot_path.exists() else ""
    invariants = json_parse_check(root, checks, "context/SYSTEM_INVARIANTS.json")
    task = json_parse_check(root, checks, "context/TASK_STATE.json")
    current = json_parse_check(root, checks, "context/CURRENT_VERDICT.json")

    max_lines = int(invariants.get("boot_limits", {}).get("max_lines", 80) or 80)
    max_chars = int(invariants.get("boot_limits", {}).get("max_chars", 4000) or 4000)

    add_check(
        checks,
        "boot_exists",
        "boot_size",
        "PASS" if boot_path.exists() else "FAIL",
        "HIGH",
        "BOOT.md",
        "exists" if boot_path.exists() else "missing",
        "exists",
    )
    add_check(
        checks,
        "boot_line_limit",
        "boot_size",
        "PASS" if boot_path.exists() and line_count(boot_path) <= max_lines else "FAIL",
        "HIGH",
        "BOOT.md",
        str(line_count(boot_path)),
        f"<= {max_lines}",
    )
    add_check(
        checks,
        "boot_char_limit",
        "boot_size",
        "PASS" if boot_path.exists() and char_count(boot_path) <= max_chars else "FAIL",
        "HIGH",
        "BOOT.md",
        str(char_count(boot_path)),
        f"<= {max_chars}",
    )

    table_lines = sum(1 for line in boot_text.splitlines() if line.strip().startswith("|") and line.strip().endswith("|"))
    add_check(
        checks,
        "boot_no_long_tables",
        "boot_content",
        "PASS" if table_lines <= 4 else "FAIL",
        "MEDIUM",
        "BOOT.md",
        str(table_lines),
        "<= 4 markdown table lines",
    )
    for check_id, pattern in BAD_BOOT_PATTERNS:
        match = pattern.search(boot_text)
        add_check(
            checks,
            check_id,
            "boot_content",
            "FAIL" if match else "PASS",
            "HIGH",
            "BOOT.md",
            match.group(0) if match else "absent",
            "absent",
        )
    claims, claim_errors = load_forbidden_claims(invariants)
    for claim_id in claim_errors:
        add_check(
            checks,
            f"forbidden_claim_pattern_{claim_id}",
            "schema",
            "FAIL",
            "HIGH",
            "context/SYSTEM_INVARIANTS.json",
            "invalid regex",
            "valid forbidden_claims pattern",
        )
    for check_id, pattern in BAD_SEMANTIC_DRIFT + claims:
        match = pattern.search(boot_text)
        add_check(
            checks,
            check_id,
            "semantic",
            "FAIL" if match else "PASS",
            "HIGH",
            "BOOT.md",
            match.group(0) if match else "absent",
            "absent",
        )

    add_check(
        checks,
        "boot_no_recursive_entry_reference",
        "recursion",
        "PASS" if "BOOT_FOR_BOOT" not in boot_text else "FAIL",
        "HIGH",
        "BOOT.md",
        "absent" if "BOOT_FOR_BOOT" not in boot_text else "present",
        "absent",
    )
    recursive_files = find_recursive_entry_files(root)
    add_check(
        checks,
        "recursive_entry_files_absent",
        "recursion",
        "PASS" if not recursive_files else "FAIL",
        "HIGH",
        ".",
        ",".join(relpath(root, path) for path in recursive_files) if recursive_files else "none",
        "none",
    )

    task_path = root / "context/TASK_STATE.json"
    verdict_path = root / "context/CURRENT_VERDICT.json"
    add_check(
        checks,
        "task_state_line_limit",
        "state_size",
        "PASS" if task_path.exists() and line_count(task_path) <= 200 else "FAIL",
        "HIGH",
        "context/TASK_STATE.json",
        str(line_count(task_path)),
        "<= 200",
    )
    add_check(
        checks,
        "current_verdict_line_limit",
        "state_size",
        "PASS" if verdict_path.exists() and line_count(verdict_path) <= 120 else "FAIL",
        "HIGH",
        "context/CURRENT_VERDICT.json",
        str(line_count(verdict_path)),
        "<= 120",
    )

    for rel in [
        "context/indexes/FILE_INDEX.csv",
        "context/indexes/RUNNER_INDEX.csv",
        "context/indexes/GAP_INDEX.csv",
    ]:
        add_check(
            checks,
            f"exists_{Path(rel).stem.lower()}",
            "pointer",
            "PASS" if (root / rel).exists() else "FAIL",
            "HIGH",
            rel,
            "exists" if (root / rel).exists() else "missing",
            "exists",
        )

    runners = read_csv(root / "context/indexes/RUNNER_INDEX.csv")
    runner_paths = {row.get("path", "") for row in runners}
    current_runner = task.get("current_runner", "")
    add_check(
        checks,
        "current_runner_indexed",
        "pointer",
        "PASS" if current_runner in runner_paths and (root / current_runner).exists() else "FAIL",
        "HIGH",
        current_runner or "context/TASK_STATE.json",
        "indexed" if current_runner in runner_paths else "missing",
        "runner exists in RUNNER_INDEX.csv",
    )

    for key, check_id in [
        ("latest_verdict_path", "latest_verdict_exists"),
        ("latest_gap_queue_path", "latest_gap_queue_exists"),
    ]:
        rel = task.get(key, "")
        add_check(
            checks,
            check_id,
            "pointer",
            "PASS" if rel and (root / rel).exists() else "FAIL",
            "HIGH",
            rel or f"context/TASK_STATE.json:{key}",
            "exists" if rel and (root / rel).exists() else "missing",
            "existing path",
        )

    holdout_required = invariants.get("holdout_status_required", "LOCKED")
    add_check(
        checks,
        "holdout_locked",
        "holdout",
        "PASS" if task.get("holdout_status") == holdout_required == "LOCKED" else "FAIL",
        "HIGH",
        "context/TASK_STATE.json",
        str(task.get("holdout_status", "")),
        "LOCKED",
    )

    file_rows = read_csv(root / "context/indexes/FILE_INDEX.csv")
    high_generated = [
        row
        for row in file_rows
        if row.get("artifact_type") in {"summary", "report", "boot"}
        and authority_number(row) > 90
        and row.get("source_of_truth") == "TRUE"
    ]
    add_check(
        checks,
        "compressed_context_authority_ceiling",
        "authority",
        "PASS" if not high_generated else "FAIL",
        "HIGH",
        "context/indexes/FILE_INDEX.csv",
        ",".join(row.get("path", "") for row in high_generated) if high_generated else "none",
        "generated summaries cannot outrank sources",
    )

    verdict = classify_verdict(checks)
    failures = [row for row in checks if row["status"] == "FAIL"]
    warnings = [row for row in checks if row["status"] == "WARN"]
    hard_blocker = bool(failures)
    now = utc_now()
    summary = {
        "script": "context_integrity_check.py",
        "created_at_utc": now,
        "verdict": verdict,
        "hard_blocker": hard_blocker,
        "check_count": len(checks),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "boot_line_count": line_count(boot_path),
        "boot_char_count": char_count(boot_path),
    }
    verdict_doc = {
        "script": "context_integrity_check.py",
        "created_at_utc": now,
        "verdict": verdict,
        "hard_blocker": hard_blocker,
        "failures": failures[:20],
    }
    audit_dir = root / AUDIT_DIR_REL
    write_csv(audit_dir / "context_integrity_check.csv", CHECK_FIELDS, checks)
    write_json(audit_dir / "context_integrity_summary.json", summary)
    write_json(audit_dir / "context_integrity_verdict.json", verdict_doc)
    write_json(root / CONTROL_DIR_REL / "summary.json", summary)
    write_json(root / CONTROL_DIR_REL / "verdict.json", verdict_doc)
    write_json_with_self_sha(root / "context/CURRENT_VERDICT.json", {
        "current_verdict_version": "1.0",
        "updated_at_utc": now,
        "verdict": verdict,
        "hard_blocker": hard_blocker,
        "latest_summary_path": str(CONTROL_DIR_REL / "summary.json"),
        "latest_report_path": "",
        "failure_count": len(failures),
        "notes": "Integrity verdict generated from context microkernel checks.",
    })
    write_script_audit(root, "context_integrity_check", summary, verdict_doc, [])

    if failures:
        first = failures[0]
        append_gap(
            root,
            {
                "phase": "context_control",
                "artifact_path": first["path"],
                "gap_type": first["check_id"],
                "severity": first["severity"],
                "blocking_level": "HARD",
                "observed_status": first["observed"],
                "expected_status": first["expected"],
                "auto_repairable": "TRUE",
                "repair_attempted": "FALSE",
                "repair_result": "",
                "next_action": "Run tools/context/context_repair.py, then rerun context_integrity_check.py.",
                "notes": verdict,
            },
        )
        append_blocked(
            root,
            {
                "phase": "context_control",
                "artifact_path": first["path"],
                "reason": first["check_id"],
                "severity": first["severity"],
                "next_action": "Repair the context microkernel before using BOOT.md as startup context.",
                "notes": verdict,
            },
        )

    return {"summary": summary, "verdict": verdict_doc, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_checks(Path(args.root))
    if args.json:
        print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if not result["verdict"]["hard_blocker"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
