#!/usr/bin/env python3
"""Build a startup-safe bundle for the active project."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import char_count, line_count, read_csv, read_json, relpath, utc_now, write_csv, write_json
from governor_common import (
    ensure_default_registry,
    ensure_governor_dirs,
    get_project,
    load_budget,
    project_abs_path,
    project_control_path,
    project_views_dir,
)


VIEW_NAMES = {
    "file_index_view": "FILE_INDEX_VIEW.csv",
    "runner_index_view": "RUNNER_INDEX_VIEW.csv",
    "case_index_view": "CASE_INDEX_VIEW.csv",
    "evidence_index_view": "EVIDENCE_INDEX_VIEW.csv",
    "gap_index_view": "GAP_INDEX_VIEW.csv",
}


def compact_json(data: Any, keys: list[str]) -> str:
    if not isinstance(data, dict):
        return "{}"
    body = {key: data.get(key) for key in keys if key in data}
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True)


def read_short(path: Path, max_chars: int = 3500) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text.strip()
    return text[:max_chars].rstrip() + "\n[truncated_by_startup_bundle]"


def top_gaps(views_dir: Path) -> list[dict[str, str]]:
    path = views_dir / VIEW_NAMES["gap_index_view"]
    rows = read_csv(path)
    return rows[:10]


def build(root: Path, project_id: str | None = None) -> dict[str, Any]:
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_project(root, project_id)
    budget = load_budget(root, project)
    project_id = project["project_id"]
    views_dir = project_views_dir(root, project)
    view_paths = {role: relpath(root, views_dir / filename) for role, filename in VIEW_NAMES.items()}

    boot = project_abs_path(root, project, project["boot_path"])
    state_path = project_abs_path(root, project, project["state_path"])
    verdict_path = project_abs_path(root, project, project["verdict_path"])
    task = read_json(state_path, {})
    verdict = read_json(verdict_path, {})
    current_runner = str(task.get("current_runner", ""))
    current_output_dir = str(task.get("writable_output_dir", "var/context_governor_2026_06_24"))
    next_action = str(task.get("next_allowed_action", "Run tools/context/continue_project.sh <project_id>."))

    bundle_path = project_control_path(root, project, str(project.get("startup_bundle_path") or f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md"))
    manifest_path = bundle_path.with_name(f"{project_id}_STARTUP_BUNDLE_MANIFEST.csv")
    audit_path = bundle_path.with_name(f"{project_id}_STARTUP_BUDGET_AUDIT.json")

    lines: list[str] = []
    lines.append(f"# Startup Bundle: {project_id}")
    lines.append("")
    lines.append("This bundle is a bounded startup pointer set, not project history.")
    lines.append("")
    lines.append("## Boot")
    lines.append(read_short(boot, max_chars=min(3500, budget["boot_max_chars"])))
    lines.append("")
    lines.append("## Active State")
    lines.append(f"- State path: `{relpath(root, state_path)}`")
    lines.append("```json")
    lines.append(compact_json(task, ["project_id", "current_phase", "current_runner", "holdout_status", "latest_gap_queue_path", "next_allowed_action", "writable_output_dir"]))
    lines.append("```")
    lines.append("")
    lines.append("## Current Verdict")
    lines.append(f"- Verdict path: `{relpath(root, verdict_path)}`")
    lines.append("```json")
    lines.append(compact_json(verdict, ["verdict", "integrity_verdict", "hard_blocker", "latest_report_path", "updated_at_utc"]))
    lines.append("```")
    lines.append("")
    lines.append("## Startup-Safe Index Views")
    for label, rel in view_paths.items():
        lines.append(f"- {label}: `{rel}`")
    lines.append("")
    lines.append("## Current Execution")
    lines.append(f"- Current runner: `{current_runner}`")
    lines.append(f"- Current output directory: `{current_output_dir}`")
    lines.append(f"- Next action: {next_action}")
    lines.append("")
    lines.append("## Top Blocking Gaps")
    gaps = top_gaps(views_dir)
    if not gaps:
        lines.append("- None listed in the startup-safe gap view.")
    else:
        for row in gaps:
            item = row.get("next_action") or row.get("gap_type") or row.get("gap_id", "")
            severity = row.get("severity", "")
            blocking = row.get("blocking_level", "")
            case_id = row.get("case_id", "")
            lines.append(f"- {severity}/{blocking} {case_id}: {item}")
    lines.append("")
    lines.append("## Read Rules")
    lines.append("- At startup, read this bundle before opening project files.")
    lines.append("- Use index views above for orientation.")
    lines.append("- Use `tools/context/query_index.py` for full-index queries.")
    lines.append("- Use `tools/context/read_gate/read_context_file.py` for large files.")

    text = "\n".join(lines).strip() + "\n"
    bundle_path.write_text(text, encoding="utf-8")

    manifest_rows = [
        {"role": "boot", "path": relpath(root, boot), "chars": char_count(boot), "lines": line_count(boot)},
        {"role": "task_state", "path": relpath(root, state_path), "chars": char_count(state_path), "lines": line_count(state_path)},
        {"role": "current_verdict", "path": relpath(root, verdict_path), "chars": char_count(verdict_path), "lines": line_count(verdict_path)},
    ]
    for role, rel in view_paths.items():
        path = root / rel
        manifest_rows.append({"role": role, "path": rel, "chars": char_count(path), "lines": line_count(path)})
    write_csv(manifest_path, ["role", "path", "chars", "lines"], manifest_rows)

    audit = {
        "project_id": project_id,
        "bundle_path": relpath(root, bundle_path),
        "manifest_path": relpath(root, manifest_path),
        "bundle_chars": len(text),
        "manifest_files": len(manifest_rows),
        "max_chars": budget["startup_bundle_max_chars"],
        "max_files": budget["startup_bundle_max_files"],
        "current_runner": current_runner,
        "updated_at_utc": utc_now(),
    }
    write_json(audit_path, audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()
    audit = build(Path(args.root).expanduser().resolve(), args.project_id)
    print(f"startup bundle built: {audit['bundle_path']} ({audit['bundle_chars']} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
