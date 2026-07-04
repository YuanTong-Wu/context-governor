#!/usr/bin/env python3
"""Build context/indexes/RUNNER_INDEX.csv."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from context_common import (
    AUDIT_DIR_REL,
    artifact_id,
    ensure_dirs,
    infer_phase,
    relpath,
    sha256_file,
    utc_now,
    write_csv,
    write_script_audit,
)
from governor_common import get_project, project_index_path, project_scan_root


FIELDS = [
    "runner_id",
    "project_id",
    "path",
    "phase",
    "purpose",
    "run_command",
    "input_contract",
    "output_contract",
    "status",
    "last_run_at_utc",
    "last_verdict_path",
    "safe_to_rerun",
    "writes_to",
    "reads_from",
    "forbidden_reads",
    "notes",
]


def read_purpose(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except Exception:
        return "runner"
    doc = re.search(r'"""(.*?)"""', text, re.S)
    if doc:
        return " ".join(doc.group(1).strip().split())[:180]
    for line in text.splitlines()[:20]:
        stripped = line.strip(" #")
        if stripped and not stripped.startswith("#!/"):
            return stripped[:180]
    return "runner"


def infer_contracts(rel: str) -> tuple[str, str, str, str]:
    name = Path(rel).name
    if name == "build_file_index.py":
        return "repository files", "context/indexes/FILE_INDEX.csv", "context/indexes/FILE_INDEX.csv,var/context_control_2026_06_23/audit", ".git,node_modules,holdout_content"
    if name == "build_runner_index.py":
        return "tools/**/*.py,tools/**/*.sh", "context/indexes/RUNNER_INDEX.csv", "context/indexes/RUNNER_INDEX.csv,var/context_control_2026_06_23/audit", "holdout_content"
    if name == "build_case_index.py":
        return "case file metadata", "context/indexes/CASE_INDEX.csv", "context/indexes/CASE_INDEX.csv,var/context_control_2026_06_23/audit", "sealed_sample_content"
    if name == "build_evidence_index.py":
        return "evidence manifest metadata", "context/indexes/EVIDENCE_INDEX.csv", "context/indexes/EVIDENCE_INDEX.csv,var/context_control_2026_06_23/audit", "external_side_effect_interfaces"
    if name == "build_gap_index.py":
        return "**/gap_queue.csv", "context/indexes/GAP_INDEX.csv", "context/indexes/GAP_INDEX.csv,var/context_control_2026_06_23/audit", "none"
    if name == "build_boot_context.py":
        return "invariants,state,verdict,indexes", "BOOT.md,context/generated manifests", "BOOT.md,context/generated,var/context_control_2026_06_23", "raw_evidence_content"
    if name == "context_integrity_check.py":
        return "BOOT.md,state,verdict,indexes", "audit integrity outputs", "var/context_control_2026_06_23/audit", "external_side_effect_interfaces"
    if name == "context_repair.py":
        return "integrity outputs and context files", "repaired context files and quarantine manifest", "context/quarantine,var/context_control_2026_06_23/audit", "raw_evidence_content"
    if name == "update_task_state.py":
        return "latest summary/verdict/manifest/gap", "context/TASK_STATE.json", "context/TASK_STATE.json", "raw_evidence_content"
    if name == "run_context_control_all.sh":
        return "repository context files", "context microkernel outputs", "context,var/context_control_2026_06_23", "external_side_effect_interfaces"
    return "script-specific", "script-specific", "script-specific", "external_side_effect_interfaces"


def run_command(rel: str) -> str:
    if rel.endswith(".sh"):
        return f"bash {rel}"
    return f"python3 {rel}"


def indexed_rel(root: Path, scan_root: Path, path: Path) -> str:
    if scan_root.resolve() != root.resolve():
        try:
            return str(path.resolve().relative_to(scan_root.resolve()))
        except Exception:
            return str(path.resolve())
    return relpath(root, path)


def build_runner_index(root: Path, project_id: str | None = None) -> tuple[list[dict[str, str]], dict[str, str]]:
    project = get_project(root, project_id)
    scan_root = project_scan_root(root, project)
    tools_root = scan_root / "tools"
    rows: list[dict[str, str]] = []
    for path in sorted(tools_root.rglob("*")) if tools_root.exists() else []:
        if not path.is_file() or path.suffix.lower() not in {".py", ".sh"}:
            continue
        rel = indexed_rel(root, scan_root, path)
        input_contract, output_contract, writes_to, forbidden_reads = infer_contracts(rel)
        verdict_path = root / AUDIT_DIR_REL / f"{Path(path).stem}_verdict.json"
        rows.append(
            {
                "runner_id": artifact_id("runner", f"{project['project_id']}:{rel}"),
                "project_id": str(project["project_id"]),
                "path": rel,
                "phase": infer_phase(Path(rel)),
                "purpose": read_purpose(path),
                "run_command": run_command(rel),
                "input_contract": input_contract,
                "output_contract": output_contract,
                "status": "ACTIVE",
                "last_run_at_utc": "",
                "last_verdict_path": relpath(root, verdict_path) if verdict_path.exists() else "",
                "safe_to_rerun": "TRUE",
                "writes_to": writes_to,
                "reads_from": input_contract,
                "forbidden_reads": forbidden_reads,
                "notes": f"sha256={sha256_file(path)}",
            }
        )
    return rows, project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    ensure_dirs(root)
    rows, project = build_runner_index(root, args.project_id)
    output_path = project_index_path(root, project, "runner")
    write_csv(output_path, FIELDS, rows)
    now = utc_now()
    summary = {
        "script": "build_runner_index.py",
        "project_id": project["project_id"],
        "scan_root": str(project_scan_root(root, project)),
        "created_at_utc": now,
        "output_path": relpath(root, output_path),
        "row_count": len(rows),
    }
    verdict = {
        "script": "build_runner_index.py",
        "project_id": project["project_id"],
        "created_at_utc": now,
        "verdict": "RUNNER_INDEX_BUILT",
        "hard_blocker": False,
    }
    manifest = [
        {
            "artifact_path": relpath(root, output_path),
            "artifact_role": "output",
            "sha256": sha256_file(output_path),
            "created_at_utc": now,
            "notes": "runner index",
        }
    ]
    write_script_audit(root, "build_runner_index", summary, verdict, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
