#!/usr/bin/env python3
"""Check that registry and state pointers resolve to local files."""

from __future__ import annotations

from pathlib import Path

from dev_common import add_check, path_exists, read_json, resolve_root, root_arg, write_check_outputs
from governor_common import resolve_runner_path


def check_rel(checks: list[dict[str, str]], root: Path, check_id: str, rel: str, severity: str = "HIGH") -> None:
    add_check(
        checks,
        check_id,
        "path",
        "PASS" if path_exists(root, rel) else "FAIL",
        severity,
        rel or check_id,
        "exists" if path_exists(root, rel) else "missing",
        "existing path",
    )


def main() -> int:
    parser = root_arg()
    args = parser.parse_args()
    root = resolve_root(args.root)
    checks: list[dict[str, str]] = []

    registry = read_json(root / "context/global/PROJECT_REGISTRY.json", {})
    active = read_json(root / "context/global/ACTIVE_PROJECT.json", {})
    project_id = active.get("active_project_id", "default") if isinstance(active, dict) else "default"
    projects = registry.get("projects", {}) if isinstance(registry, dict) else {}
    project = projects.get(project_id, {}) if isinstance(projects, dict) else {}

    add_check(
        checks,
        "active_project_registered",
        "registry",
        "PASS" if project else "FAIL",
        "HIGH",
        "context/global/ACTIVE_PROJECT.json",
        project_id if project else "missing",
        "active project exists in registry",
    )
    for key in [
        "boot_path",
        "state_path",
        "verdict_path",
        "budgets_path",
        "invariants_path",
        "read_policy_path",
        "startup_bundle_path",
    ]:
        if key == "startup_bundle_path":
            severity = "MEDIUM"
        else:
            severity = "HIGH"
        check_rel(checks, root, f"project_{key}_exists", str(project.get(key, "")), severity)

    state = read_json(root / str(project.get("state_path", "context/TASK_STATE.json")), {})
    # A business runner lives in the project root, which may be outside the workspace.
    runner = str(state.get("current_runner", ""))
    runner_ok = bool(runner) and bool(project) and resolve_runner_path(root, project, runner).is_file()
    add_check(
        checks,
        "task_current_runner_exists",
        "path",
        "PASS" if runner_ok else "FAIL",
        "HIGH",
        runner or "task_current_runner_exists",
        "exists" if runner_ok else "missing",
        "existing path",
    )
    for key in ["latest_gap_queue_path", "latest_verdict_path"]:
        check_rel(checks, root, f"task_{key}_exists", str(state.get(key, "")), "HIGH")
    summary_rel = str(state.get("latest_summary_path", ""))
    if summary_rel:
        check_rel(checks, root, "task_latest_summary_path_exists", summary_rel, "MEDIUM")
    else:
        # Project-local task states (projects other than default) carry no summary pointer.
        add_check(checks, "task_latest_summary_path_exists", "path", "WARN", "MEDIUM", "task_latest_summary_path_exists", "not set", "existing path")

    for rel in [
        "context/indexes/views/FILE_INDEX_VIEW.csv",
        "context/indexes/views/RUNNER_INDEX_VIEW.csv",
        "context/indexes/views/CASE_INDEX_VIEW.csv",
        "context/indexes/views/EVIDENCE_INDEX_VIEW.csv",
        "context/indexes/views/GAP_INDEX_VIEW.csv",
        "tools/context/query_index.py",
        "tools/context/read_gate/read_context_file.py",
        "tools/context/start_project.sh",
        "tools/context/continue_project.sh",
    ]:
        check_rel(checks, root, f"exists_{Path(rel).stem.lower()}", rel)

    summary = write_check_outputs(root, "path_consistency_check", checks)
    print(summary["verdict"])
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
