#!/usr/bin/env python3
"""Shared helpers for the multi-project context governor."""

from __future__ import annotations

import csv
import fnmatch
import json
import os
from pathlib import Path
from typing import Any, Iterable

from context_common import (
    append_jsonl,
    artifact_id,
    char_count,
    coerce_root,
    read_csv,
    read_json,
    relpath,
    sha256_file,
    utc_now,
    write_csv,
    write_json,
)


GOVERNOR_DIR_REL = Path("var/context_governor_2026_06_24")
GOVERNOR_AUDIT_DIR_REL = GOVERNOR_DIR_REL / "audit"
GOVERNOR_REPORT_DIR_REL = GOVERNOR_DIR_REL / "reports"
DEV_CHANGE_DIR_REL = Path("var/dev_change_control_2026_06_24")

GLOBAL_DIR_REL = Path("context/global")
PROJECTS_DIR_REL = Path("context/projects")
GLOBAL_BUDGET_REL = Path("context/budgets/GLOBAL_CONTEXT_BUDGET.json")
READ_LOG_REL = Path("context/read_logs/CONTEXT_READ_LOG.jsonl")
INDEX_QUERY_LOG_REL = Path("context/read_logs/INDEX_QUERY_LOG.jsonl")

PROJECT_FIELDS = [
    "project_id",
    "project_name",
    "project_root",
    "boot_path",
    "state_path",
    "verdict_path",
    "indexes_dir",
    "file_index_path",
    "runner_index_path",
    "gap_index_path",
    "case_index_path",
    "evidence_index_path",
    "budgets_path",
    "invariants_path",
    "read_policy_path",
    "startup_bundle_path",
    "status",
    "active_status",
    "authority_profile",
    "forbidden_actions",
    "holdout_policy",
    "created_at_utc",
    "updated_at_utc",
]

GOVERNOR_GAP_FIELDS = [
    "gap_id",
    "phase",
    "project_id",
    "artifact_path",
    "gap_type",
    "severity",
    "blocking_level",
    "observed_status",
    "expected_status",
    "next_action",
    "created_at_utc",
    "notes",
]

GOVERNOR_BLOCKED_FIELDS = [
    "blocked_id",
    "phase",
    "project_id",
    "artifact_path",
    "reason",
    "severity",
    "created_at_utc",
    "next_action",
    "notes",
]

DEFAULT_BUDGET: dict[str, int] = {
    "boot_max_lines": 80,
    "boot_max_chars": 4000,
    "task_state_max_lines": 200,
    "verdict_max_lines": 120,
    "startup_bundle_max_chars": 12000,
    "startup_bundle_max_files": 8,
    "index_view_max_rows": 200,
    "index_view_max_chars": 30000,
    "single_file_default_max_chars": 30000,
    "large_file_threshold_chars": 50000,
    "large_csv_threshold_rows": 1000,
    "gap_view_max_rows": 100,
    "case_view_max_rows": 100,
    "evidence_view_max_rows": 100,
    "max_files_opened_at_startup": 8,
}


