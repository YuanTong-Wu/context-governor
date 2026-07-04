#!/usr/bin/env python3
"""Read bounded gap metadata from the startup-safe gap view."""

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--project")
    parser.add_argument("--phase")
    parser.add_argument("--case-id")
    parser.add_argument("--severity")
    parser.add_argument("--blocking-level")
    parser.add_argument("--status")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--requested-by", default="agent")
    parser.add_argument("--reason", default="gap_context_pointer")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_active_project(root)
    project_id = args.project or project["project_id"]
    budget = load_budget(root, project)
    path = root / "context/indexes/views/GAP_INDEX_VIEW.csv"
    rows = filtered_rows(
        read_csv(path),
        {
            "project": project_id,
            "phase": args.phase or "",
            "case_id": args.case_id or "",
            "severity": args.severity or "",
            "blocking_level": args.blocking_level or "",
            "status": args.status or "",
        },
    )[: max(0, min(args.limit, int(budget["gap_view_max_rows"])))]
    log = {
        "read_id": artifact_id("gap_context", f"{path}:{utc_now()}"),
        "project_id": project_id,
        "path": relpath(root, path),
        "requested_by": args.requested_by,
        "reason": args.reason,
        "chars_requested": char_count(path),
        "chars_returned": len(json.dumps(rows, ensure_ascii=False)),
        "line_range": "",
        "allowed": True,
        "denial_reason": "",
        "created_at_utc": utc_now(),
    }
    write_jsonl_log(root, READ_LOG_REL, log)
    print(json.dumps({"allowed": True, "gap_rows": rows, "row_count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
