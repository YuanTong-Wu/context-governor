#!/usr/bin/env python3
"""Query full indexes by filters instead of reading them wholesale."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import read_csv, relpath, utc_now, write_csv
from governor_common import (
    INDEX_QUERY_LOG_REL,
    ensure_default_registry,
    ensure_governor_dirs,
    filtered_rows,
    get_project,
    project_index_path,
    write_jsonl_log,
)


INDEX_NAMES = ("file", "runner", "case", "evidence", "gap")


def print_csv(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    writer = csv.DictWriter(sys.stdout, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--index", choices=sorted(INDEX_NAMES), required=True)
    parser.add_argument("--project")
    parser.add_argument("--project-id")
    parser.add_argument("--phase")
    parser.add_argument("--artifact-type")
    parser.add_argument("--case-id")
    parser.add_argument("--entity-key")
    parser.add_argument("--status")
    parser.add_argument("--severity")
    parser.add_argument("--blocking-level")
    parser.add_argument("--path-contains")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_project(root, args.project_id or args.project)
    project_id = project["project_id"]

    source = project_index_path(root, project, args.index)
    rows = read_csv(source)
    for row in rows:
        row.setdefault("project_id", project_id)
    filters = {
        "project": project_id,
        "phase": args.phase or "",
        "artifact_type": args.artifact_type or "",
        "case_id": args.case_id or "",
        "entity_key": args.entity_key or "",
        "status": args.status or "",
        "severity": args.severity or "",
        "blocking_level": args.blocking_level or "",
        "path_contains": args.path_contains or "",
    }
    results = filtered_rows(rows, filters)[: max(args.limit, 0)]

    if args.output:
        write_csv(Path(args.output), list(results[0].keys()) if results else ["project_id"], results)
    else:
        print_csv(results)

    write_jsonl_log(
        root,
        INDEX_QUERY_LOG_REL,
        {
            "query_id": f"idxq_{utc_now()}",
            "project_id": project_id,
            "index": args.index,
            "source_path": relpath(root, source),
            "filters": {k: v for k, v in filters.items() if v},
            "limit": args.limit,
            "rows_returned": len(results),
            "output": args.output or "stdout",
            "created_at_utc": utc_now(),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
