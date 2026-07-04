#!/usr/bin/env python3
"""Build context/indexes/EVIDENCE_INDEX.csv from manifest metadata."""

from __future__ import annotations

import argparse
from pathlib import Path

from context_common import (
    append_gap,
    artifact_id,
    ensure_dirs,
    infer_authority,
    relpath,
    sha256_file,
    utc_now,
    write_csv,
    write_script_audit,
)
from governor_common import get_project, project_index_path, project_scan_root


FIELDS = [
    "evidence_id",
    "project_id",
    "case_id",
    "source_type",
    "authority_level",
    "official_status",
    "path",
    "raw_path",
    "manifest_path",
    "sha256",
    "published_at_utc",
    "retrieved_at_utc",
    "as_of_validity",
    "read_policy",
    "notes",
]


TERMS = ("evidence", "official", "manifest", "source", "archive", "as_of", "notice", "filing")


def source_type_for(rel: str) -> str:
    lower = rel.lower()
    if "official" in lower or "notice" in lower or "filing" in lower:
        return "official_manifest_or_report"
    if "archive" in lower or "raw" in lower:
        return "raw_archive_manifest"
    if "manifest" in lower:
        return "manifest"
    return "evidence_related_artifact"


def indexed_rel(root: Path, scan_root: Path, path: Path) -> str:
    if scan_root.resolve() != root.resolve():
        try:
            return str(path.resolve().relative_to(scan_root.resolve()))
        except Exception:
            return str(path.resolve())
    return relpath(root, path)


def build_evidence_index(root: Path, project_id: str | None = None) -> tuple[list[dict[str, str]], dict[str, str]]:
    project = get_project(root, project_id)
    scan_root = project_scan_root(root, project)
    rows: list[dict[str, str]] = []
    for path in sorted(scan_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".csv", ".json", ".jsonl", ".txt"}:
            continue
        rel = indexed_rel(root, scan_root, path)
        lower = rel.lower()
        if not any(term in lower for term in TERMS):
            continue
        source_type = source_type_for(rel)
        official = "OFFICIAL_CANDIDATE" if "official" in lower or "notice" in lower or "filing" in lower else "NOT_OFFICIAL_RAW"
        authority = infer_authority(Path(rel), "evidence_manifest")
        rows.append(
            {
                "evidence_id": artifact_id("evidence", f"{project['project_id']}:{rel}"),
                "project_id": str(project["project_id"]),
                "case_id": "",
                "source_type": source_type,
                "authority_level": str(authority),
                "official_status": official,
                "path": rel,
                "raw_path": rel if source_type == "raw_archive_manifest" else "",
                "manifest_path": rel if "manifest" in lower else "",
                "sha256": sha256_file(path),
                "published_at_utc": "",
                "retrieved_at_utc": "",
                "as_of_validity": "UNKNOWN",
                "read_policy": "metadata_only_unless_audit" if source_type == "raw_archive_manifest" else "metadata_first_read_content_only_for_audit",
                "notes": "search_results_and_request_captures_are_not_marked_official_raw",
            }
        )
    if not rows and project["project_id"] == "default":
        append_gap(
            root,
            {
                "phase": "context_control",
                "artifact_path": relpath(root, project_index_path(root, project, "evidence")),
                "gap_type": "missing_evidence_manifest_source",
                "severity": "LOW",
                "blocking_level": "NON_BLOCKING",
                "observed_status": "no evidence manifest detected",
                "expected_status": "evidence manifest optional for context microkernel",
                "auto_repairable": "FALSE",
                "repair_attempted": "FALSE",
                "repair_result": "",
                "next_action": "Add evidence manifests only when an evidence audit task requires them.",
                "notes": "Empty EVIDENCE_INDEX is acceptable for this bootstrap.",
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
    rows, project = build_evidence_index(root, args.project_id)
    output_path = project_index_path(root, project, "evidence")
    write_csv(output_path, FIELDS, rows)
    now = utc_now()
    summary = {
        "script": "build_evidence_index.py",
        "project_id": project["project_id"],
        "scan_root": str(project_scan_root(root, project)),
        "created_at_utc": now,
        "output_path": relpath(root, output_path),
        "row_count": len(rows),
        "official_candidates": sum(1 for row in rows if row["official_status"] == "OFFICIAL_CANDIDATE"),
    }
    verdict = {
        "script": "build_evidence_index.py",
        "project_id": project["project_id"],
        "created_at_utc": now,
        "verdict": "EVIDENCE_INDEX_BUILT" if rows else "EVIDENCE_INDEX_EMPTY_WITH_GAP",
        "hard_blocker": False,
    }
    manifest = [
        {
            "artifact_path": relpath(root, output_path),
            "artifact_role": "output",
            "sha256": sha256_file(output_path),
            "created_at_utc": now,
            "notes": "evidence metadata index",
        }
    ]
    write_script_audit(root, "build_evidence_index", summary, verdict, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
