#!/usr/bin/env python3
"""Validate small schema and structured context files."""

from __future__ import annotations

from pathlib import Path

from dev_common import add_check, csv_header, json_parse_ok, read_json, resolve_root, root_arg, write_check_outputs


def require_fields(checks: list[dict[str, str]], root: Path, rel: str, fields: set[str]) -> None:
    path = root / rel
    header = set(csv_header(path)) if path.exists() else set()
    missing = sorted(fields - header)
    add_check(
        checks,
        f"csv_fields_{Path(rel).stem.lower()}",
        "schema",
        "PASS" if path.exists() and not missing else "FAIL",
        "HIGH",
        rel,
        "missing=" + ",".join(missing) if missing else "present",
        "required fields present",
    )


def main() -> int:
    parser = root_arg()
    args = parser.parse_args()
    root = resolve_root(args.root)
    checks: list[dict[str, str]] = []

    for rel in [
        "context/SYSTEM_INVARIANTS.json",
        "context/TASK_STATE.json",
        "context/CURRENT_VERDICT.json",
        "context/global/PROJECT_REGISTRY.json",
        "context/global/ACTIVE_PROJECT.json",
        "context/budgets/GLOBAL_CONTEXT_BUDGET.json",
    ]:
        path = root / rel
        ok, observed = json_parse_ok(path)
        add_check(checks, f"json_parse_{path.stem.lower()}", "schema", "PASS" if ok else "FAIL", "HIGH", rel, observed, "valid json")

    for schema in sorted((root / "context/schemas").glob("*.json")):
        ok, observed = json_parse_ok(schema)
        add_check(checks, f"json_parse_schema_{schema.stem}", "schema", "PASS" if ok else "FAIL", "MEDIUM", str(schema.relative_to(root)), observed, "valid json")

    registry = read_json(root / "context/global/PROJECT_REGISTRY.json", {})
    projects = registry.get("projects", {}) if isinstance(registry, dict) else {}
    default_project = projects.get("default", {}) if isinstance(projects, dict) else {}
    required_project_keys = {
        "project_id",
        "project_root",
        "boot_path",
        "state_path",
        "verdict_path",
        "file_index_path",
        "runner_index_path",
        "gap_index_path",
        "budgets_path",
        "startup_bundle_path",
    }
    missing_project_keys = sorted(required_project_keys - set(default_project))
    add_check(
        checks,
        "registry_default_required_keys",
        "schema",
        "PASS" if not missing_project_keys else "FAIL",
        "HIGH",
        "context/global/PROJECT_REGISTRY.json",
        "missing=" + ",".join(missing_project_keys) if missing_project_keys else "present",
        "required project keys",
    )

    require_fields(checks, root, "context/global/PROJECTS.csv", required_project_keys)
    require_fields(checks, root, "context/indexes/views/FILE_INDEX_VIEW.csv", {"path", "artifact_type", "read_policy"})
    require_fields(checks, root, "context/indexes/views/RUNNER_INDEX_VIEW.csv", {"path", "status", "run_command"})
    require_fields(checks, root, "context/indexes/views/GAP_INDEX_VIEW.csv", {"gap_id", "severity", "blocking_level", "next_action"})

    summary = write_check_outputs(root, "schema_compat_check", checks)
    print(summary["verdict"])
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
