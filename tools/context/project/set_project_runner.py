#!/usr/bin/env python3
"""Set or clear a project's business runner.

continue_project.sh runs the project's current runner. By default that is the
governor runner, which continue refuses to run (exit 3). This script stores a
business runner in the project registry and writes it into the project's task
state; update_task_state.py and init_project_context.py keep it from then on.

    python3 tools/context/project/set_project_runner.py --root . tools/jobs/run_daily.sh
    python3 tools/context/project/set_project_runner.py --root . --project-id my_project tools/run_main.py
    python3 tools/context/project/set_project_runner.py --root . --clear

A business runner is a .py or .sh file under tools/ of the project root, so the
runner index lists it. Governance scripts (tools/context, tools/dev,
tools/keeper) are refused. continue_project.sh calls it with --root <workspace>.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import read_json, utc_now, write_json, write_json_with_self_sha
from governor_common import (
    GOVERNANCE_RUNNERS,
    GOVERNOR_RUNNER,
    ensure_default_registry,
    get_project,
    load_registry,
    project_abs_path,
    resolve_project_root,
    resolve_runner_path,
    save_registry,
)

GOVERNANCE_DIRS = ("tools/context/", "tools/dev/", "tools/keeper/")
RUNNER_SUFFIXES = (".py", ".sh")


def fail(message: str) -> int:
    print(f"business runner not set: {message}", file=sys.stderr)
    return 2


def normalize_runner(root: Path, project: dict, value: str) -> tuple[str, str]:
    """Return (runner relative to the project root, error)."""
    text = value.strip()
    if not text:
        return "", "empty runner path"
    path = Path(text).expanduser()
    project_root = resolve_project_root(root, project)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(project_root)
        except ValueError:
            return "", f"{text} is outside the project root"
    rel = path.as_posix()
    while rel.startswith("./"):
        rel = rel[2:]
    if ".." in Path(rel).parts:
        return "", f"{text} leaves the project root"
    if rel in GOVERNANCE_RUNNERS or rel.startswith(GOVERNANCE_DIRS):
        return "", f"{rel} is a governance script, not a business runner"
    if not rel.startswith("tools/"):
        return "", f"{rel} must be under tools/ of the project root, so the runner index lists it"
    if not rel.endswith(RUNNER_SUFFIXES):
        return "", f"{rel} must be a .py or .sh file"
    if not resolve_runner_path(root, project, rel).is_file():
        return "", f"{rel} does not exist in the project root"
    return rel, ""


def write_state_runner(root: Path, project: dict, runner: str) -> list[Path]:
    """Write the runner into the project's existing task state files."""
    project_id = str(project["project_id"])
    paths = [project_abs_path(root, project, str(project["state_path"]))]
    local = root / "context/projects" / project_id / "TASK_STATE.json"
    if local.resolve() not in {path.resolve() for path in paths}:
        paths.append(local)
    if runner:
        next_action = f"Run tools/context/continue_project.sh {project_id} to run the business runner."
    else:
        next_action = f"Start with tools/context/start_project.sh {project_id}; read the generated startup bundle first."
    written = []
    for path in paths:
        state = read_json(path, None)
        if not isinstance(state, dict):
            continue
        state["current_runner"] = runner or GOVERNOR_RUNNER
        state["current_runner_args"] = []
        state["next_allowed_action"] = next_action
        state["updated_at_utc"] = utc_now()
        if "sha256_self" in state:
            write_json_with_self_sha(path, state)
        else:
            write_json(path, state)
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Set or clear a project's business runner.")
    parser.add_argument("runner", nargs="?", help="path under tools/ of the project root, e.g. tools/jobs/run_daily.sh")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--project-id", default=None, help="defaults to the active project")
    parser.add_argument("--clear", action="store_true", help="remove the business runner")
    args = parser.parse_args()
    if bool(args.runner) == bool(args.clear):
        parser.error("give a runner path or --clear")

    root = Path(args.root).expanduser().resolve()
    ensure_default_registry(root)
    project = get_project(root, args.project_id)
    project_id = str(project["project_id"])

    runner = ""
    if not args.clear:
        runner, error = normalize_runner(root, project, args.runner)
        if error:
            return fail(error)

    registry = load_registry(root)
    record = registry["projects"][project_id]
    if runner:
        record["business_runner"] = runner
    else:
        record.pop("business_runner", None)
    record["updated_at_utc"] = utc_now()
    save_registry(root, registry)
    write_state_runner(root, record, runner)

    if runner:
        print(f"business runner for {project_id}: {runner}")
        print(f"run it with: bash tools/context/continue_project.sh {project_id} --root .")
    else:
        print(f"business runner cleared for {project_id}; current runner is {GOVERNOR_RUNNER} again")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
