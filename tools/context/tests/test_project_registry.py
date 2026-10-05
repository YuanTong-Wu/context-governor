#!/usr/bin/env python3
"""Verify the project registry and active project contract."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from test_common import assert_true, read_json


REQUIRED_FIELDS = {
    "project_id",
    "project_name",
    "project_root",
    "boot_path",
    "state_path",
    "verdict_path",
    "indexes_dir",
    "budgets_path",
    "invariants_path",
    "read_policy_path",
    "startup_bundle_path",
    "active_status",
    "authority_profile",
    "forbidden_actions",
    "created_at_utc",
    "updated_at_utc",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()

    registry_path = root / "context/global/PROJECT_REGISTRY.json"
    active_path = root / "context/global/ACTIVE_PROJECT.json"
    projects_csv = root / "context/global/PROJECTS.csv"
    assert_true(registry_path.exists(), "PROJECT_REGISTRY.json missing")
    assert_true(active_path.exists(), "ACTIVE_PROJECT.json missing")
    assert_true(projects_csv.exists(), "PROJECTS.csv missing")

    registry = read_json(registry_path)
    active = read_json(active_path)
    project_id = active.get("active_project_id")
    projects = registry.get("projects", {})
    assert_true("default" in projects, "root project 'default' missing from registry")
    assert_true(project_id in projects, f"active project is not registered: {project_id}")
    project = projects.get(project_id, {})
    missing = sorted(REQUIRED_FIELDS - set(project))
    assert_true(not missing, f"project registry missing fields: {missing}")
    assert_true(project.get("holdout_policy") == "LOCKED", "holdout policy must be LOCKED")
    assert_true(project.get("active_status") == "active", "active project must have active_status=active")

    for key in ["boot_path", "state_path", "verdict_path", "budgets_path", "invariants_path", "read_policy_path", "startup_bundle_path"]:
        path = root / str(project[key])
        assert_true(path.exists(), f"registry path missing: {key}={project[key]}")

    with projects_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert_true(any(row.get("project_id") == project_id for row in rows), "PROJECTS.csv missing active project")
    print("project registry test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

