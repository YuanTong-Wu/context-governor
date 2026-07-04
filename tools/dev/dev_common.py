#!/usr/bin/env python3
"""Shared helpers for local development change-control checks."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


CONTEXT_TOOL_DIR = Path(__file__).resolve().parents[1] / "context"
if str(CONTEXT_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTEXT_TOOL_DIR))

from context_common import read_csv, read_json, relpath, utc_now, write_csv, write_json  # noqa: E402


DEV_AUDIT_REL = Path("var/dev_change_control_2026_06_24")

CHECK_FIELDS = ["check_id", "category", "status", "severity", "path", "observed", "expected", "notes"]
RISK_FIELDS = ["path", "risk_level", "risk_type", "required_checks", "notes"]


def root_arg() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--change-note", default="")
    return parser


def resolve_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def ensure_dev_dir(root: Path) -> Path:
    path = root / DEV_AUDIT_REL
    path.mkdir(parents=True, exist_ok=True)
    return path


def git_changed_files(root: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception:
        return []
    files: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            files.append(path)
    return sorted(set(files))


def changed_files(root: Path, explicit: Iterable[str]) -> list[str]:
    explicit_list = [str(item).strip() for item in explicit if str(item).strip()]
    return sorted(set(explicit_list or git_changed_files(root)))


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


def write_check_outputs(root: Path, stem: str, checks: list[dict[str, str]]) -> dict[str, Any]:
    audit_dir = ensure_dev_dir(root)
    failures = [row for row in checks if row.get("status") == "FAIL"]
    warnings = [row for row in checks if row.get("status") == "WARN"]
    summary = {
        "script": stem,
        "created_at_utc": utc_now(),
        "check_count": len(checks),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "verdict": "PASS" if not failures else "FAIL",
    }
    write_csv(audit_dir / f"{stem}.csv", CHECK_FIELDS, checks)
    write_json(audit_dir / f"{stem}_summary.json", summary)
    return summary


def write_risk_outputs(root: Path, stem: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    audit_dir = ensure_dev_dir(root)
    high_count = sum(1 for row in rows if row.get("risk_level") in {"HIGH", "CRITICAL"})
    unknown_count = sum(
        1
        for row in rows
        if row.get("risk_level") == "UNKNOWN" or row.get("risk_type") == "UNKNOWN_CHANGE_SURFACE"
    )
    verdict = "UNKNOWN_CHANGE_SURFACE" if unknown_count else ("RISK_REVIEW_REQUIRED" if high_count else "LOW_RISK")
    summary = {
        "script": stem,
        "created_at_utc": utc_now(),
        "changed_file_count": len(rows),
        "high_or_critical_risk_count": high_count,
        "unknown_change_surface_count": unknown_count,
        "verdict": verdict,
    }
    write_csv(audit_dir / f"{stem}.csv", RISK_FIELDS, rows)
    write_json(audit_dir / f"{stem}_summary.json", summary)
    return summary


def json_parse_ok(path: Path) -> tuple[bool, str]:
    try:
        read_json(path, {})
        return True, "valid"
    except Exception as exc:
        return False, str(exc)


def csv_header(path: Path) -> list[str]:
    rows = read_csv(path)
    if rows:
        return list(rows[0].keys())
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            return next(reader, [])
    except Exception:
        return []


def path_exists(root: Path, rel: str | None) -> bool:
    return bool(rel) and (root / str(rel)).exists()


def rel(root: Path, path: Path) -> str:
    return relpath(root, path)
