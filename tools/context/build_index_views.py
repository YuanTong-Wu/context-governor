#!/usr/bin/env python3
"""Build small startup-safe index views and coarse shards from full indexes."""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from context_common import read_csv, read_json, relpath, utc_now, write_csv, write_json
from governor_common import (
    append_governor_gap,
    ensure_default_registry,
    ensure_governor_dirs,
    get_project,
    load_budget,
    project_abs_path,
    project_index_path,
    project_shards_dir,
    project_views_dir,
)


INDEX_KEYS = {
    "FILE_INDEX": "file",
    "RUNNER_INDEX": "runner",
    "CASE_INDEX": "case",
    "EVIDENCE_INDEX": "evidence",
    "GAP_INDEX": "gap",
}

SEVERITY_SCORE = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1, "": 0}
BLOCKING_SCORE = {"BLOCKING": 5, "HARD_BLOCK": 5, "SOFT_BLOCK": 3, "WARNING": 2, "OPEN": 1, "": 0}


def safe_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip() or "unknown")
    return name[:120]


def with_project(rows: list[dict[str, str]], project_id: str) -> list[dict[str, str]]:
    output = []
    for row in rows:
        body = dict(row)
        body.setdefault("project_id", project_id)
        output.append(body)
    return output


def fieldnames(rows: list[dict[str, Any]], fallback: list[str]) -> list[str]:
    fields = list(fallback)
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    for required in ["project_id", "view_reason", "view_rank"]:
        if required not in fields:
            fields.append(required)
    return fields


def csv_char_size(fields: list[str], rows: list[dict[str, str]]) -> int:
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return len(handle.getvalue())


def trim_to_char_budget(rows: list[dict[str, str]], fallback_fields: list[str], max_chars: int) -> list[dict[str, str]]:
    if not rows:
        return rows
    fields = fieldnames(rows, fallback_fields)
    trimmed = list(rows)
    while trimmed and csv_char_size(fields, trimmed) > max_chars:
        trimmed = trimmed[:-1]
    return trimmed


def score_file_row(row: dict[str, str], phase: str, runner: str) -> tuple[int, str]:
    path = row.get("path", "")
    artifact = row.get("artifact_type", "")
    score = 0
    reasons = []
    if runner and path == runner:
        score += 100
        reasons.append("current_runner")
    if phase and phase != "unspecified" and phase.lower() in path.lower():
        score += 45
        reasons.append("current_phase")
    if artifact in {"boot", "task_state", "verdict", "invariant", "summary", "manifest", "gap_queue", "runner"}:
        score += 30
        reasons.append(f"artifact:{artifact}")
    if path.startswith(("context/", "tools/context/", "var/context_governor_2026_06_24/")):
        score += 20
        reasons.append("context_governance_path")
    if row.get("status") == "ACTIVE":
        score += 5
    return score, ";".join(reasons) or "top_context_relevance"


def choose_file_view(rows: list[dict[str, str]], limit: int, phase: str, runner: str) -> list[dict[str, str]]:
    ranked = []
    for row in rows:
        score, reason = score_file_row(row, phase, runner)
        body = dict(row)
        body["view_reason"] = reason
        body["view_rank"] = str(score)
        ranked.append(body)
    ranked.sort(key=lambda row: (int(row.get("view_rank", "0") or 0), row.get("modified_at_utc", "")), reverse=True)
    return ranked[:limit]


def choose_runner_view(rows: list[dict[str, str]], limit: int, phase: str, runner: str) -> list[dict[str, str]]:
    ranked = []
    for row in rows:
        path = row.get("path", "")
        score = 0
        reason = []
        if runner and path == runner:
            score += 100
            reason.append("current_runner")
        if phase and phase != "unspecified" and row.get("phase") == phase:
            score += 30
            reason.append("current_phase")
        if path.startswith("tools/context/"):
            score += 20
            reason.append("context_governance_runner")
        body = dict(row)
        body["project_id"] = body.get("project_id", "default")
        body["view_reason"] = ";".join(reason) or "runner_relevance"
        body["view_rank"] = str(score)
        ranked.append(body)
    ranked.sort(key=lambda row: int(row.get("view_rank", "0") or 0), reverse=True)
    return ranked[:limit]


