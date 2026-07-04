#!/usr/bin/env python3
"""Merge gap queues into context/indexes/GAP_INDEX.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

from context_common import (
    artifact_id,
    ensure_control_csvs,
    ensure_dirs,
    read_csv,
    relpath,
    sha256_file,
    utc_now,
    write_csv,
    write_script_audit,
)
from governor_common import get_project, project_index_path, project_scan_root


FIELDS = [
    "gap_id",
    "project_id",
    "source_gap_queue_path",
    "phase",
    "case_id",
    "gap_type",
    "severity",
    "blocking_level",
    "status",
    "next_action",
    "owner_type",
    "created_at_utc",
    "notes",
]


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4, "": 5}
BLOCK_ORDER = {"HARD": 0, "SAFETY": 0, "BLOCKING": 1, "NON_BLOCKING": 3, "WARNING": 4, "": 5}


def indexed_rel(root: Path, scan_root: Path, path: Path) -> str:
    if scan_root.resolve() != root.resolve():
        try:
            return str(path.resolve().relative_to(scan_root.resolve()))
        except Exception:
            return relpath(root, path)
    return relpath(root, path)


def normalize_row(root: Path, scan_root: Path, source: Path, row: dict[str, str], project_id: str) -> dict[str, str]:
    rel = indexed_rel(root, scan_root, source)
    phase = row.get("phase", "") or "unspecified"
    gap_type = row.get("gap_type", "") or row.get("reason", "") or "unspecified_gap"
    severity = (row.get("severity", "") or "INFO").upper()
    blocking = (row.get("blocking_level", "") or "NON_BLOCKING").upper()
    next_action = row.get("next_action", "")
    notes = row.get("notes", "")
    seed = "|".join([rel, phase, row.get("case_id", ""), gap_type, next_action, notes])
    return {
        "gap_id": row.get("gap_id", "") or artifact_id("gap", seed),
        "project_id": row.get("project_id", "") or project_id,
        "source_gap_queue_path": rel,
        "phase": phase,
        "case_id": row.get("case_id", ""),
        "gap_type": gap_type,
        "severity": severity,
        "blocking_level": blocking,
        "status": row.get("observed_status", "") or row.get("status", "") or "OPEN",
        "next_action": next_action,
        "owner_type": row.get("owner_type", "") or "agent",
        "created_at_utc": row.get("created_at_utc", "") or utc_now(),
        "notes": notes,
    }


def build_gap_index(root: Path, project_id: str | None = None) -> tuple[list[dict[str, str]], dict[str, str]]:
    project = get_project(root, project_id)
    scan_root = project_scan_root(root, project)
    output_path = project_index_path(root, project, "gap")
    if project["project_id"] == "default":
        ensure_control_csvs(root)
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    sources = list(sorted(scan_root.rglob("*gap_queue*.csv")))
    project_gap_queue = root / "context" / "projects" / str(project["project_id"]) / "gap_queue.csv"
    if project_gap_queue.exists() and project_gap_queue not in sources:
        sources.append(project_gap_queue)
    for source in sorted(sources):
        if not source.is_file() or source.resolve() == output_path.resolve():
            continue
        for raw in read_csv(source):
            if not any((value or "").strip() for value in raw.values()):
                continue
            row = normalize_row(root, scan_root, source, raw, str(project["project_id"]))
            key = (row["source_gap_queue_path"], row["phase"], row["gap_type"], row["next_action"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    rows.sort(key=lambda row: (SEVERITY_ORDER.get(row["severity"], 5), BLOCK_ORDER.get(row["blocking_level"], 5), row["created_at_utc"]))
    return rows, project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    ensure_dirs(root)
    rows, project = build_gap_index(root, args.project_id)
    output_path = project_index_path(root, project, "gap")
    write_csv(output_path, FIELDS, rows)
    now = utc_now()
    max_blocker = rows[0] if rows else {}
    summary = {
        "script": "build_gap_index.py",
        "project_id": project["project_id"],
        "scan_root": str(project_scan_root(root, project)),
        "created_at_utc": now,
        "output_path": relpath(root, output_path),
        "row_count": len(rows),
        "max_blocker": max_blocker,
    }
    verdict = {
        "script": "build_gap_index.py",
        "project_id": project["project_id"],
        "created_at_utc": now,
        "verdict": "GAP_INDEX_BUILT",
        "hard_blocker": bool(max_blocker and max_blocker.get("blocking_level") in {"HARD", "SAFETY"}),
    }
    manifest = [
        {
            "artifact_path": relpath(root, output_path),
            "artifact_role": "output",
            "sha256": sha256_file(output_path),
            "created_at_utc": now,
            "notes": "merged gap index",
        }
    ]
    write_script_audit(root, "build_gap_index", summary, verdict, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
