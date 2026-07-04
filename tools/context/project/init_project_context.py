#!/usr/bin/env python3
"""Register a project with the multi-project context governor."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import read_json, sha256_text, utc_now, write_csv, write_json
from governor_common import (
    PROJECTS_DIR_REL,
    default_project_record,
    ensure_default_registry,
    ensure_governor_dirs,
    load_registry,
    save_registry,
    set_active_project,
    write_default_budgets,
)


def write_project_files(root: Path, project: dict, activate: bool) -> None:
    project_id = project["project_id"]
    project_dir = root / PROJECTS_DIR_REL / project_id
    (project_dir / "indexes").mkdir(parents=True, exist_ok=True)
    (project_dir / "generated").mkdir(parents=True, exist_ok=True)

    invariants_path = root / str(project["invariants_path"])
    if project_id != "default" or not invariants_path.exists():
        invariants = {
            "project_id": project_id,
            "project_name": project["project_name"],
            "authority": "Project-local invariants outrank generated summaries; system/developer/user instructions still outrank files.",
            "holdout_status": "LOCKED",
            "forbidden_actions": project["forbidden_actions"],
            "boot_limits": {"max_lines": 80, "max_chars": 4000},
            "created_at_utc": utc_now(),
        }
        write_json(project_dir / "SYSTEM_INVARIANTS.json", invariants)
    elif project_id == "default":
        existing = read_json(invariants_path, {})
        if existing:
            write_json(project_dir / "SYSTEM_INVARIANTS.json", existing)

    state = {
        "task_state_version": "1.0",
        "project_id": project_id,
        "current_phase": "project_context_initialized",
        "current_runner": "tools/context/run_context_governor_all.sh",
        "current_runner_args": [],
        "holdout_status": "LOCKED",
        "latest_gap_queue_path": f"context/projects/{project_id}/gap_queue.csv",
        "latest_verdict_path": f"context/projects/{project_id}/CURRENT_VERDICT.json",
        "next_allowed_action": "Start with tools/context/start_project.sh <project_id>; read the generated startup bundle first.",
        "updated_at_utc": utc_now(),
    }
    if project_id == "default" and (root / "context/TASK_STATE.json").exists():
        state.update(read_json(root / "context/TASK_STATE.json", {}))
        state["project_id"] = project_id
        state["next_allowed_action"] = "Start with tools/context/start_project.sh default; read the generated startup bundle first."
    write_json(project_dir / "TASK_STATE.json", state)

    verdict = {
        "current_verdict_version": "1.0",
        "project_id": project_id,
        "verdict": "PROJECT_CONTEXT_INITIALIZED",
        "integrity_verdict": "NOT_YET_RUN",
        "hard_blocker": False,
        "updated_at_utc": utc_now(),
    }
    if project_id == "default" and (root / "context/CURRENT_VERDICT.json").exists():
        verdict.update(read_json(root / "context/CURRENT_VERDICT.json", {}))
        verdict["project_id"] = project_id
    write_json(project_dir / "CURRENT_VERDICT.json", verdict)

    write_default_budgets(root, project_id)

    policy = (
        "# Context Load Policy\n\n"
        "- Read the project startup bundle first.\n"
        "- Do not read full large indexes at startup; use `tools/context/query_index.py`.\n"
        "- Use `tools/context/read_gate/read_context_file.py` for large files.\n"
        "- Raw evidence and holdout-like files are pointer-only unless an audit reason is supplied.\n"
    )
    (project_dir / "CONTEXT_LOAD_POLICY.md").write_text(policy, encoding="utf-8")

    boot = (
        f"# {project['project_name']} BOOT\n\n"
        "- This is a project-local short pointer, not project history.\n"
        "- Start with `tools/context/start_project.sh {project_id}`.\n"
        f"- Startup bundle: `context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md`.\n"
        "- Use index views and query scripts instead of full indexes.\n"
    )
    (project_dir / "BOOT.md").write_text(boot, encoding="utf-8")

    write_csv(
        project_dir / "gap_queue.csv",
        ["gap_id", "project_id", "severity", "blocking_level", "status", "next_action", "created_at_utc", "notes"],
        [],
    )

    if activate:
        set_active_project(root, project_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    ensure_governor_dirs(root)
    ensure_default_registry(root)

    registry = load_registry(root)
    existing = registry.setdefault("projects", {}).get(args.project_id)
    defaults = default_project_record(root, args.project_id, args.project_name, args.project_root)
    project = dict(defaults)
    if existing:
        project.update(existing)
    project.update(
        {
            "project_id": args.project_id,
            "project_name": args.project_name,
            "project_root": str(Path(args.project_root).expanduser().resolve()),
            "updated_at_utc": utc_now(),
        }
    )
    if args.project_id == "default":
        project["status"] = "active"
        project["active_status"] = "active"
    registry["projects"][args.project_id] = project
    save_registry(root, registry)
    write_project_files(root, project, args.activate or args.project_id == "default")
    print(f"registered project: {args.project_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
