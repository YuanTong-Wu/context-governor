#!/usr/bin/env python3
"""Budget-aware file reader for context-sensitive work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import artifact_id, char_count, read_csv, relpath, utc_now
from governor_common import (
    READ_LOG_REL,
    append_governor_blocked,
    ensure_default_registry,
    ensure_governor_dirs,
    file_metadata,
    get_project,
    load_budget,
    project_abs_path,
    project_index_path,
    project_scan_root,
    project_views_dir,
    write_jsonl_log,
)


def parse_line_range(value: str) -> tuple[int, int] | None:
    if not value:
        return None
    left, _, right = value.partition(":")
    start = int(left or "1")
    end = int(right or str(start))
    if start <= 0 or end < start:
        raise argparse.ArgumentTypeError("line range must be START:END with 1-based positive lines")
    return start, end


def is_holdout(path: Path) -> bool:
    text = str(path).lower()
    return "holdout" in text or "sealed" in text or "封存" in str(path)


def slice_lines(path: Path, line_range: tuple[int, int] | None) -> str:
    if line_range is None:
        return path.read_text(encoding="utf-8", errors="replace")
    start, end = line_range
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[start - 1 : end]) + ("\n" if end >= start else "")


def path_candidates(root: Path, project: dict, path: Path, original_arg: str) -> set[str]:
    candidates = {str(path.resolve()), str(original_arg).lstrip("./")}
    try:
        candidates.add(relpath(root, path))
    except Exception:
        pass
    try:
        candidates.add(str(path.resolve().relative_to(project_scan_root(root, project).resolve())))
    except Exception:
        pass
    return {item for item in candidates if item}


def lookup_artifact_metadata(root: Path, project: dict, path: Path, original_arg: str) -> dict[str, str]:
    try:
        path.resolve().relative_to(project_views_dir(root, project).resolve())
        if path.name.endswith("_VIEW.csv"):
            return {
                "artifact_type": "index_view",
                "read_policy": "read_when_relevant",
                "source_index": "index_view",
            }
    except Exception:
        pass

    candidates = path_candidates(root, project, path, original_arg)
    evidence_rows = read_csv(project_index_path(root, project, "evidence"))
    for row in evidence_rows:
        policy = row.get("read_policy", "") or "metadata_only_unless_audit"
        if row.get("raw_path", "") in candidates:
            return {
                "artifact_type": "raw_archive",
                "read_policy": policy,
                "source_index": "evidence",
            }

    for row in read_csv(project_index_path(root, project, "file")):
        if row.get("path", "") in candidates:
            return {
                "artifact_type": row.get("artifact_type", "unknown") or "unknown",
                "read_policy": row.get("read_policy", "read_when_relevant") or "read_when_relevant",
                "source_index": "file",
            }

    for row in evidence_rows:
        policy = row.get("read_policy", "") or "metadata_first_read_content_only_for_audit"
        if row.get("path", "") in candidates or row.get("manifest_path", "") in candidates:
            return {
                "artifact_type": "evidence_manifest",
                "read_policy": policy,
                "source_index": "evidence",
            }

    return {
        "artifact_type": "unknown",
        "read_policy": "read_when_relevant",
        "source_index": "fallback",
    }


def read_denial_for(metadata: dict[str, str], allow_raw_content: bool) -> str:
    artifact_type = metadata.get("artifact_type", "unknown")
    read_policy = metadata.get("read_policy", "read_when_relevant")
    raw_types = {"raw_archive", "official_raw_archive", "raw_evidence"}
    if read_policy == "metadata_only_locked":
        return "METADATA_ONLY_LOCKED"
    if read_policy == "metadata_only_unless_audit" and not allow_raw_content:
        return "RAW_EVIDENCE_POINTER_ONLY"
    if read_policy == "metadata_first_read_content_only_for_audit" and artifact_type in raw_types and not allow_raw_content:
        return "RAW_EVIDENCE_POINTER_ONLY"
    return ""


def deny(
    root: Path,
    project_id: str,
    path: Path,
    reason: str,
    args: argparse.Namespace,
    chars_requested: int,
    artifact_metadata: dict[str, str] | None = None,
) -> int:
    artifact_metadata = artifact_metadata or {}
    log = {
        "read_id": artifact_id("read", f"{path}:{utc_now()}"),
        "project_id": project_id,
        "path": relpath(root, path),
        "artifact_type": artifact_metadata.get("artifact_type", ""),
        "read_policy": artifact_metadata.get("read_policy", ""),
        "source_index": artifact_metadata.get("source_index", ""),
        "requested_by": args.requested_by,
        "reason": args.reason or "",
        "chars_requested": chars_requested,
        "chars_returned": 0,
        "line_range": args.line_range or "",
        "allowed": False,
        "denial_reason": reason,
        "created_at_utc": utc_now(),
    }
    write_jsonl_log(root, READ_LOG_REL, log)
    append_governor_blocked(
        root,
        {
            "phase": "read_gate",
            "project_id": project_id,
            "artifact_path": relpath(root, path),
            "reason": reason,
            "severity": "HIGH",
            "next_action": "rerun read_context_file.py with --reason and a bounded --max-chars or --line-range when allowed",
        },
    )
    metadata = file_metadata(root, path)
    metadata.update(artifact_metadata)
    print(json.dumps({"allowed": False, "denial_reason": reason, "metadata": metadata}, ensure_ascii=False, indent=2))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--project-id")
    parser.add_argument("--requested-by", default="agent")
    parser.add_argument("--reason")
    parser.add_argument("--max-chars", type=int)
    parser.add_argument("--line-range")
    parser.add_argument("--allow-raw-content", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_project(root, args.project_id)
    project_id = project["project_id"]
    budget = load_budget(root, project)
    path = Path(args.path).expanduser()
    if not path.is_absolute():
        root_relative = (root / path).resolve()
        path = root_relative if root_relative.exists() else project_abs_path(root, project, path)
    if not path.exists() or not path.is_file():
        print(json.dumps({"allowed": False, "denial_reason": "FILE_NOT_FOUND", "path": str(path)}, ensure_ascii=False, indent=2))
        return 1

    artifact_metadata = lookup_artifact_metadata(root, project, path, args.path)
    total_chars = char_count(path)
    line_range = parse_line_range(args.line_range) if args.line_range else None
    requested_chars = args.max_chars or total_chars
    large = total_chars > int(budget["single_file_default_max_chars"])

    if is_holdout(path):
        return deny(root, project_id, path, "HOLDOUT_CONTENT_READ_DENIED", args, requested_chars, artifact_metadata)

    read_denial = read_denial_for(artifact_metadata, args.allow_raw_content)
    if read_denial == "METADATA_ONLY_LOCKED":
        return deny(root, project_id, path, read_denial, args, requested_chars, artifact_metadata)
    if read_denial == "RAW_EVIDENCE_POINTER_ONLY":
        log = {
            "read_id": artifact_id("read", f"{path}:{utc_now()}"),
            "project_id": project_id,
            "path": relpath(root, path),
            "artifact_type": artifact_metadata.get("artifact_type", ""),
            "read_policy": artifact_metadata.get("read_policy", ""),
            "source_index": artifact_metadata.get("source_index", ""),
            "requested_by": args.requested_by,
            "reason": args.reason or "raw_evidence_pointer_only",
            "chars_requested": requested_chars,
            "chars_returned": 0,
            "line_range": args.line_range or "",
            "allowed": True,
            "denial_reason": "RAW_EVIDENCE_POINTER_ONLY",
            "created_at_utc": utc_now(),
        }
        write_jsonl_log(root, READ_LOG_REL, log)
        metadata = file_metadata(root, path)
        metadata.update(artifact_metadata)
        print(json.dumps({"allowed": True, "mode": "pointer_only", "metadata": metadata}, ensure_ascii=False, indent=2))
        return 0

    if large and not args.reason:
        return deny(root, project_id, path, "LARGE_FILE_REQUIRES_REASON", args, requested_chars, artifact_metadata)
    if large and args.max_chars is None and line_range is None:
        return deny(root, project_id, path, "LARGE_FILE_REQUIRES_MAX_CHARS_OR_LINE_RANGE", args, requested_chars, artifact_metadata)

    content = slice_lines(path, line_range)
    if args.max_chars is not None and len(content) > args.max_chars:
        content = content[: args.max_chars]
    returned = len(content)
    log = {
        "read_id": artifact_id("read", f"{path}:{utc_now()}"),
        "project_id": project_id,
        "path": relpath(root, path),
        "artifact_type": artifact_metadata.get("artifact_type", ""),
        "read_policy": artifact_metadata.get("read_policy", ""),
        "source_index": artifact_metadata.get("source_index", ""),
        "requested_by": args.requested_by,
        "reason": args.reason or "",
        "chars_requested": requested_chars,
        "chars_returned": returned,
        "line_range": args.line_range or "",
        "allowed": True,
        "denial_reason": "",
        "created_at_utc": utc_now(),
    }
    write_jsonl_log(root, READ_LOG_REL, log)
    metadata = file_metadata(root, path)
    metadata.update(artifact_metadata)
    print(json.dumps({"allowed": True, "mode": "content", "metadata": metadata, "content": content}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
