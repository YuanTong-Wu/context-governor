#!/usr/bin/env python3
"""Refresh context/TASK_STATE.json from the latest context-control outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from context_common import (
    AUDIT_DIR_REL,
    CONTROL_DIR_REL,
    GENERATED_DIR_REL,
    append_blocked,
    ensure_dirs,
    line_count,
    read_csv,
    read_json,
    relpath,
    utc_now,
    write_json,
    write_json_with_self_sha,
    write_script_audit,
)


def indexed_runner(root: Path) -> str:
    rows = read_csv(root / "context/indexes/RUNNER_INDEX.csv")
    paths = {row.get("path", "") for row in rows}
    for preferred in [
        "tools/context/run_context_governor_all.sh",
        "tools/context/run_context_control_all.sh",
    ]:
        if preferred in paths and (root / preferred).exists():
            return preferred
    for row in rows:
        rel = row.get("path", "")
        if rel and (root / rel).exists() and row.get("status") == "ACTIVE":
            return rel
    return preferred


def update_state(root: Path) -> dict[str, str]:
    ensure_dirs(root)
    now = utc_now()
    integrity = read_json(root / AUDIT_DIR_REL / "context_integrity_verdict.json", {})
    verdict = integrity.get("verdict", "CONTEXT_INTEGRITY_UNKNOWN")
    hard_blocker = bool(integrity.get("hard_blocker", True))
    state = {
        "task_state_version": "1.0",
        "updated_at_utc": now,
        "updated_by": "tools/context/update_task_state.py",
        "current_phase": "context_microkernel_verified" if not hard_blocker else "context_microkernel_needs_repair",
        "context_integrity_status": verdict,
        "current_runner": indexed_runner(root),
        "current_runner_args": [],
        "next_allowed_action": "Use BOOT.md plus the active project startup bundle; rerun tools/context/run_context_governor_all.sh after context edits."
        if not hard_blocker
        else "Run tools/context/context_repair.py before using BOOT.md as startup context.",
        "latest_gap_queue_path": str(CONTROL_DIR_REL / "gap_queue.csv"),
        "latest_manifest_path": str(GENERATED_DIR_REL / "BOOT_BUILD_MANIFEST.csv"),
        "source_manifest_path": str(GENERATED_DIR_REL / "BOOT_SOURCE_MANIFEST.csv"),
        "latest_summary_path": str(CONTROL_DIR_REL / "summary.json"),
        "latest_verdict_path": "context/CURRENT_VERDICT.json",
        "writable_output_dir": str(CONTROL_DIR_REL),
        "readonly_input_dirs": ["."],
        "holdout_status": "LOCKED",
        "forbidden_actions": [
            "external_side_effects",
            "external_side_effect_interfaces",
            "unlock_holdout_samples",
            "recursive_entry_files",
            "startup_full_index_reads",
        ],
        "sha256_self": "",
    }
    write_json_with_self_sha(root / "context/TASK_STATE.json", state)
    if line_count(root / "context/TASK_STATE.json") > 200:
        append_blocked(
            root,
            {
                "phase": "context_control",
                "artifact_path": "context/TASK_STATE.json",
                "reason": "TASK_STATE exceeds 200 lines after update",
                "severity": "HIGH",
                "next_action": "Compact TASK_STATE.json and rerun update_task_state.py.",
                "notes": "",
            },
        )
        raise RuntimeError("TASK_STATE exceeds 200 lines")
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    state = update_state(root)
    now = utc_now()
    summary = {
        "script": "update_task_state.py",
        "created_at_utc": now,
        "output_path": "context/TASK_STATE.json",
        "line_count": line_count(root / "context/TASK_STATE.json"),
        "context_integrity_status": state["context_integrity_status"],
    }
    verdict = {
        "script": "update_task_state.py",
        "created_at_utc": now,
        "verdict": "TASK_STATE_UPDATED",
        "hard_blocker": False,
    }
    write_json(root / AUDIT_DIR_REL / "update_task_state_summary.json", summary)
    write_script_audit(
        root,
        "update_task_state",
        summary,
        verdict,
        [
            {
                "artifact_path": "context/TASK_STATE.json",
                "artifact_role": "output",
                "sha256": "",
                "created_at_utc": now,
                "notes": "compact task state",
            }
        ],
    )
    print(f"Updated {relpath(root, root / 'context/TASK_STATE.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
