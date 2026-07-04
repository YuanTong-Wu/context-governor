#!/usr/bin/env python3
"""Read startup-safe index views with budget logging."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import artifact_id, char_count, read_csv, relpath, utc_now
from governor_common import READ_LOG_REL, ensure_default_registry, ensure_governor_dirs, filtered_rows, get_active_project, load_budget, write_jsonl_log


VIEW_MAP = {
    "file": "context/indexes/views/FILE_INDEX_VIEW.csv",
    "runner": "context/indexes/views/RUNNER_INDEX_VIEW.csv",
    "case": "context/indexes/views/CASE_INDEX_VIEW.csv",
    "evidence": "context/indexes/views/EVIDENCE_INDEX_VIEW.csv",
    "gap": "context/indexes/views/GAP_INDEX_VIEW.csv",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--view", choices=sorted(VIEW_MAP), required=True)
    parser.add_argument("--project")
    parser.add_argument("--phase")
    parser.add_argument("--artifact-type")
    parser.add_argument("--case-id")
    parser.add_argument("--entity-key")
    parser.add_argument("--status")
    parser.add_argument("--severity")
    parser.add_argument("--blocking-level")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--requested-by", default="agent")
    parser.add_argument("--reason", default="startup_safe_index_view")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_active_project(root)
    project_id = args.project or project["project_id"]
    budget = load_budget(root, project)
    path = root / VIEW_MAP[args.view]
    rows = read_csv(path)
    filters = {
        "project": project_id,
        "phase": args.phase or "",
        "artifact_type": args.artifact_type or "",
        "case_id": args.case_id or "",
        "entity_key": args.entity_key or "",
        "status": args.status or "",
        "severity": args.severity or "",
        "blocking_level": args.blocking_level or "",
    }
    selected = filtered_rows(rows, filters)[: max(0, min(args.limit, int(budget["index_view_max_rows"])))]
    returned_chars = len(json.dumps(selected, ensure_ascii=False))
    log = {
        "read_id": artifact_id("read_view", f"{path}:{utc_now()}"),
        "project_id": project_id,
        "path": relpath(root, path),
        "requested_by": args.requested_by,
        "reason": args.reason,
        "chars_requested": char_count(path),
        "chars_returned": returned_chars,
        "line_range": "",
        "allowed": True,
        "denial_reason": "",
        "created_at_utc": utc_now(),
    }
    write_jsonl_log(root, READ_LOG_REL, log)
    print(json.dumps({"allowed": True, "path": relpath(root, path), "rows": selected, "row_count": len(selected)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