def ensure_governor_dirs(root: Path) -> None:
    for rel in [
        GLOBAL_DIR_REL,
        PROJECTS_DIR_REL,
        Path("context/generated/startup_bundles"),
        Path("context/indexes/views"),
        Path("context/indexes/shards/by_project"),
        Path("context/indexes/shards/by_artifact_type"),
        Path("context/indexes/shards/by_phase"),
        Path("context/read_logs"),
        Path("context/budgets"),
        Path("tools/context/read_gate"),
        Path("tools/context/project"),
        Path("tools/context/hooks"),
        Path("tools/context/tests"),
        Path("tools/dev"),
        Path("docs/context"),
        Path("docs/dev"),
        GOVERNOR_DIR_REL,
        GOVERNOR_AUDIT_DIR_REL,
        GOVERNOR_REPORT_DIR_REL,
        DEV_CHANGE_DIR_REL,
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def ensure_governor_csvs(root: Path) -> None:
    ensure_governor_dirs(root)
    gap = root / GOVERNOR_DIR_REL / "gap_queue.csv"
    blocked = root / GOVERNOR_DIR_REL / "blocked_reason.csv"
    if not gap.exists():
        write_csv(gap, GOVERNOR_GAP_FIELDS, [])
    if not blocked.exists():
        write_csv(blocked, GOVERNOR_BLOCKED_FIELDS, [])


def append_governor_gap(root: Path, row: dict[str, Any]) -> None:
    ensure_governor_csvs(root)
    path = root / GOVERNOR_DIR_REL / "gap_queue.csv"
    rows = read_csv(path)
    body = dict(row)
    body.setdefault("gap_id", artifact_id("gov_gap", json.dumps(body, ensure_ascii=False, sort_keys=True)))
    body.setdefault("created_at_utc", utc_now())
    rows.append(body)
    write_csv(path, GOVERNOR_GAP_FIELDS, rows)


def append_governor_blocked(root: Path, row: dict[str, Any]) -> None:
    ensure_governor_csvs(root)
    path = root / GOVERNOR_DIR_REL / "blocked_reason.csv"
    rows = read_csv(path)
    body = dict(row)
    body.setdefault("blocked_id", artifact_id("gov_blocked", json.dumps(body, ensure_ascii=False, sort_keys=True)))
    body.setdefault("created_at_utc", utc_now())
    rows.append(body)
    write_csv(path, GOVERNOR_BLOCKED_FIELDS, rows)


def default_project_record(root: Path, project_id: str, project_name: str, project_root: str | Path | None = None) -> dict[str, Any]:
    project_root_path = Path(project_root).expanduser().resolve() if project_root else root.resolve()
    now = utc_now()
    return {
        "project_id": project_id,
        "project_name": project_name,
        "project_root": str(project_root_path),
        "boot_path": "BOOT.md" if project_root_path == root.resolve() else f"context/projects/{project_id}/BOOT.md",
        "state_path": "context/TASK_STATE.json" if project_id == "default" else f"context/projects/{project_id}/TASK_STATE.json",
        "verdict_path": "context/CURRENT_VERDICT.json" if project_id == "default" else f"context/projects/{project_id}/CURRENT_VERDICT.json",
        "indexes_dir": "context/indexes" if project_id == "default" else f"context/projects/{project_id}/indexes",
        "file_index_path": "context/indexes/FILE_INDEX.csv" if project_id == "default" else f"context/projects/{project_id}/indexes/FILE_INDEX.csv",
        "runner_index_path": "context/indexes/RUNNER_INDEX.csv" if project_id == "default" else f"context/projects/{project_id}/indexes/RUNNER_INDEX.csv",
        "gap_index_path": "context/indexes/GAP_INDEX.csv" if project_id == "default" else f"context/projects/{project_id}/indexes/GAP_INDEX.csv",
        "case_index_path": "context/indexes/CASE_INDEX.csv" if project_id == "default" else f"context/projects/{project_id}/indexes/CASE_INDEX.csv",
        "evidence_index_path": "context/indexes/EVIDENCE_INDEX.csv" if project_id == "default" else f"context/projects/{project_id}/indexes/EVIDENCE_INDEX.csv",
        "budgets_path": f"context/projects/{project_id}/CONTEXT_BUDGET.json",
        "invariants_path": "context/SYSTEM_INVARIANTS.json" if project_id == "default" else f"context/projects/{project_id}/SYSTEM_INVARIANTS.json",
        "read_policy_path": "context/CONTEXT_LOAD_POLICY.md" if project_id == "default" else f"context/projects/{project_id}/CONTEXT_LOAD_POLICY.md",
        "startup_bundle_path": f"context/generated/startup_bundles/{project_id}_STARTUP_BUNDLE.md",
        "status": "active" if project_id == "default" else "inactive",
        "active_status": "active" if project_id == "default" else "inactive",
        "authority_profile": "system_invariants_first_generated_summaries_lowest",
        "forbidden_actions": [
            "external_side_effects",
            "external_side_effect_interfaces",
            "unlock_holdout_samples",
            "recursive_entry_files",
            "startup_full_index_reads",
        ],
        "holdout_policy": "LOCKED",
        "created_at_utc": now,
        "updated_at_utc": now,
    }


def registry_path(root: Path) -> Path:
    return root / GLOBAL_DIR_REL / "PROJECT_REGISTRY.json"


def active_project_path(root: Path) -> Path:
    return root / GLOBAL_DIR_REL / "ACTIVE_PROJECT.json"


def projects_csv_path(root: Path) -> Path:
    return root / GLOBAL_DIR_REL / "PROJECTS.csv"


def load_registry(root: Path) -> dict[str, Any]:
    data = read_json(registry_path(root), None)
    if isinstance(data, dict):
        data.setdefault("projects", {})
        return data
    return {"registry_version": "1.0", "projects": {}, "updated_at_utc": utc_now()}


def save_registry(root: Path, registry: dict[str, Any]) -> None:
    registry["updated_at_utc"] = utc_now()
    write_json(registry_path(root), registry)
    rows = []
    for project in registry.get("projects", {}).values():
        row = dict(project)
        if isinstance(row.get("forbidden_actions"), list):
            row["forbidden_actions"] = ";".join(row["forbidden_actions"])
        rows.append(row)
    write_csv(projects_csv_path(root), PROJECT_FIELDS, rows)


def set_active_project(root: Path, project_id: str) -> dict[str, Any]:
    registry = load_registry(root)
    if project_id not in registry.get("projects", {}):
        raise SystemExit(f"unknown project_id: {project_id}")
    for pid, project in registry["projects"].items():
        project["active_status"] = "active" if pid == project_id else "inactive"
        project["updated_at_utc"] = utc_now()
    save_registry(root, registry)
    active = {"active_project_id": project_id, "updated_at_utc": utc_now()}
    write_json(active_project_path(root), active)
    return registry["projects"][project_id]


def get_active_project(root: Path) -> dict[str, Any]:
    registry = load_registry(root)
    active = read_json(active_project_path(root), {})
    project_id = active.get("active_project_id") or "default"
    if project_id not in registry.get("projects", {}):
        if registry.get("projects"):
            project_id = sorted(registry["projects"])[0]
        else:
            project = default_project_record(root, "default", "Default Project", root)
            registry["projects"][project["project_id"]] = project
            save_registry(root, registry)
            project_id = project["project_id"]
    return registry["projects"][project_id]


def get_project(root: Path, project_id: str | None = None) -> dict[str, Any]:
    registry = ensure_default_registry(root)
    if not project_id:
        return get_active_project(root)
    if project_id not in registry.get("projects", {}):
        raise SystemExit(f"unknown project_id: {project_id}")
    return registry["projects"][project_id]


def ensure_default_registry(root: Path) -> dict[str, Any]:
    ensure_governor_dirs(root)
    registry = load_registry(root)
    if "default" not in registry.get("projects", {}):
        project = default_project_record(root, "default", "Default Project", root)
        registry.setdefault("projects", {})[project["project_id"]] = project
        save_registry(root, registry)
    if not active_project_path(root).exists():
        set_active_project(root, "default")
    return load_registry(root)


def write_default_budgets(root: Path, project_id: str = "default") -> None:
    ensure_governor_dirs(root)
    global_budget = dict(DEFAULT_BUDGET)
    global_budget.update({"budget_version": "1.0", "scope": "global", "updated_at_utc": utc_now()})
    write_json(root / GLOBAL_BUDGET_REL, global_budget)
    project_budget = dict(DEFAULT_BUDGET)
    project_budget.update({"budget_version": "1.0", "scope": "project", "project_id": project_id, "updated_at_utc": utc_now()})
    write_json(root / PROJECTS_DIR_REL / project_id / "CONTEXT_BUDGET.json", project_budget)


def load_budget(root: Path, project: dict[str, Any] | None = None) -> dict[str, int]:
    budget: dict[str, Any] = dict(DEFAULT_BUDGET)
    global_budget = read_json(root / GLOBAL_BUDGET_REL, {})
    if isinstance(global_budget, dict):
        budget.update({k: v for k, v in global_budget.items() if isinstance(v, int)})
    if project:
        project_budget = read_json(root / str(project.get("budgets_path", "")), {})
        if isinstance(project_budget, dict):
            budget.update({k: v for k, v in project_budget.items() if isinstance(v, int)})
    return {k: int(v) for k, v in budget.items() if isinstance(v, int)}


def project_abs_path(root: Path, project: dict[str, Any], rel_or_abs: str | Path) -> Path:
    path = Path(rel_or_abs)
    if path.is_absolute():
        return path
    rel_text = str(path)
    if rel_text.startswith(("context/projects/", "context/generated/", "context/global/", "context/budgets/")):
        return (root / path).resolve()
    project_root = Path(str(project.get("project_root") or root)).expanduser().resolve()
    return (project_root / path).resolve()


def project_control_path(root: Path, project: dict[str, Any], rel_or_abs: str | Path) -> Path:
    path = Path(rel_or_abs)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def project_scan_root(root: Path, project: dict[str, Any]) -> Path:
    project_root = Path(str(project.get("project_root") or root)).expanduser().resolve()
    return project_root if project_root.exists() else root.resolve()


def project_indexes_dir(root: Path, project: dict[str, Any]) -> Path:
    return project_control_path(root, project, str(project.get("indexes_dir") or "context/indexes"))


def project_views_dir(root: Path, project: dict[str, Any]) -> Path:
    return project_indexes_dir(root, project) / "views"


def project_shards_dir(root: Path, project: dict[str, Any]) -> Path:
    return project_indexes_dir(root, project) / "shards"


def project_index_path(root: Path, project: dict[str, Any], index_name: str) -> Path:
    key = index_name.lower()
    if key.endswith("_index"):
        key = key[:-6]
    field = {
        "file": "file_index_path",
        "runner": "runner_index_path",
        "gap": "gap_index_path",
        "case": "case_index_path",
        "evidence": "evidence_index_path",
    }.get(key)
    if not field:
        raise ValueError(f"unknown project index: {index_name}")
    return project_control_path(root, project, str(project.get(field) or f"context/indexes/{key.upper()}_INDEX.csv"))


def is_allowlisted(root: Path, rel: str, allowlist: dict[str, Any]) -> bool:
    entries = allowlist.get("allowed_paths", []) if isinstance(allowlist, dict) else []
    for pattern in entries:
        if rel == pattern or fnmatch.fnmatch(rel, pattern):
            return True
    return False


def file_metadata(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": relpath(root, path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "chars": char_count(path) if path.exists() and path.is_file() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else "",
    }


def filtered_rows(rows: Iterable[dict[str, str]], filters: dict[str, str]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        keep = True
        for key, expected in filters.items():
            if not expected:
                continue
            if key == "path_contains":
                keep = expected.lower() in str(row.get("path", "")).lower()
            elif key in {"blocking_level", "severity", "status", "phase", "artifact_type", "case_id", "entity_key"}:
                keep = str(row.get(key, "")).lower() == expected.lower()
            elif key == "project":
                keep = str(row.get("project_id", "default") or "default") == expected
            else:
                keep = str(row.get(key, "")).lower() == expected.lower()
            if not keep:
                break
        if keep:
            output.append(row)
    return output


def write_jsonl_log(root: Path, rel: Path, row: dict[str, Any]) -> None:
    append_jsonl(root / rel, row)


def shell_quote(path: str) -> str:
    return "'" + path.replace("'", "'\"'\"'") + "'"