def choose_gap_view(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    ranked = []
    for row in rows:
        score = SEVERITY_SCORE.get(row.get("severity", "").upper(), 0) * 10
        score += BLOCKING_SCORE.get(row.get("blocking_level", "").upper(), 0)
        body = dict(row)
        body["project_id"] = body.get("project_id", "default")
        body["view_reason"] = "highest_blocking_gaps"
        body["view_rank"] = str(score)
        ranked.append(body)
    ranked.sort(key=lambda row: int(row.get("view_rank", "0") or 0), reverse=True)
    return ranked[:limit]


def choose_simple_view(rows: list[dict[str, str]], limit: int, reason: str) -> list[dict[str, str]]:
    output = []
    for idx, row in enumerate(rows[:limit]):
        body = dict(row)
        body["project_id"] = body.get("project_id", "default")
        body["view_reason"] = reason
        body["view_rank"] = str(limit - idx)
        output.append(body)
    return output


def write_view(root: Path, views_dir: Path, name: str, rows: list[dict[str, str]], fallback_fields: list[str], max_chars: int) -> dict[str, Any]:
    rows = trim_to_char_budget(rows, fallback_fields, max_chars)
    path = views_dir / f"{name}_VIEW.csv"
    write_csv(path, fieldnames(rows, fallback_fields), rows)
    return {"view_name": f"{name}_VIEW", "path": relpath(root, path), "rows": len(rows)}


def write_shards(root: Path, shards_dir: Path, file_rows: list[dict[str, str]], project_id: str, fields: list[str]) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    by_project = shards_dir / "by_project" / f"{project_id}_FILE_INDEX.csv"
    write_csv(by_project, fields, file_rows)
    manifests.append({"shard_type": "by_project", "path": relpath(root, by_project), "rows": len(file_rows)})

    artifact_groups: dict[str, list[dict[str, str]]] = {}
    phase_groups: dict[str, list[dict[str, str]]] = {}
    for row in file_rows:
        artifact_groups.setdefault(safe_name(row.get("artifact_type", "unknown")), []).append(row)
        phase_groups.setdefault(safe_name(row.get("phase", "unspecified")), []).append(row)

    for artifact, rows in artifact_groups.items():
        path = shards_dir / "by_artifact_type" / f"{artifact}.csv"
        write_csv(path, fields, rows)
        manifests.append({"shard_type": "by_artifact_type", "path": relpath(root, path), "rows": len(rows)})
    for phase, rows in phase_groups.items():
        path = shards_dir / "by_phase" / f"{phase}.csv"
        write_csv(path, fields, rows)
        manifests.append({"shard_type": "by_phase", "path": relpath(root, path), "rows": len(rows)})
    return manifests


def build(root: Path, project_id: str | None = None) -> dict[str, Any]:
    ensure_governor_dirs(root)
    ensure_default_registry(root)
    project = get_project(root, project_id)
    budget = load_budget(root, project)
    project_id = project["project_id"]
    task = read_json(project_abs_path(root, project, str(project.get("state_path", "context/TASK_STATE.json"))), {})
    phase = str(task.get("current_phase", "unspecified"))
    runner = str(task.get("current_runner", ""))
    views_dir = project_views_dir(root, project)
    shards_dir = project_shards_dir(root, project)

    full: dict[str, list[dict[str, str]]] = {}
    for name, key in INDEX_KEYS.items():
        source_path = project_index_path(root, project, key)
        rows = read_csv(source_path)
        full[name] = with_project(rows, project_id)
        if not rows:
            append_governor_gap(
                root,
                {
                    "phase": "build_index_views",
                    "project_id": project_id,
                    "artifact_path": relpath(root, source_path),
                    "gap_type": "missing_or_empty_index",
                    "severity": "MEDIUM",
                    "blocking_level": "WARNING",
                    "observed_status": "empty",
                    "expected_status": "rows_available",
                    "next_action": "run the corresponding full index builder",
                },
            )

    max_rows = int(budget["index_view_max_rows"])
    max_chars = int(budget["index_view_max_chars"])
    views = [
        write_view(root, views_dir, "FILE_INDEX", choose_file_view(full["FILE_INDEX"], max_rows, phase, runner), list(full["FILE_INDEX"][0].keys()) if full["FILE_INDEX"] else [], max_chars),
        write_view(root, views_dir, "RUNNER_INDEX", choose_runner_view(full["RUNNER_INDEX"], max_rows, phase, runner), list(full["RUNNER_INDEX"][0].keys()) if full["RUNNER_INDEX"] else [], max_chars),
        write_view(root, views_dir, "CASE_INDEX", choose_simple_view(full["CASE_INDEX"], int(budget["case_view_max_rows"]), "current_or_high_priority_cases"), list(full["CASE_INDEX"][0].keys()) if full["CASE_INDEX"] else [], max_chars),
        write_view(root, views_dir, "EVIDENCE_INDEX", choose_simple_view(full["EVIDENCE_INDEX"], int(budget["evidence_view_max_rows"]), "current_phase_evidence_pointers"), list(full["EVIDENCE_INDEX"][0].keys()) if full["EVIDENCE_INDEX"] else [], max_chars),
        write_view(root, views_dir, "GAP_INDEX", choose_gap_view(full["GAP_INDEX"], int(budget["gap_view_max_rows"])), list(full["GAP_INDEX"][0].keys()) if full["GAP_INDEX"] else [], max_chars),
    ]

    file_fields = fieldnames(full["FILE_INDEX"], list(full["FILE_INDEX"][0].keys()) if full["FILE_INDEX"] else [])
    shards = write_shards(root, shards_dir, full["FILE_INDEX"], project_id, file_fields)

    manifest_path = views_dir / "INDEX_VIEW_MANIFEST.csv"
    write_csv(manifest_path, ["view_name", "path", "rows"], views)
    summary = {
        "script": "build_index_views.py",
        "project_id": project_id,
        "current_phase": phase,
        "current_runner": runner,
        "views": views,
        "shards_written": len(shards),
        "max_view_rows": max_rows,
        "updated_at_utc": utc_now(),
    }
    write_json(views_dir / "INDEX_VIEW_SUMMARY.json", summary)
    write_csv(views_dir / "INDEX_SHARD_MANIFEST.csv", ["shard_type", "path", "rows"], shards)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()
    summary = build(Path(args.root).expanduser().resolve(), args.project_id)
    print(f"index views built for {summary['project_id']}: {len(summary['views'])} views")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
