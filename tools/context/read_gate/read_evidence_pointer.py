#!/usr/bin/env python3
"""Return evidence pointers and hashes without reading raw evidence bodies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import artifact_id, char_count, read_csv, relpath, sha256_file, utc_now
from governor_common import READ_LOG_REL, ensure_default_registry, ensure_governor_dirs, filtered_rows, get_active_project, load_budget, write_jsonl_log


def pointer_row(root: Path, row: dict[str, str]) -> dict[str, str]:
    body = dict(row)
    for key in ["path", "raw_path", "manifest_path"]:
        value = body.get(key, "")
        if value:
            candidate = root / value
            body[f"{key}_exists"] = "TRUE" if candidate.exists() else "FALSE"
            body[f"{key}_sha256"] = sha256_file(candidate) if candidate.exists() and candidate.is_file() else ""
    body["content_mode"] = "pointer_only"
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--project")
    parser.add_argument("--case-id")
    parser.add_argument("--entity-key")
    parser.add_argument("--status")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--requested-by", default="agent")
    parser.add_argument("--reason", default="evidence_pointer_only")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_active_project(root)
    project_id = args.project or project["project_id"]
    budget = load_budget(root, project)
    path = root / "context/indexes/views/EVIDENCE_INDEX_VIEW.csv"
    rows = filtered_rows(
        read_csv(path),
        {"project": project_id, "case_id": args.case_id or "", "entity_key": args.entity_key or "", "status": args.status or ""},
    )[: max(0, min(args.limit, int(budget["evidence_view_max_rows"])))]
    pointers = [pointer_row(root, row) for row in rows]
    log = {
        "read_id": artifact_id("evidence_pointer", f"{path}:{utc_now()}"),
        "project_id": project_id,
        "path": relpath(root, path),
        "requested_by": args.requested_by,
        "reason": args.reason,
        "chars_requested": char_count(path),
        "chars_returned": len(json.dumps(pointers, ensure_ascii=False)),
        "line_range": "",
        "allowed": True,
        "denial_reason": "POINTER_ONLY",
        "created_at_utc": utc_now(),
    }
    write_jsonl_log(root, READ_LOG_REL, log)
    print(json.dumps({"allowed": True, "mode": "pointer_only", "evidence_pointers": pointers, "row_count": len(pointers)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
