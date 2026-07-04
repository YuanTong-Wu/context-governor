#!/usr/bin/env python3
"""Build context/indexes/FILE_INDEX.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

from context_common import (
    AUDIT_DIR_REL,
    artifact_id,
    classify_artifact,
    ensure_dirs,
    file_mtime_utc,
    infer_authority,
    infer_phase,
    read_policy_for,
    relpath,
    sha256_file,
    should_scan_file,
    utc_now,
    write_csv,
    write_json,
    write_script_audit,
    write_policy_for,
)
from governor_common import get_project, project_index_path, project_scan_root


FIELDS = [
    "artifact_id",
    "project_id",
    "path",
    "artifact_type",
    "phase",
    "status",
    "authority_level",
    "sha256",
    "created_at_utc",
    "modified_at_utc",
    "read_policy",
    "write_policy",
    "source_of_truth",
    "supersedes",
    "superseded_by",
    "notes",
]


def indexed_rel(root: Path, scan_root: Path, path: Path) -> str:
    if scan_root.resolve() != root.resolve():
        try:
            return str(path.resolve().relative_to(scan_root.resolve()))
        except Exception:
            return str(path.resolve())
    return relpath(root, path)


def build_file_index(root: Path, project_id: str | None = None) -> tuple[list[dict[str, str]], dict[str, str]]:
    project = get_project(root, project_id)
    scan_root = project_scan_root(root, project)
    rows: list[dict[str, str]] = []
    for path in sorted(scan_root.rglob("*")):
        if not path.is_file() or not should_scan_file(path):
            continue
        rel = indexed_rel(root, scan_root, path)
        artifact_type = classify_artifact(Path(rel))
        authority = infer_authority(Path(rel), artifact_type)
        read_policy = read_policy_for(Path(rel), artifact_type)
        write_policy = write_policy_for(artifact_type)
        is_source = "TRUE" if authority >= 85 or artifact_type in {"invariant", "task_state"} else "FALSE"
        rows.append(
            {
                "artifact_id": artifact_id("file", f"{project['project_id']}:{rel}"),
                "project_id": str(project["project_id"]),
                "path": rel,
                "artifact_type": artifact_type,
                "phase": infer_phase(Path(rel)),
                "status": "ACTIVE" if "quarantine" not in rel else "QUARANTINED",
                "authority_level": str(authority),
                "sha256": sha256_file(path),
                "created_at_utc": file_mtime_utc(path),
                "modified_at_utc": file_mtime_utc(path),
                "read_policy": read_policy,
                "write_policy": write_policy,
                "source_of_truth": is_source,
                "supersedes": "",
                "superseded_by": "",
                "notes": "content_not_read" if path.suffix.lower() == ".parquet" else "",
            }
        )
    return rows, project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    ensure_dirs(root)

    rows, project = build_file_index(root, args.project_id)
    output_path = project_index_path(root, project, "file")
    write_csv(output_path, FIELDS, rows)

    now = utc_now()
    summary = {
        "script": "build_file_index.py",
        "project_id": project["project_id"],
        "scan_root": str(project_scan_root(root, project)),
        "created_at_utc": now,
        "output_path": relpath(root, output_path),
        "row_count": len(rows),
        "artifact_type_counts": {},
    }
    for row in rows:
        summary["artifact_type_counts"][row["artifact_type"]] = summary["artifact_type_counts"].get(row["artifact_type"], 0) + 1
    verdict = {
        "script": "build_file_index.py",
        "project_id": project["project_id"],
        "created_at_utc": now,
        "verdict": "FILE_INDEX_BUILT",
        "hard_blocker": False,
        "output_path": relpath(root, output_path),
    }
    manifest = [
        {
            "artifact_path": relpath(root, output_path),
            "artifact_role": "output",
            "sha256": sha256_file(output_path),
            "created_at_utc": now,
            "notes": "file index",
        }
    ]
    write_json(root / AUDIT_DIR_REL / "file_index_summary.json", summary)
    write_script_audit(root, "build_file_index", summary, verdict, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
