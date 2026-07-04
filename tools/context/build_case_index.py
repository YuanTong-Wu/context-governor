#!/usr/bin/env python3
"""Build context/indexes/CASE_INDEX.csv from metadata only."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from context_common import (
    append_gap,
    artifact_id,
    ensure_dirs,
    read_policy_for,
    relpath,
    sha256_file,
    utc_now,
    write_csv,
    write_script_audit,
)
from governor_common import get_project, project_index_path, project_scan_root


FIELDS = [
    "case_id",
    "project_id",
    "sample_id",
    "entity_key",
    "entity_name",
    "split_set",
    "lane",
    "current_status",
    "evidence_status",
    "first_check_status",
    "timestamp_audit_status",
    "historical_context_status",
    "data_status",
    "baseline_status",
    "leakage_status",
    "latest_case_card_path",
    "latest_gap_queue_path",
    "holdout_status",
    "notes",
]


CASE_TERMS = ("case", "sample", "case_card", "样本")


def entity_key_from_name(name: str) -> str:
    match = re.search(r"(?<!\d)(\d{4,6})(?!\d)", name)
    if match:
        return match.group(1)
    match = re.search(r"\b([A-Z]{2,5})(?:_[A-Z]{1,3})?\b", name)
    return match.group(1) if match else ""


def indexed_rel(root: Path, scan_root: Path, path: Path) -> str:
    if scan_root.resolve() != root.resolve():
        try:
            return str(path.resolve().relative_to(scan_root.resolve()))
        except Exception:
            return str(path.resolve())
    return relpath(root, path)


def build_case_index(root: Path, project_id: str | None = None) -> tuple[list[dict[str, str]], dict[str, str]]:
    project = get_project(root, project_id)
    scan_root = project_scan_root(root, project)
    latest_gap_queue_path = (
        "var/context_control_2026_06_23/gap_queue.csv"
        if project["project_id"] == "default"
        else f"context/projects/{project['project_id']}/gap_queue.csv"
    )
    rows: list[dict[str, str]] = []
    for path in sorted(scan_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".csv", ".json"}:
            continue
        rel = indexed_rel(root, scan_root, path)
        lower = rel.lower()
        if not any(term in lower for term in CASE_TERMS):
            continue
        locked = "LOCKED" if any(term in lower for term in ["holdout", "sealed", "封存"]) else "NOT_HOLDOUT"
        rows.append(
            {
                "case_id": artifact_id("case", f"{project['project_id']}:{rel}"),
                "project_id": str(project["project_id"]),
                "sample_id": Path(rel).stem,
                "entity_key": entity_key_from_name(Path(rel).stem),
                "entity_name": "",
                "split_set": "holdout" if locked == "LOCKED" else "unknown",
                "lane": "unknown",
                "current_status": "METADATA_INDEXED",
                "evidence_status": "UNKNOWN",
                "first_check_status": "UNKNOWN",
                "timestamp_audit_status": "UNKNOWN",
                "historical_context_status": "UNKNOWN",
                "data_status": "UNKNOWN",
                "baseline_status": "UNKNOWN",
                "leakage_status": "UNKNOWN",
                "latest_case_card_path": rel,
                "latest_gap_queue_path": latest_gap_queue_path,
                "holdout_status": locked,
                "notes": f"metadata_only; read_policy={read_policy_for(Path(rel), 'case_package')}; sha256={sha256_file(path)}",
            }
        )
    if not rows and project["project_id"] == "default":
        append_gap(
            root,
            {
                "phase": "context_control",
                "artifact_path": relpath(root, project_index_path(root, project, "case")),
                "gap_type": "missing_structured_case_source",
                "severity": "LOW",
                "blocking_level": "NON_BLOCKING",
                "observed_status": "no case source detected",
                "expected_status": "case source optional for context microkernel",
                "auto_repairable": "FALSE",
                "repair_attempted": "FALSE",
                "repair_result": "",
                "next_action": "Add case packages only when an active case task requires them.",
                "notes": "Empty CASE_INDEX is acceptable for this bootstrap.",
            },
        )
    return rows, project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    ensure_dirs(root)
    rows, project = build_case_index(root, args.project_id)
    output_path = project_index_path(root, project, "case")
    write_csv(output_path, FIELDS, rows)
    now = utc_now()
    summary = {
        "script": "build_case_index.py",
        "project_id": project["project_id"],
        "scan_root": str(project_scan_root(root, project)),
        "created_at_utc": now,
        "output_path": relpath(root, output_path),
        "row_count": len(rows),
        "holdout_rows": sum(1 for row in rows if row["holdout_status"] == "LOCKED"),
        "content_policy": "metadata_only",
    }
    verdict = {
        "script": "build_case_index.py",
        "project_id": project["project_id"],
        "created_at_utc": now,
        "verdict": "CASE_INDEX_BUILT" if rows else "CASE_INDEX_EMPTY_WITH_GAP",
        "hard_blocker": False,
    }
    manifest = [
        {
            "artifact_path": relpath(root, output_path),
            "artifact_role": "output",
            "sha256": sha256_file(output_path),
            "created_at_utc": now,
            "notes": "case index metadata only",
        }
    ]
    write_script_audit(root, "build_case_index", summary, verdict, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
